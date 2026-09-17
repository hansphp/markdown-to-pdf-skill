"""Resolve document metadata without changing the source Markdown.

The initial ``documento`` and ``pdf`` YAML mappings configure the document.
Existing documents retain their exact HTML when no metadata override was requested.
The structure module is passed in so the converter can load local modules
without requiring its scripts directory on the Python import path.
"""

from __future__ import annotations

import re
import unicodedata


FIELDS = ("titulo", "subtitulo", "codigo", "version", "fecha", "estado", "clasificacion")
LABELS = {
    "titulo": "Título", "subtitulo": "Subtítulo", "codigo": "Código",
    "version": "Versión", "fecha": "Fecha", "estado": "Estado",
    "clasificacion": "Clasificación",
}


def _frontmatter_parts(markdown):
    lines = markdown.splitlines(keepends=True)
    if not lines or lines[0].lstrip("\ufeff").strip() != "---":
        return None
    end = next((index for index, line in enumerate(lines[1:], 1)
                if line.strip() in {"---", "..."}), None)
    source = "".join(lines[1:end]) if end is not None else "".join(lines[1:])
    relevant = re.search(r"(?m)(?:^|[{,])\s*['\"]?(?:documento|pdf)['\"]?\s*:", source)
    if not relevant:
        return None
    return lines, end, source


def has_metadata_frontmatter(markdown: str) -> bool:
    """Whether metadata parsing is needed, without importing optional YAML."""
    return _frontmatter_parts(markdown) is not None


def read_frontmatter(markdown: str) -> tuple[str, dict[str, str] | None]:
    """Compatibility wrapper returning only the body and document metadata."""
    body, config, _ = read_configuration(markdown)
    return body, config


