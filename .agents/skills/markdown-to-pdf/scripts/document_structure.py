"""Add document navigation and captions to the converter's HTML using stdlib."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser


VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}
HEADING_TAGS = {f"h{level}" for level in range(1, 7)}
NUMBERED_SECTION = re.compile(r"^\s*\d+(?:\.\d+)*[.)]?\s+\S")
REFERENCE_ID = re.compile(r"(?:tbl|fig):[\w][\w.:-]*\Z", re.UNICODE)
GENERATED_NAVIGATION = {"toc", "toc-break", "table-index", "figure-index"}
METADATA_KEYS = {
    "organización", "producto", "producto y entrega", "tipo de documento",
    "versión", "estado", "fecha", "fuentes", "guía utilizada",
    "referencia de análisis", "destinatarios", "aplicación",
}


class _Node:
    def __init__(self, tag: str, attrs=None, data: str = ""):
        self.tag = tag
        self.attrs = list(attrs or [])
        self.data = data
        self.children: list[_Node] = []
        self.parent: _Node | None = None

    def get(self, name: str, default=None):
        return next((value for key, value in self.attrs if key == name), default)

    def set(self, name: str, value: str) -> None:
        self.attrs = [(key, current) for key, current in self.attrs if key != name]
        self.attrs.append((name, value))

    def append(self, node: _Node) -> None:
        if node.parent is not None:
            node.parent.children.remove(node)
        node.parent = self
        self.children.append(node)

    def remove(self) -> None:
        if self.parent is not None:
            self.parent.children.remove(self)
            self.parent = None


class _DocumentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.root = _Node("#document")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, attrs)
        self.stack[-1].append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].append(_Node(tag, attrs))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        self.stack[-1].append(_Node("#text", data=data))

    def handle_entityref(self, name):
        self.handle_data(f"&{name};")

    def handle_charref(self, name):
        self.handle_data(f"&#{name};")

    def handle_comment(self, data):
        self.stack[-1].append(_Node("#raw", data=f"<!--{data}-->"))

    def handle_decl(self, decl):
        self.stack[-1].append(_Node("#raw", data=f"<!{decl}>"))

    def handle_pi(self, data):
        self.stack[-1].append(_Node("#raw", data=f"<?{data}>"))


def _walk(node):
    if not node.tag.startswith("#"):
        yield node
    for child in node.children:
        yield from _walk(child)


def _serialize(node):
    if node.tag in {"#text", "#raw"}:
        return node.data
    children = "".join(_serialize(child) for child in node.children)
    if node.tag == "#document":
        return children
    attrs = "".join(
        f" {key}" if value is None else f' {key}="{html.escape(value, quote=True)}"'
        for key, value in node.attrs
    )
    if node.tag in VOID_TAGS:
        return f"<{node.tag}{attrs}>"
    return f"<{node.tag}{attrs}>{children}</{node.tag}>"


def _text(node):
    if node.tag == "#text":
        return html.unescape(node.data)
    if node.tag in {"#raw", "style", "script"}:
        return ""
    if node.tag == "br":
        return " "
    return "".join(_text(child) for child in node.children)


def _label(node):
    return re.sub(r"\s+", " ", _text(node)).strip()


def _literal(text):
    return _Node("#text", data=html.escape(text, quote=False))


def _label_content(node, keep_references=False):
    """Copy inline labels without creating extra destinations or note calls.

    References remain active only while composing an inferred body caption.
    Links in navigation labels are unwrapped because the whole entry is already
    a link. Mathematical placeholders retain their markup for browser rendering.
    """
    result = []
    for child in node.children:
        classes = (child.get("class") or "").split()
        if "document-footnote-reference" in classes or child.get("role") == "doc-noteref":
            result.append(_literal("[" + _label(child) + "]"))
            continue
        if child.tag in {"#raw", "style", "script"}:
            continue
        if child.tag == "#text":
            result.append(_Node("#text", data=child.data))
            continue
        if child.tag == "img":
            result.append(_literal(child.get("alt") or ""))
            continue
        content = _label_content(child, keep_references)
        reference = child.get("data-document-reference") if keep_references else None
        if child.tag == "a" and reference is None:
            result.extend(content)
            continue
        attrs = [(key, value) for key, value in child.attrs
                 if key not in {"id", "href", "aria-labelledby", "aria-describedby",
                                "data-document-reference", "data-document-reference-alias",
                                "data-document-generated", "data-document-anchor"}]
        copied = _Node("span" if child.tag == "a" else child.tag, attrs)
        if reference is not None:
            copied.set("data-document-reference", reference)
        for descendant in content:
            copied.append(descendant)
        result.append(copied)
    return result


def _label_fragment(node, prefix=None, keep_references=False):
    fragment = _Node("span")
    for child in _label_content(node, keep_references):
        fragment.append(child)
    if prefix:
        match = re.match(prefix, _text(fragment))
        if match:
            _remove_text_prefix(fragment, match.end())
    return fragment


def _inline_html(node):
    return "".join(_serialize(child) for child in node.children)


def _classes(node, added):
    classes = (node.get("class") or "").split()
    if added not in classes:
        classes.append(added)
    node.set("class", " ".join(classes))


def _insert_before(reference, inserted):
    parent = reference.parent
    position = parent.children.index(reference)
    inserted.remove()
    inserted.parent = parent
    parent.children.insert(position, inserted)


def _previous_element(node):
    if node.parent is None:
        return None
    position = node.parent.children.index(node)
    for sibling in reversed(node.parent.children[:position]):
        if sibling.tag == "#raw" or (sibling.tag == "#text" and not sibling.data.strip()):
            continue
        return sibling
    return None


def _remove_text_prefix(node, length):
    """Remove a label prefix across inline nodes while preserving their markup."""
    if length <= 0:
        return 0
    if node.tag == "#text":
        decoded = html.unescape(node.data)
        removed = min(length, len(decoded))
        node.data = html.escape(decoded[removed:], quote=False)
        return length - removed
    for child in node.children:
        length = _remove_text_prefix(child, length)
        if length == 0:
            break
    return length


def _remove_text_suffix(node, length):
    """Remove a trailing ID across inline nodes without flattening its title."""
    if length <= 0:
        return 0
    if node.tag == "#text":
        decoded = html.unescape(node.data)
        removed = min(length, len(decoded))
        node.data = html.escape(decoded[:len(decoded) - removed], quote=False)
        return length - removed
    for child in reversed(node.children):
        length = _remove_text_suffix(child, length)
        if length == 0:
            break
    return length


def _literal_region(node, start, end, offset=0, protected=False):
    """Keep example IDs written in code literals out of caption metadata."""
    protected = protected or node.tag in {"code", "pre"}
    if node.tag == "#text":
        limit = offset + len(_text(node))
        return protected and start < limit and end > offset
    for child in node.children:
        if _literal_region(child, start, end, offset, protected):
            return True
        offset += len(_text(child))
    return False


def _extract_reference_id(caption, kind):
    if caption is None:
        return None
    text = _text(caption)
    match = re.search(r"\s*\{#([^{}]*)\}\s*$", text)
    if match is None or _literal_region(caption, match.start(), match.end()):
        return None
    identifier = match.group(1)
    # The inline Markdown parser marks active IDs. An escaped brace or code
    # literal can have exactly the same text, so plain text is never metadata.
    marker = None
    cursor = 0

    def visit(node):
        nonlocal marker, cursor
        if node.get("data-document-anchor") == identifier and cursor == text.index("{#", match.start()):
            marker = node
        if node.tag == "#text" or node.tag == "br":
            cursor += len(_text(node))
        else:
            for child in node.children:
                visit(child)

    visit(caption)
    if marker is None:
        return None
    prefix = "tbl:" if kind == "Tabla" else "fig:"
    if not REFERENCE_ID.fullmatch(identifier) or not identifier.startswith(prefix):
        raise ValueError(
            f"Identificador de {kind.lower()} no válido: {identifier!r} en {_reference_location(caption)}. "
            f"Usa {{#{prefix}nombre}} al final del rótulo."
        )
    _remove_text_suffix(caption, len(text) - match.start())
    marker.remove()
    return identifier


def _restore_reference_aliases(main):
    for node in list(_walk(main)):
        alias = node.get("data-document-reference-alias")
        if alias and node.get("id") == alias:
            node.attrs = [(key, value) for key, value in node.attrs
                          if key not in {"id", "data-document-reference-alias"}]
        if node.get("data-document-generated") == "reference-target":
            for child in list(node.children):
                _insert_before(node, child)
            node.remove()


def _reference_alias(target, identifier):
    """Anchor a stable ID on visible content, keeping the original target ID."""
    if not target.get("id"):
        target.set("id", identifier)
        target.set("data-document-reference-alias", identifier)
        return
    wrapper = _Node("span", [("id", identifier),
                              ("data-document-generated", "reference-target")])
    for child in list(target.children):
        wrapper.append(child)
    target.append(wrapper)


def _register_reference(node, caption, kind, used, references, record):
    declared = _extract_reference_id(caption, kind)
    stored = node.get("data-document-id")
    if declared and stored and declared != stored:
        raise ValueError(f"Identificadores de {kind.lower()} contradictorios: {stored} y {declared} "
                         f"en {_reference_location(caption or node)}.")
    identifier = declared or stored
    if identifier is None:
        return
    if identifier in references:
        raise ValueError(f"Identificador explícito duplicado: {identifier} ({kind} {record['number']}) "
                         f"en {_reference_location(caption or node)}.")
    if identifier in used:
        raise ValueError(f"El identificador explícito {identifier} ya existe en otro elemento del documento; "
                         f"declarado en {_reference_location(caption or node)}.")
    used.add(identifier)
    references[identifier] = record
    record["reference_id"] = identifier
    node.set("data-document-id", identifier)


def _reference_location(node):
    current = node
    while current is not None:
        line = current.get("data-source-line")
        if line:
            return f"línea {line}"
        if current.tag in {"p", "li", "caption", "figcaption"} | HEADING_TAGS:
            return f"bloque «{_label(current)[:100]}»"
        current = current.parent
    return "el documento"


def _resolve_references(main, references):
    for node in list(_walk(main)):
        identifier = node.get("data-document-reference")
        if identifier is None:
            continue
        current = node.parent
        while current is not None and current.tag not in {"code", "pre"}:
            current = current.parent
        if current is not None:
            continue
        record = references.get(identifier)
        if record is None:
            raise ValueError(f"Referencia sin destino: {identifier} en {_reference_location(node)}.")
        kind = "Tabla" if identifier.startswith("tbl:") else "Figura"
        node.tag = "a"
        node.set("href", f"#{identifier}")
        _classes(node, "document-reference")
        for child in list(node.children):
            child.remove()
        node.append(_literal(f"{kind} {record['number']}"))


def _marker_before(node, kind):
    previous = _previous_element(node)
    if previous is None or previous.tag != "p":
        return None
    match = re.match(rf"^\s*{kind}\s*:\s*", _text(previous), re.IGNORECASE)
    if match and _text(previous)[match.end():].strip():
        return previous, match.end()
    return None


def _metadata_table(table):
    if table.get("data-document-role") == "metadata":
        return True
    rows = [node for node in _walk(table) if node.tag == "tr"]
    if not rows:
        return False
    header = [_label(node).casefold() for node in rows[0].children if node.tag in {"th", "td"}]
    if header != ["dato", "valor"]:
        return False
    keys = {
        _label(next(node for node in row.children if node.tag in {"th", "td"})).casefold()
        for row in rows[1:] if any(node.tag in {"th", "td"} for node in row.children)
    }
    return len(keys & METADATA_KEYS) >= 2


def _subtitle(title, headings):
    """Recognize the ERS subtitle layout without discarding a normal first section."""
    explicit = next((node for node in headings if node.get("data-document-role") == "subtitle"), None)
    if explicit is not None:
        return explicit
    if title is None or title.parent is None:
        return None
    siblings = title.parent.children
    following = [node for node in siblings[siblings.index(title) + 1:] if not node.tag.startswith("#")]
    if not following or following[0].tag != "h2":
        return None
    candidate = following[0]
    if candidate.get("data-document-role") == "section":
        return None
    label = _label(candidate)
    if NUMBERED_SECTION.match(label) or label.casefold() in {
        "introducción", "resumen", "alcance", "propósito", "propósito y alcance",
        "objetivos", "requisitos", "contexto", "contenido", "índice",
    }:
        return None
    later = next((node for node in following[1:] if node.tag in HEADING_TAGS), None)
    if later is None or later.tag != "h2" or not NUMBERED_SECTION.match(_label(later)):
        return None
    between = following[1:following.index(later)]
    if any(_metadata_table(node) for block in between for node in _walk(block) if node.tag == "table"):
        return candidate
    return None


def _unique_id(base, used):
    candidate = base
    suffix = 1
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _reserve_ids(root):
    nodes = list(_walk(root))
    used = {node.get("id") for node in nodes if node.get("id")}
    seen = set()
    for node in nodes:
        identifier = node.get("id")
        if not identifier:
            continue
        if identifier in seen:
            node.set("id", _unique_id(identifier, used))
        else:
            seen.add(identifier)
    return used


def _ensure_id(node, base, used):
    if not node.get("id"):
        node.set("id", _unique_id(base, used))
    return node.get("id")


def _caption(node, tag, kind, number, title, marker=None, title_content=None):
    existing = next((child for child in node.children if child.tag == tag), None)
    if existing is not None:
        generated = existing.get("data-document-caption")
        if generated:
            prefix = re.match(rf"^\s*{kind}\s+\d+\.\s*", _text(existing))
            if prefix:
                _remove_text_prefix(existing, prefix.end())
        content = list(existing.children)
        existing.remove()
    elif marker is not None:
        previous, prefix_length = marker
        _remove_text_prefix(previous, prefix_length)
        content = list(previous.children)
        previous.remove()
    else:
        content = list(title_content) if title_content is not None else [_literal(title)]
    caption = _Node(tag, [("data-document-caption", kind.casefold())])
    _classes(caption, "document-figure-caption" if kind == "Figura" else "document-table-caption")
    caption.append(_literal(f"{kind} {number}. "))
    for child in content:
        caption.append(child)
    if tag == "caption":
        caption.parent = node
        node.children.insert(0, caption)
    else:
        node.append(caption)
    return caption


def _existing_caption_title(node, tag, kind):
    existing = next((child for child in node.children if child.tag == tag), None)
    if existing is None:
        return None
    title = _label(existing)
    if existing.get("data-document-caption"):
        title = re.sub(rf"^\s*{kind}\s+\d+\.\s*", "", title)
    return title or None


def _figure_context(image, main):
    current = image.parent
    while current is not None and current is not main:
        if current.tag == "figure" or current.get("data-document-figure"):
            return current
        if current.tag == "p":
            return current
        current = current.parent
    return image


def _is_body_image(image, main):
    current = image
    while current is not None and current is not main:
        if current.get("data-document-role") == "cover-logo":
            return False
        if current.tag in {"header", "footer", "nav"} | HEADING_TAGS:
            return False
        classes = set((current.get("class") or "").casefold().split())
        if classes & {"logo", "brand-logo", "branding", "document-logo"}:
            return False
        current = current.parent
    return True


def _wrap_figure(image, context):
    if context.tag == "figure" or context.get("data-document-figure"):
        return context, "figcaption" if context.tag == "figure" else "span"
    images = [node for node in _walk(context) if node.tag == "img"]
    if context.tag == "p" and len(images) == 1 and not _label(context):
        context.tag = "figure"
        _classes(context, "document-figure")
        context.set("data-document-figure", "block")
        return context, "figcaption"
    standalone = image.parent.tag in {"main", "article", "section", "div", "blockquote", "body"}
    wrapper = _Node("figure" if standalone else "span", [
        ("class", "document-figure" if standalone else "document-figure-inline"),
        ("data-document-figure", "block" if standalone else "inline"),
    ])
    if not standalone:
        wrapper.set("role", "figure")
    _insert_before(image, wrapper)
    wrapper.append(image)
    return wrapper, "figcaption" if standalone else "span"


def _toc(entries, identifier, title="Índice", kind="toc"):
    nav = _Node("nav", [("id", identifier), ("class", "document-toc"),
                        ("aria-label", title), ("data-document-generated", kind)])
    if kind != "toc":
        _classes(nav, f"document-{kind}")
    heading = _Node("h2")
    heading.append(_literal(title))
    nav.append(heading)
    listing = _Node("ol", [("class", "document-toc-list")])
    nav.append(listing)
    for entry in entries:
        item = _Node("li", [("class", "document-toc-item"), ("data-toc-level", str(entry["toc_level"]))])
        link = _Node("a", [("href", f'#{entry["id"]}')])
        label = _Node("span", [("class", "document-toc-label")])
        if "title_html" in entry:
            fragment = _DocumentParser()
            fragment.feed(entry["title_html"])
            fragment.close()
            for child in list(fragment.root.children):
                label.append(child)
        else:
            label.append(_literal(entry["title"]))
        leader = _Node("span", [("class", "document-toc-leader"), ("aria-hidden", "true")])
        page = _Node("span", [("class", "document-toc-page"), ("data-toc-target", entry["id"])])
        page.append(_literal("…"))
        link.append(label)
        link.append(leader)
        link.append(page)
        item.append(link)
        listing.append(item)
    return nav


def prepare_document(html_document, with_toc=True, with_captions=True, toc_depth=2,
                     with_table_index=False, with_figure_index=False):
    """Return enriched HTML and heading/table/figure registries.

    ``toc_depth`` counts levels relative to the highest section heading, excluding
    the document title and a conservatively recognized subtitle. The registry
    retains actual HTML heading levels as ``level`` and adds ``toc_level``.
    """
    if not isinstance(toc_depth, int) or isinstance(toc_depth, bool) or not 1 <= toc_depth <= 6:
        raise ValueError("toc_depth must be an integer between 1 and 6")
    parser = _DocumentParser()
    parser.feed(html_document)
    parser.close()
    root = parser.root
    main = next((node for node in _walk(root) if node.tag == "main"), None)
    if main is None:
        main = next((node for node in _walk(root) if node.tag == "body"), root)
    for node in list(_walk(main)):
        if node.get("data-document-generated") in GENERATED_NAVIGATION:
            node.remove()
    _restore_reference_aliases(main)
    used = _reserve_ids(root)
    nodes = list(_walk(main))
    headings = [node for node in nodes if node.tag in HEADING_TAGS and node.get("data-document-role") != "note-content"]
    title = next((node for node in headings if node.get("data-document-role") == "title"), None)
    if title is None:
        title = next((node for node in headings if node.tag == "h1" and node.get("data-document-role") != "section"), None)
    subtitle = _subtitle(title, headings)
    records = []
    heading_records = {}
    for index, heading in enumerate(headings, 1):
        role = "title" if heading is title else "subtitle" if heading is subtitle else "section"
        record = {"id": _ensure_id(heading, f"section-{index}", used),
                  "title": _label(heading), "level": int(heading.tag[1]), "role": role}
        records.append(record)
        heading_records[id(heading)] = record
    sections = [record for record in records if record["role"] == "section"]
    base_level = min((record["level"] for record in sections), default=1)
    for record in sections:
        record["toc_level"] = record["level"] - base_level + 1
    entries = [dict(record) for record in sections if record["toc_level"] <= toc_depth]
    structure = {"entries": entries, "headings": records, "tables": [], "figures": [],
                 "toc_id": None, "table_index_id": None, "figure_index_id": None,
                 "navigation_entries": []}
    references = {}
    caption_sources = []
    nearest_section = None
    for node in nodes:
        if node.tag in HEADING_TAGS and id(node) in heading_records:
            record = heading_records[id(node)]
            if record["role"] == "section":
                nearest_section = node
        elif node.tag == "table":
            number = len(structure["tables"]) + 1
            identifier = _ensure_id(node, f"table-{number}", used)
            marker = _marker_before(node, "Tabla")
            caption_source = next((child for child in node.children if child.tag == "caption"), None)
            if caption_source is None and marker:
                caption_source = marker[0]
            record = {"id": identifier, "number": number}
            _register_reference(node, caption_source, "Tabla", used, references, record)
            existing_title = _existing_caption_title(node, "caption", "Tabla")
            inferred = None
            if existing_title:
                caption_title = existing_title
            elif marker:
                caption_title = re.sub(r"\s+", " ", _text(marker[0])[marker[1]:]).strip()
            elif number == 1 and _metadata_table(node):
                caption_title = "Datos del documento"
            elif nearest_section:
                inferred = _label_fragment(
                    nearest_section, r"^(?:\d+(?:\.\d+)+[.)]?|\d+[.)])\s+",
                    keep_references=True,
                )
                caption_title = _label(inferred)
            else:
                headers = [child for child in _walk(node) if child.tag == "th"]
                inferred = _Node("span")
                for index, header in enumerate(headers):
                    if index:
                        inferred.append(_literal(" / "))
                    for child in _label_content(header, keep_references=True):
                        inferred.append(child)
                caption_title = _label(inferred) or "Contenido tabular"
                if not _label(inferred):
                    inferred.append(_literal(caption_title))
            if with_captions:
                caption_source = _caption(node, "caption", "Tabla", number, caption_title, marker,
                                          inferred.children if inferred is not None else None)
            record.update({"title": caption_title, "caption": f"Tabla {number}. {caption_title}"})
            structure["tables"].append(record)
            prefix = r"^\s*Tabla\s+\d+\.\s*" if with_captions else r"^\s*Tabla\s*:\s*"
            if caption_source is None and inferred is not None:
                caption_source, prefix = inferred, None
            caption_sources.append((record, caption_source, "Tabla", prefix))
            if record.get("reference_id"):
                target = caption_source if with_captions else next(
                    (child for child in _walk(node) if child.tag in {"th", "td"}), None)
                if target is None:
                    raise ValueError(f"La tabla {record['reference_id']} necesita una celda o rótulo para su destino.")
                _reference_alias(target, record["reference_id"])
        elif node.tag == "img" and _is_body_image(node, main):
            number = len(structure["figures"]) + 1
            identifier = _ensure_id(node, f"figure-{number}", used)
            context = _figure_context(node, main)
            marker = _marker_before(context, "Figura")
            caption_tag = "figcaption" if context.tag == "figure" else "span"
            caption_source = next((child for child in context.children
                                   if child.tag == caption_tag and child.get("data-document-caption")), None)
            if caption_source is None and context.tag == "figure":
                caption_source = next((child for child in context.children if child.tag == "figcaption"), None)
            if caption_source is None and marker:
                caption_source = marker[0]
            record = {"id": identifier, "number": number, "src": node.get("src", "")}
            _register_reference(node, caption_source, "Figura", used, references, record)
            existing_title = _existing_caption_title(context, caption_tag, "Figura") if context.get("data-document-figure") or context.tag == "figure" else None
            if existing_title:
                caption_title = existing_title
            elif marker:
                caption_title = re.sub(r"\s+", " ", _text(marker[0])[marker[1]:]).strip()
            else:
                caption_title = node.get("title") or node.get("alt") or "Imagen del documento"
            if with_captions:
                figure, caption_tag = _wrap_figure(node, context)
                caption_source = _caption(figure, caption_tag, "Figura", number, caption_title, marker)
            record.update({"title": caption_title, "caption": f"Figura {number}. {caption_title}"})
            structure["figures"].append(record)
            prefix = r"^\s*Figura\s+\d+\.\s*" if with_captions else r"^\s*Figura\s*:\s*"
            caption_sources.append((record, caption_source, "Figura", prefix))
            if record.get("reference_id"):
                if with_captions:
                    _reference_alias(figure, record["reference_id"])
                else:
                    # A small inline wrapper puts the alias exactly on the image
                    # without manufacturing a visible caption or block figure.
                    wrapper = _Node("span", [("id", record["reference_id"]),
                                              ("data-document-generated", "reference-target")])
                    _insert_before(node, wrapper)
                    wrapper.append(node)
    _resolve_references(main, references)
    for heading in headings:
        heading_records[id(heading)]["title"] = _label(heading)
        heading_records[id(heading)]["title_html"] = _inline_html(_label_fragment(heading))
    entries = [dict(record) for record in sections if record["toc_level"] <= toc_depth]
    structure["entries"] = entries
    for record, caption_source, kind, prefix in caption_sources:
        if caption_source is not None:
            # Sources kept off the DOM for --no-captions need the same final
            # reference numbers as visible captions and section headings.
            _resolve_references(caption_source, references)
            caption_title = _label(caption_source)
            if prefix:
                caption_title = re.sub(prefix, "", caption_title)
            record["title"] = caption_title
            record["caption"] = f"{kind} {record['number']}. {caption_title}"
            record["title_html"] = _inline_html(_label_fragment(caption_source, prefix))
        else:
            record["title_html"] = html.escape(record["title"], quote=False)
        record["caption_html"] = f"{kind} {record['number']}. " + record["title_html"]
    indices = []
    if with_toc and entries:
        indices.append(("toc", "Índice", entries))
    for kind, label, rows, enabled in (
            ("table-index", "Índice de tablas", structure["tables"], with_table_index),
            ("figure-index", "Índice de figuras", structure["figures"], with_figure_index)):
        if enabled and rows:
            indices.append((kind, label, [{**record, "title": record["caption"],
                                          "title_html": record["caption_html"], "toc_level": 1,
                                          "kind": kind.removesuffix("-index")} for record in rows]))
    if indices:
        cover = next((node for node in main.children
                      if node.get("data-document-role") == "cover"), None)
        insertion = None
        if cover is not None:
            position = main.children.index(cover) + 1
        elif sections:
            first_section = next(node for node in headings if heading_records[id(node)]["role"] == "section")
            insertion = first_section
            while insertion.parent is not main:
                insertion = insertion.parent
            position = main.children.index(insertion)
        else:
            # With no section headings, keep introductory document metadata
            # together and place lists before the first real body element.
            introductory = {id(node) for node in (title, subtitle) if node is not None}
            metadata = [node for node in main.children if node.get("data-document-role") == "metadata"
                        or (node.tag == "table" and _metadata_table(node))]
            introductory.update(id(node) for node in metadata)
            position = 0
            for index, child in enumerate(main.children):
                if id(child) in introductory:
                    position = index + 1
        for kind, label, rows in indices:
            identifier = _unique_id(f"document-{kind}", used)
            nav = _toc(rows, identifier, label, kind)
            nav.parent = main
            main.children.insert(position, nav)
            position += 1
            structure[{"toc": "toc_id", "table-index": "table_index_id",
                       "figure-index": "figure_index_id"}[kind]] = identifier
            structure["navigation_entries"].extend(rows)
    return _serialize(root), structure
