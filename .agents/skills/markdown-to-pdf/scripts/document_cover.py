"""Move centralized document presentation into an optional, single-page cover."""

from __future__ import annotations

import os
import tempfile
import unicodedata
from pathlib import Path


def apply_cover(html_document: str, metadata: dict[str, str], logo_uri: str | None,
                structure_module) -> str:
    """Return HTML with the existing title, subtitle and metadata on a cover.

    The caller first centralizes metadata, marking direct children of ``main``
    with their document roles. Only those nodes move; introductory prose and
    nested tables remain in the body. IDs and existing captions move with their
    nodes, so navigation can be generated afterwards without duplicate targets.
    ``logo_uri`` is an already validated, embedded image supplied by the caller.
    """
    s = structure_module
    parser = s._DocumentParser()
    parser.feed(html_document)
    parser.close()
    root = parser.root
    main = next((node for node in s._walk(root) if node.tag == "main"), None)
    if main is None:
        raise ValueError("La portada requiere un documento HTML con contenido principal main.")
    if any(node.get("data-document-role") == "cover" for node in main.children):
        return html_document

    presentation = []
    for role in ("title", "subtitle", "metadata"):
        node = next((node for node in main.children
                     if node.get("data-document-role") == role), None)
        if node is not None and s._label(node):
            presentation.append(node)

    def is_classification_row(row):
        cells = [child for child in row.children if child.tag in {"td", "th"}]
        if len(cells) != 2:
            return False
        label = "".join(char for char in unicodedata.normalize("NFD", s._label(cells[0]))
                        if not unicodedata.combining(char)).casefold().strip(" :")
        return label == "clasificacion" and bool(s._label(cells[1]))

    classification = metadata.get("clasificacion", "")
    if any(is_classification_row(row) for node in presentation
           if node.get("data-document-role") == "metadata"
           for row in s._walk(node) if row.tag == "tr"):
        classification = ""
    if not presentation and not logo_uri and not classification:
        raise ValueError("La portada no tiene contenido visible. Añade un título, metadatos "
                         "o un logotipo, o desactívala con --no-cover / pdf.portada: false.")

    cover = s._Node("section", [("class", "document-cover"),
                                ("data-document-role", "cover"),
                                ("aria-label", "Portada")])
    if logo_uri or classification:
        top = s._Node("div", [("class", "document-cover-top")])
        if logo_uri:
            top.append(s._Node("img", [("class", "document-cover-logo logo"),
                                       ("data-document-role", "cover-logo"),
                                       ("src", logo_uri), ("alt", "Logotipo")]))
        if classification:
            label = s._Node("p", [("class", "document-cover-classification"),
                                  ("data-document-role", "cover-classification")])
            label.append(s._literal(classification))
            top.append(label)
        cover.append(top)
    if presentation:
        content = s._Node("div", [("class", "document-cover-content")])
        for node in presentation:
            content.append(node)
        cover.append(content)
    cover.parent = main
    main.children.insert(0, cover)
    return s._serialize(root)


def replace_cover_page(pdf_path: Path, clean_cover_pdf: Path) -> None:
    """Replace only page one's drawing, retaining the complete PDF navigation.

    Both PDFs must be rendered from the same DOM and with identical page
    geometry. The clean rendition disables browser headers and footers. Keeping
    the original Page object preserves bookmarks, annotations, named targets
    and the structure tree's page references; only its content and resources
    are cloned from the clean rendition. Publication is atomic.
    """
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import DictionaryObject, NameObject
    except ImportError as exc:
        raise ValueError("La portada requiere pypdf en el entorno local del skill.") from exc

    pdf_path = Path(pdf_path)
    clean_cover_pdf = Path(clean_cover_pdf)
    if pdf_path.resolve() == clean_cover_pdf.resolve():
        raise ValueError("El PDF completo y el PDF de portada deben ser archivos distintos.")
    temporary = None
    try:
        with PdfReader(str(pdf_path)) as original, PdfReader(str(clean_cover_pdf)) as clean:
            if not original.pages or not clean.pages:
                raise ValueError("El PDF completo y la portada deben contener al menos una página.")
            first = original.pages[0]
            replacement = clean.pages[0]
            for box in ("mediabox", "cropbox"):
                old_box, new_box = getattr(first, box), getattr(replacement, box)
                if any(abs(float(before) - float(after)) > 0.01
                       for before, after in zip(old_box, new_box)):
                    raise ValueError("La geometría del PDF de portada no coincide con la primera página.")
            if (first.rotation != replacement.rotation
                    or abs(first.user_unit - replacement.user_unit) > 0.0001):
                raise ValueError("La orientación o escala del PDF de portada no coincide con la primera página.")
            if "/StructParents" in first:
                def marked_content(page):
                    content = page.get_contents()
                    if content is None:
                        return []
                    return [(str(operands[0]), int(operands[1]["/MCID"]))
                            for operands, operator in content.operations
                            if operator == b"BDC" and len(operands) == 2
                            and isinstance(operands[1], DictionaryObject) and "/MCID" in operands[1]]

                if marked_content(first) != marked_content(replacement):
                    raise ValueError("La estructura etiquetada de la portada cambió al omitir el encabezado "
                                     "y el pie. Vuelve a renderizar ambos PDF desde el mismo documento.")
            # pypdf's writer context manager reinitializes the instance on entry,
            # discarding clone_from. Preserve the cloned catalog and Page objects.
            writer = PdfWriter(clone_from=original)
            try:
                target = writer.pages[0]
                for key in ("/Contents", "/Resources"):
                    if key in replacement:
                        target[NameObject(key)] = replacement.raw_get(key).clone(writer)
                    else:
                        target.pop(key, None)
                with tempfile.NamedTemporaryFile(
                    dir=pdf_path.parent, prefix=f".{pdf_path.name}.cover-", suffix=".pdf", delete=False,
                ) as output:
                    temporary = Path(output.name)
                    writer.write(output)
                    output.flush()
                    os.fsync(output.fileno())
            finally:
                writer.close()
        os.replace(temporary, pdf_path)
        temporary = None
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"No se pudo integrar la portada sin encabezado ni pie: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