def read_configuration(markdown: str) -> tuple[str, dict[str, str] | None, dict]:
    """Read document metadata and PDF options from the initial YAML block.

    YAML is imported only when the initial block mentions our configuration.
    Document values are strings or explicit empty values (``null`` / ``""``).
    PDF options retain their types and distinguish absent keys from overrides;
    the caller resolves precedence and logo paths relative to the Markdown.
    Unrelated front matter remains available to the legacy parser. Errors refer
    to source Markdown line numbers.
    """
    parts = _frontmatter_parts(markdown)
    if parts is None:
        return markdown, None, {}
    lines, end, source = parts
    if end is None:
        raise ValueError("El front matter de metadatos iniciado en la línea 1 necesita un cierre ---.")

    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError("La configuración documento/pdf requiere PyYAML; usa el entorno local .venv "
                         "del skill con las dependencias de requirements.txt.") from exc

    class LocatedMap(dict):
        def __init__(self, mark):
            super().__init__()
            self.mark = mark
            self.key_marks = {}
            self.value_marks = {}
            self.value_nodes = {}

    class UniqueLoader(yaml.SafeLoader):
        pass

    def construct_mapping(loader, node):
        result = LocatedMap(node.start_mark)
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=True)
            try:
                duplicate = key in result
            except TypeError:
                raise yaml.constructor.ConstructorError(
                    None, None, "clave YAML no válida", key_node.start_mark)
            if duplicate:
                raise yaml.constructor.ConstructorError(
                    None, None, f"clave duplicada: {key}", key_node.start_mark)
            result[key] = loader.construct_object(value_node, deep=True)
            result.key_marks[key] = key_node.start_mark
            result.value_marks[key] = value_node.start_mark
            result.value_nodes[key] = value_node
        return result

    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)

    def fail(message, mark=None):
        location = f"línea {mark.line + 2}, columna {mark.column + 1}" if mark else "línea 2"
        raise ValueError(f"Metadatos YAML inválidos en {location}: {message}")

    try:
        data = yaml.load(source, Loader=UniqueLoader)
    except yaml.YAMLError as exc:
        fail(getattr(exc, "problem", None) or str(exc), getattr(exc, "problem_mark", None))
    if not isinstance(data, dict):
        fail("se esperaba un mapa con la clave documento o pdf.")
    pdf_options = {}
    if "pdf" in data:
        pdf = data["pdf"]
        if pdf is None:
            pdf = {}
        if not isinstance(pdf, dict):
            fail("pdf debe ser un mapa de opciones y valores.", data.value_marks["pdf"])
        for key, value in pdf.items():
            if key not in {"portada", "logo", "indice_tablas", "indice_figuras", "validacion"}:
                fail(f"opción pdf.{key} desconocida. Opciones admitidas: portada, logo, indice_tablas, indice_figuras, validacion.",
                     pdf.key_marks[key])
            if key in {"portada", "indice_tablas", "indice_figuras"}:
                # PyYAML also resolves yes/on as booleans; keep the documented
                # true/false spelling explicit and reject integers and strings.
                if type(value) is not bool or pdf.value_nodes[key].value.lower() not in {"true", "false"}:
                    fail(f"pdf.{key} debe ser un booleano true o false, sin comillas.",
                         pdf.value_marks[key])
            elif key == "validacion":
                if value not in ("normal", "estricta"):
                    fail("pdf.validacion debe ser normal o estricta.", pdf.value_marks[key])
            elif value is not None:
                if not isinstance(value, str) or not value.strip():
                    fail("pdf.logo debe ser una ruta local de texto no vacía o null para omitir el logotipo.",
                         pdf.value_marks[key])
                if re.match(r"(?:[a-z][a-z0-9+.-]*:|//)", value.lstrip(), re.I) or "\x00" in value:
                    fail("pdf.logo debe ser una ruta local, no una URL.", pdf.value_marks[key])
            pdf_options[key] = value
    config = None
    if "documento" in data:
        document = data["documento"]
        if document is None:
            document = {}
        if not isinstance(document, dict):
            fail("documento debe ser un mapa de campos y valores.", data.value_marks["documento"])
        config = {}
        for key, value in document.items():
            if key not in FIELDS:
                fail(f"campo documento.{key} desconocido. Campos admitidos: {', '.join(FIELDS)}.",
                     document.key_marks[key])
            if value is not None and not isinstance(value, str):
                fail(f"documento.{key} debe ser texto o null; escribe números, fechas y "
                     "booleanos entre comillas para conservar su formato.", document.value_marks[key])
            config[key] = value if value is not None else ""
    return "".join(lines[end + 1:]), config, pdf_options


def _field(label):
    normalized = "".join(char for char in unicodedata.normalize("NFD", label.casefold())
                         if unicodedata.category(char) != "Mn")
    normalized = re.sub(r"\s+", " ", normalized).strip().rstrip(":")
    return {"codigo del documento": "codigo", "codigo de documento": "codigo"}.get(
        normalized, normalized if normalized in FIELDS else None)


