"""Resuelve navegación a partir del PDF maquetado, sin estimar alturas del HTML.

Usa destinos PDF nativos y conserva el archivo generado por el navegador.
API de referencia: https://pypdf.readthedocs.io/en/stable/modules/PdfReader.html
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Callable, Iterable, Mapping
from urllib.parse import quote, unquote


class NavigationError(RuntimeError):
    """El PDF no permite verificar una navegación completa y consistente."""


def _entries(entries: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    result = []
    seen = set()
    for entry in entries:
        identifier = entry.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise NavigationError("Cada entrada del índice debe tener un identificador de destino.")
        if identifier in seen:
            raise NavigationError(f"Identificador de índice duplicado: {identifier}")
        seen.add(identifier)
        result.append(dict(entry))
    return result


def _open_pdf(pdf_path: Path):
    # Importación diferida: el motor básico no necesita esta dependencia.
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise NavigationError("El índice automático requiere pypdf en el entorno local del skill.") from exc
    try:
        return PdfReader(str(pdf_path))
    except Exception as exc:
        raise NavigationError(f"No se pudo leer la navegación del PDF {pdf_path}: {exc}") from exc


def _destination_details(reader, destination, source: str, name: str | None = None) -> dict[str, object]:
    page_index = reader.get_destination_page_number(destination)
    if page_index is None or page_index < 0 or page_index >= len(reader.pages):
        raise NavigationError(f"El destino {name or destination.get('/Title', '')} no apunta a una página válida.")
    array = destination.dest_array
    coordinates = []
    for value in array[2:]:
        if isinstance(value, (int, float)):
            coordinates.append(float(value))
        else:
            coordinates.append(None if value.__class__.__name__ == "NullObject" else str(value))
    return {
        "page": page_index + 1,
        "page_index": page_index,
        "fit": str(array[1]),
        "coordinates": coordinates,
        "source": source,
        "named_destination": name,
    }


def _flatten_outline(items, level: int = 1):
    for item in items:
        if isinstance(item, list):
            yield from _flatten_outline(item, level + 1)
        else:
            yield item, level


def _named_match(named, identifier: str):
    # Chrome exporta IDs Unicode como nombres PDF /cap%C3%ADtulo. Se prueban
    # primero coincidencias literales para no confundir un % escapado con otro ID.
    encoded = quote(identifier, safe="-._~")
    for candidate in (identifier, "/" + identifier, encoded, "/" + encoded):
        if candidate in named:
            return candidate, named[candidate]
    matches = [(name, destination) for name, destination in named.items()
               if unquote(str(name).removeprefix("/")) == identifier]
    if len(matches) > 1:
        raise NavigationError(f"Hay varios destinos PDF para el identificador {identifier}.")
    return matches[0] if matches else None


def resolve_toc_destinations(
    pdf_path: Path,
    entries: Iterable[Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    """Devuelve página física y coordenadas PDF para cada ID del índice.

    Los destinos nombrados tienen prioridad y distinguen títulos repetidos.
    Si faltan, un marcador de título único puede servir como alternativa. Un
    título repetido sin ID verificable se rechaza en lugar de elegir una página.
    """
    items = _entries(entries)
    if not items:
        return {}
    reader = _open_pdf(Path(pdf_path))
    try:
        named = reader.named_destinations
        result = {}
        missing = []
        outline = None
        title_counts = {}
        for entry in items:
            title = entry.get("title")
            if isinstance(title, str):
                title_counts[title] = title_counts.get(title, 0) + 1
        for entry in items:
            identifier = entry["id"]
            matched = _named_match(named, identifier)
            if matched:
                name, destination = matched
                result[identifier] = _destination_details(reader, destination, "named", str(name))
                continue
            if outline is None:
                outline = list(_flatten_outline(reader.outline))
            title = entry.get("title")
            alternatives = [destination for destination, _ in outline
                            if title and str(destination.get("/Title", "")) == title]
            if len(alternatives) == 1 and title_counts.get(title) == 1:
                result[identifier] = _destination_details(reader, alternatives[0], "outline")
            else:
                missing.append(identifier)
        if missing:
            raise NavigationError("No se pudieron verificar los destinos del índice: " + ", ".join(missing))
        return result
    finally:
        reader.close()


def resolve_toc_pages(pdf_path: Path, entries: Iterable[Mapping[str, object]]) -> dict[str, int]:
    """Resuelve números de página físicos, comenzando en uno."""
    return {identifier: int(details["page"])
            for identifier, details in resolve_toc_destinations(pdf_path, entries).items()}


def read_bookmarks(pdf_path: Path) -> list[dict[str, object]]:
    """Lee marcadores en orden y conserva títulos duplicados y jerarquía."""
    reader = _open_pdf(Path(pdf_path))
    try:
        result = []
        for destination, level in _flatten_outline(reader.outline):
            details = _destination_details(reader, destination, "outline")
            details.update(title=str(destination.get("/Title", "")), level=level)
            result.append(details)
        return result
    finally:
        reader.close()


def update_bookmark_labels(pdf_path: Path, headings: list[dict]) -> None:
    """Replace only outline titles, preserving native destinations and hierarchy.

    The renderer supplies visible headings in DOM order and the text Chromium
    uses for each native bookmark. Validate that sequence before any mutation;
    repeated titles are therefore matched by occurrence, never by title alone.
    """
    if not any(heading.get("needs_update") for heading in headings):
        return
    try:
        from pypdf import PdfWriter
        from pypdf.generic import NameObject, TextStringObject
    except ImportError as exc:
        raise NavigationError(
            "Los marcadores con fórmulas o notas requieren pypdf en el entorno local del skill."
        ) from exc

    normalized = lambda value: re.sub(r"\s+", " ", str(value)).strip()
    expected = [heading for heading in headings if normalized(heading["native_title"])]
    reader = _open_pdf(pdf_path)
    try:
        writer = PdfWriter(clone_from=reader)
        outlines = writer.root_object.get("/Outlines")
        nodes = []

        def visit(reference):
            while reference:
                node = reference.get_object()
                nodes.append(node)
                visit(node.get("/First"))
                reference = node.get("/Next")

        if outlines:
            visit(outlines.get_object().get("/First"))
        if len(nodes) != len(expected) or any(
                normalized(node.get("/Title", "")) != normalized(heading["native_title"])
                for node, heading in zip(nodes, expected)):
            raise NavigationError(
                "Los marcadores nativos no coinciden con los encabezados renderizados; "
                "no se pueden actualizar sus textos sin alterar la navegación."
            )
        for node, heading in zip(nodes, expected):
            if heading.get("needs_update"):
                node[NameObject("/Title")] = TextStringObject(heading["title"])
        output = io.BytesIO()
        writer.write(output)
    finally:
        reader.close()
    Path(pdf_path).write_bytes(output.getvalue())


def validate_navigation(
    pdf_path: Path,
    entries: Iterable[Mapping[str, object]],
    expected_pages: Mapping[str, int] | None = None,
) -> dict[str, int]:
    """Comprueba destinos y, si se proporcionan, las páginas impresas del índice."""
    resolved = resolve_toc_pages(pdf_path, entries)
    if expected_pages is not None and dict(expected_pages) != resolved:
        differences = [identifier for identifier in sorted(set(expected_pages) | set(resolved))
                       if expected_pages.get(identifier) != resolved.get(identifier)]
        raise NavigationError("Las páginas del índice no coinciden con sus destinos: " + ", ".join(differences))
    return resolved


def stabilize_toc(
    render_pass: Callable[[dict[str, int]], Path],
    entries: Iterable[Mapping[str, object]],
    max_passes: int = 4,
) -> tuple[Path, dict[str, int], int]:
    """Renderiza hasta que las páginas impresas coincidan con el PDF de esa pasada.

    El callback recibe {} en la primera pasada y después el mapa de páginas de
    la anterior. Debe renderizar el documento completo, incluidos todos los
    índices, y devolver su ruta. Se devuelve (ruta, páginas, pasadas). Si el
    índice ocupa varias páginas, sus desplazamientos quedan incluidos en los
    destinos reales de cada nueva pasada.
    """
    if isinstance(max_passes, bool) or not isinstance(max_passes, int) or not 1 <= max_passes <= 4:
        raise NavigationError("El índice admite entre una y cuatro pasadas de renderizado.")
    items = _entries(entries)
    printed_pages: dict[str, int] = {}
    for pass_number in range(1, max_passes + 1):
        pdf_path = Path(render_pass(dict(printed_pages)))
        actual_pages = resolve_toc_pages(pdf_path, items)
        if printed_pages == actual_pages:
            return pdf_path, actual_pages, pass_number
        printed_pages = actual_pages
    raise NavigationError(
        f"El índice no alcanzó una paginación estable después de {max_passes} pasadas; no se publicará este resultado."
    )