def resolve_document(html_document: str, config: dict | None, overrides: dict[str, str],
                     fallback: str, structure_module) -> tuple[str, dict[str, str]]:
    """Resolve CLI > YAML > recognized Markdown, then update only document data.

    Active metadata does not invent a title or subtitle. The filename title and
    first H2 subtitle are legacy-only defaults. ``CONFIDENCIAL`` remains the
    default header classification, but does not create an extra metadata row.
    Explicit empty values suppress presentation and prevent lower-priority
    fallbacks. IDs on replaced headings and table cells stay valid.
    """
    s = structure_module
    parser = s._DocumentParser()
    parser.feed(html_document)
    parser.close()
    root = parser.root
    main = next((node for node in s._walk(root) if node.tag == "main"), None)
    if main is None:
        main = next((node for node in s._walk(root) if node.tag == "body"), root)
    nodes = list(s._walk(main))
    headings = [node for node in nodes if node.tag in s.HEADING_TAGS]
    active = config is not None or bool(overrides)
    document_headings = [node for node in headings if node.parent is main] if active else headings
    title = next((node for node in document_headings if node.get("data-document-role") == "title"), None)
    if title is None:
        title = next((node for node in document_headings if node.tag == "h1"), None)
    subtitle = next((node for node in document_headings if node.get("data-document-role") == "subtitle"), None)
    if subtitle is None:
        subtitle = s._subtitle(title, document_headings)
        if subtitle is not None and s._label(subtitle).casefold() in {
            "control de cambios", "historial de cambios", "histórico de cambios", "registro de cambios",
        }:
            subtitle = None

    resolved = dict.fromkeys(FIELDS, "")
    if not active:
        resolved["titulo"] = s._label(title) if title is not None else fallback
        first_h2 = next((node for node in headings if node.tag == "h2"), None)
        resolved["subtitulo"] = s._label(first_h2) if first_h2 is not None else ""
        resolved["clasificacion"] = "CONFIDENCIAL"
        return html_document, resolved

    def table_rows(table):
        return [(row, [cell for cell in row.children if cell.tag in {"th", "td"}])
                for row in s._walk(table) if row.tag == "tr"]

    first_section = next((node for node in headings if node not in (title, subtitle)), None)
    before = nodes[:nodes.index(first_section)] if first_section is not None else nodes
    table = next((node for node in before if node.tag == "table" and node.parent is main and (
        node.get("data-document-role") == "metadata" or (
            table_rows(node) and [s._label(cell).casefold() for cell in table_rows(node)[0][1]] == ["dato", "valor"]
            and any(_field(s._label(cells[0])) for _, cells in table_rows(node)[1:] if len(cells) == 2)
        ))), None)
    row_fields = {}
    present = set()
    if table is not None:
        for row, cells in table_rows(table)[1:]:
            if len(cells) != 2:
                continue
            field = _field(s._label(cells[0]))
            if field:
                row_fields.setdefault(field, []).append((row, cells[1]))
                if field not in present:
                    resolved[field] = s._label(cells[1])
                present.add(field)
    for field, node in (("titulo", title), ("subtitulo", subtitle)):
        if node is not None:
            resolved[field] = s._label(node)
            present.add(field)
    for source in (config or {}, overrides):
        for field, value in source.items():
            if field not in FIELDS or not isinstance(value, str):
                raise ValueError(f"Metadato no válido: {field}; se requiere un campo conocido y texto.")
            resolved[field] = value
            present.add(field)
    if "clasificacion" not in present:
        resolved["clasificacion"] = "CONFIDENCIAL"

    def set_value(node, value):
        # Preserve linked anchors below the changed node as well as its own ID.
        anchors = []
        for child in s._walk(node):
            if child is not node and child.get("id"):
                anchors.append(s._Node("span", [("id", child.get("id"))]))
        for child in list(node.children):
            child.remove()
        for anchor in anchors:
            node.append(anchor)
        node.append(s._literal(value))

    def remove_presentation(node):
        # Empty fields remove their visible layout while retaining link targets.
        anchors = [child.get("id") for child in s._walk(node) if child.get("id")]
        reference = node
        if node.tag == "tr":
            while reference.parent is not None and reference.tag != "table":
                reference = reference.parent
        for identifier in anchors:
            s._insert_before(reference, s._Node("span", [("id", identifier)]))
        node.remove()

    def at_start(node):
        node.parent = main
        main.children.insert(0, node)

    def after(reference, node):
        node.remove()
        node.parent = reference.parent
        reference.parent.children.insert(reference.parent.children.index(reference) + 1, node)

    for field, node, tag, role in (("titulo", title, "h1", "title"),
                                   ("subtitulo", subtitle, "h2", "subtitle")):
        value = resolved[field]
        if node is not None:
            if value:
                node.set("data-document-role", role)
                if s._label(node) != value:
                    set_value(node, value)
            else:
                remove_presentation(node)
                node = None
        elif value:
            node = s._Node(tag, [("data-document-role", role)])
            if field in row_fields and field not in (config or {}) and field not in overrides:
                # Inherited Markdown remains markup when a metadata cell becomes
                # a heading. Moving its children preserves formulas, note calls,
                # links and their IDs without duplicating them in the old row.
                cell = row_fields[field][0][1]
                for child in list(cell.children):
                    node.append(child)
            else:
                # YAML and CLI values are explicitly plain text, even when they
                # happen to match the text of a formatted Markdown cell.
                node.append(s._literal(value))
            if role == "subtitle" and title is not None:
                after(title, node)
            else:
                at_start(node)
        if role == "title":
            title = node
        else:
            subtitle = node

    # Generated metadata can change the subtitle heuristic; keep actual body
    # headings as sections, even when an explicit empty title removed an H1.
    for heading in headings:
        if heading.parent is not None and heading not in (title, subtitle):
            heading.set("data-document-role", "section")

    # Existing data rows retain ordering, unknown fields and cell attributes.
    # Title/subtitle values move into headings, without duplicate table rows.
    for field, rows in row_fields.items():
        for row, cell in rows:
            if field in {"titulo", "subtitulo"}:
                remove_presentation(row)
            elif resolved[field]:
                if s._label(cell) != resolved[field]:
                    set_value(cell, resolved[field])
            else:
                remove_presentation(row)
    missing = [field for field in FIELDS if field in present and resolved[field]
               and field not in row_fields and field not in {"titulo", "subtitulo"}]
    if table is None and missing:
        table = s._Node("table", [("data-document-role", "metadata")])
        head = s._Node("thead")
        row = s._Node("tr")
        for label in ("Dato", "Valor"):
            cell = s._Node("th")
            cell.append(s._literal(label))
            row.append(cell)
        head.append(row)
        table.append(head)
        if subtitle is not None or title is not None:
            after(subtitle if subtitle is not None else title, table)
        else:
            at_start(table)
    if table is not None:
        table.set("data-document-role", "metadata")
        if missing:
            body = next((child for child in table.children if child.tag == "tbody"), None)
            if body is None:
                body = s._Node("tbody")
                table.append(body)
            for field in missing:
                row = s._Node("tr")
                for value in (LABELS[field], resolved[field]):
                    cell = s._Node("td")
                    cell.append(s._literal(value))
                    row.append(cell)
                body.append(row)
        if len(table_rows(table)) == 1:
            remove_presentation(table)

    # Browser/PDF document title shares the same source, including an empty one.
    for node in s._walk(root):
        if node.tag == "title":
            set_value(node, resolved["titulo"])
    return s._serialize(root), resolved


def refresh_generated_metadata(html_document: str, resolved: dict[str, str],
                               centralized: bool, structure_module) -> tuple[str, dict[str, str]]:
    """Read final heading content after references and notes have been resolved.

    Return the DOM IDs to read again after KaTeX rendering. This first pass also
    updates the basic engine's title without requiring a browser or math assets.
    Explicit omissions and the legacy filename/first-H2 defaults remain intact.
    """
    s = structure_module
    parser = s._DocumentParser()
    parser.feed(html_document)
    parser.close()
    root = parser.root
    main = next((node for node in s._walk(root) if node.tag == "main"), None)
    if main is None:
        return html_document, {}

    def text(node):
        if node.get("role") == "doc-noteref":
            return "[" + s._label(node) + "]"
        if node.tag.startswith("#") or node.tag in {"br", "style", "script"}:
            return s._text(node)
        return "".join(text(child) for child in node.children)

    headings = [node for node in s._walk(main) if node.tag in s.HEADING_TAGS]
    targets = {}
    for field, role, tag in (("titulo", "title", "h1"), ("subtitulo", "subtitle", "h2")):
        if centralized:
            heading = next((node for node in headings if node.get("data-document-role") == role), None)
        else:
            heading = next((node for node in headings if node.tag == tag and node.parent is main), None)
        if heading is None:
            continue
        resolved[field] = re.sub(r"\s+", " ", text(heading)).strip()
        if heading.get("id"):
            targets[field] = heading.get("id")
    for node in s._walk(root):
        if node.tag == "title":
            for child in list(node.children):
                child.remove()
            node.append(s._literal(resolved["titulo"]))
    return s._serialize(root), targets
