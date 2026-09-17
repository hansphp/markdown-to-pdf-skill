"""Numbered Markdown notes with explicit document-end placement and backlinks.

The parser preserves source line numbers and never edits the Markdown file.
Chromium does not lay these notes out at each page's bottom: the HTML explicitly
uses a ``doc-endnotes`` section, matching the documented Markdown convention.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


IDENTIFIER = r"[^\s\[\]]+"
DEFINITION_RE = re.compile(r"^ {0,3}\[\^(" + IDENTIFIER + r")\]:[ \t]*(.*)$")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})\s*([^\s`]*)\s*$")
LIST_RE = re.compile(r"^\s*([-+*]|\d+[.)])\s+(.+)$")


def _starts_block(lines: list[str], index: int) -> bool:
    """Recognize the boundaries used for lazy list continuations by the renderer."""
    line = lines[index]
    compact = re.sub(r"\s", "", line)
    return bool(
        not line.strip()
        or FENCE_RE.match(line)
        or LIST_RE.match(line)
        or re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        or re.match(r"^\s*>\s?(.*)$", line)
        or re.match(r"^\s*<!--\s*pagebreak\s*-->\s*$", line, re.IGNORECASE)
        or line.strip().startswith(("$$", r"\["))
        or (len(compact) >= 3 and len(set(compact)) == 1 and compact[0] in "-*_")
        or (index + 1 < len(lines) and "|" in line and re.fullmatch(
            r"\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*", lines[index + 1]
        ))
    )


def _list_item(lines: list[str], index: int, match: re.Match) -> tuple[list[str], int]:
    """Expose one list item's Markdown using the same indentation as render_blocks.

    A nested fence belongs only to this item. In particular, an unclosed fence
    cannot protect a real definition in a later item or outside the list.
    """
    content_indent = match.start(2)
    content = [match.group(2)]
    index += 1
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            following = index + 1
            while following < len(lines) and not lines[following].strip():
                following += 1
            next_indent = len(lines[following]) - len(lines[following].lstrip()) if following < len(lines) else -1
            if next_indent < content_indent:
                break
            content.append("")
        elif len(line) - len(line.lstrip()) >= content_indent:
            content.append(line[content_indent:])
        elif not _starts_block(lines, index):
            content.append(line.lstrip())
        else:
            break
        index += 1
    task = re.match(r"^\[([ xX])\]\s+(.*)$", content[0])
    if task:
        content[0] = task.group(2)
    return content, index


class FootnoteError(ValueError):
    """A source-level note error that must not produce a partial document."""


@dataclass(frozen=True)
class FootnoteDefinition:
    identifier: str
    lines: list[str]
    line_numbers: list[int]
    source_line: int


def _protected_lines(lines: list[str]) -> set[int]:
    """Find literal code before interpreting line-start note definitions."""
    protected = set()
    index = 0
    while index < len(lines):
        fence = FENCE_RE.match(lines[index])
        if fence:
            marker = fence.group(1)
            closing = re.compile(r"^\s*" + re.escape(marker[0]) + r"{" + str(len(marker)) + r",}\s*$")
            protected.add(index)
            index += 1
            while index < len(lines):
                protected.add(index)
                if closing.match(lines[index]):
                    index += 1
                    break
                index += 1
            continue
        item = LIST_RE.match(lines[index])
        if item:
            item_lines, end = _list_item(lines, index, item)
            protected.update(index + offset for offset in _protected_lines(item_lines))
            index = end
            continue
        # Inline spans can continue only within the same rendered paragraph.
        # Headings and other block starts have their own inline scope, even
        # when their first line already contains an unmatched opening run.
        end = index + 1
        if not _starts_block(lines, index):
            while end < len(lines) and not _starts_block(lines, end):
                end += 1
        source = "\n".join(lines[index:end])
        cursor = 0
        while cursor < len(source):
            if source[cursor] == "\\":
                cursor += 2
                continue
            if source[cursor] != "`":
                cursor += 1
                continue
            run = re.match(r"`+", source[cursor:]).group(0)
            close = re.search(r"(?<!`)`{" + str(len(run)) + r"}(?!`)", source[cursor + len(run):])
            if close is None:
                cursor += len(run)
                continue
            finish = cursor + len(run) + close.end()
            first_line = index + source[:cursor].count("\n")
            last_line = index + source[:finish].count("\n")
            # A definition on the first line starts before its own inline code;
            # only later lines are inside the literal span at column zero.
            protected.update(range(first_line + 1, last_line + 1))
            cursor = finish
        index = end
    return protected


def _continuation(line: str) -> str | None:
    if line.startswith("\t"):
        return line[1:]
    if line.startswith("    "):
        return line[4:]
    return None


def extract_definitions(
    lines: list[str], line_numbers: list[int] | None = None,
) -> tuple[list[str], dict[str, FootnoteDefinition]]:
    """Extract ``[^id]:`` definitions while keeping blank source placeholders.

    Continuations require a tab or four spaces. Empty lines are included when
    followed by an indented continuation, so paragraphs, lists and code fences
    remain separate Markdown blocks. Definition labels are case sensitive and
    cannot contain whitespace or brackets.
    """
    numbers = list(range(1, len(lines) + 1)) if line_numbers is None else line_numbers
    if len(numbers) != len(lines):
        raise ValueError("Cada línea de Markdown debe tener su número de origen.")
    body = list(lines)
    definitions = {}
    protected = _protected_lines(lines)
    index = 0
    while index < len(lines):
        match = DEFINITION_RE.match(lines[index]) if index not in protected else None
        if match is None:
            index += 1
            continue
        identifier = match.group(1)
        source_line = numbers[index]
        if identifier in definitions:
            previous = definitions[identifier].source_line
            raise FootnoteError(
                f"Nota [^{identifier}] duplicada en línea {source_line}; "
                f"la primera definición está en línea {previous}."
            )
        note_lines = [match.group(2)]
        note_numbers = [source_line]
        body[index] = ""
        index += 1
        while index < len(lines):
            continuation = _continuation(lines[index])
            if continuation is not None:
                note_lines.append(continuation)
                note_numbers.append(numbers[index])
                body[index] = ""
                index += 1
                continue
            if not lines[index].strip():
                next_content = index + 1
                while next_content < len(lines) and not lines[next_content].strip():
                    next_content += 1
                if next_content < len(lines) and _continuation(lines[next_content]) is not None:
                    while index < next_content:
                        note_lines.append("")
                        note_numbers.append(numbers[index])
                        body[index] = ""
                        index += 1
                    continue
            break
        if not any(line.strip() for line in note_lines):
            raise FootnoteError(f"Nota [^{identifier}] vacía en línea {source_line}.")
        definitions[identifier] = FootnoteDefinition(identifier, note_lines, note_numbers, source_line)
    return body, definitions


def apply_footnotes(html_document: str, definitions: dict[str, FootnoteDefinition], render_blocks,
                    structure_module) -> str:
    """Resolve inline markers and append a numbered section with backlinks.

    ``render_blocks`` accepts ``(lines, line_numbers=...)``. Inline references
    arrive as elements with ``data-document-footnote=id`` and an optional
    ``data-source-line``. Missing, unused or nested notes fail explicitly so no
    source content disappears silently.
    """
    structure = structure_module
    parser = structure._DocumentParser()
    parser.feed(html_document)
    parser.close()
    root = parser.root
    nodes = list(structure._walk(root))
    if any(node.get("data-document-role") == "footnotes" for node in nodes):
        return html_document
    references = [node for node in nodes if node.get("data-document-footnote") is not None]
    if not definitions and not references:
        return html_document
    used = set()
    ordered = []
    for node in references:
        identifier = node.get("data-document-footnote")
        if identifier not in definitions:
            line = node.get("data-source-line")
            location = f" en línea {line}" if line else ""
            raise FootnoteError(f"La referencia [^{identifier}]{location} no tiene definición.")
        if identifier not in used:
            used.add(identifier)
            ordered.append(identifier)
    unused = [definition for identifier, definition in definitions.items() if identifier not in used]
    if unused:
        details = "; ".join(f"[^{note.identifier}] en línea {note.source_line}" for note in unused)
        raise FootnoteError("Notas sin referencia: " + details + ". Añade una referencia o elimina la definición.")
    main = next((node for node in nodes if node.tag == "main"), None)
    if main is None:
        raise FootnoteError("No se encontró el cuerpo principal para insertar las notas.")
    occupied = {node.get("id") for node in nodes if node.get("id")}

    def unique(candidate):
        result = candidate
        suffix = 1
        while result in occupied:
            result = f"{candidate}-{suffix}"
            suffix += 1
        occupied.add(result)
        return result

    fragments = {}
    for identifier in ordered:
        definition = definitions[identifier]
        rendered = render_blocks(definition.lines, line_numbers=definition.line_numbers)
        fragment = structure._DocumentParser()
        fragment.feed(rendered)
        fragment.close()
        for node in structure._walk(fragment.root):
            if node.get("data-document-footnote") is not None:
                line = node.get("data-source-line") or definition.source_line
                raise FootnoteError(
                    f"Nota [^{identifier}] en línea {line}: no se admiten referencias a notas dentro de otra nota."
                )
            if node.get("id"):
                occupied.add(node.get("id"))
            if node.tag in structure.HEADING_TAGS:
                node.set("data-document-role", "note-content")
        fragments[identifier] = fragment.root
    section = structure._Node("section", [("class", "document-footnotes"),
                                         ("data-document-role", "footnotes"), ("role", "doc-endnotes")])
    heading = structure._Node("h2", [("id", unique("document-notes")), ("data-document-role", "section")])
    heading.append(structure._literal("Notas"))
    section.set("aria-labelledby", heading.get("id"))
    section.append(heading)
    listing = structure._Node("ol", [("class", "document-footnotes-list")])
    section.append(listing)
    records = {}
    for number, identifier in enumerate(ordered, 1):
        definition = definitions[identifier]
        item = structure._Node("li", [("id", unique(f"document-note-{number}")),
                                      ("data-source-line", str(definition.source_line)),
                                      ("data-footnote-number", str(number))])
        for child in list(fragments[identifier].children):
            item.append(child)
        listing.append(item)
        records[identifier] = {"number": number, "item": item, "backlinks": []}
    for node in references:
        identifier = node.get("data-document-footnote")
        record = records[identifier]
        number = record["number"]
        occurrence = len(record["backlinks"]) + 1
        reference_id = unique(f"document-note-ref-{number}-{occurrence}")
        # Preserve a user-provided sup ID (if any) and place our destination on
        # the generated link. All generated IDs remain ASCII and collision free.
        node.attrs = [(key, value) for key, value in node.attrs if key != "data-document-footnote"]
        structure._classes(node, "document-footnote-reference")
        for child in node.children:
            child.parent = None
        node.children = []
        anchor = structure._Node("a", [("id", reference_id),
                                      ("href", "#" + record["item"].get("id")),
                                      ("role", "doc-noteref"),
                                      ("aria-label", f"Nota {number}")])
        anchor.append(structure._literal(str(number)))
        node.append(anchor)
        record["backlinks"].append(reference_id)
    for record in records.values():
        backlinks = structure._Node("p", [("class", "document-footnote-backlinks")])
        for occurrence, identifier in enumerate(record["backlinks"], 1):
            if occurrence > 1:
                backlinks.append(structure._literal(" "))
            anchor = structure._Node("a", [("href", "#" + identifier), ("role", "doc-backlink"),
                                          ("aria-label", f"Volver a la referencia {occurrence} de la nota {record['number']}")])
            label = "↩" if len(record["backlinks"]) == 1 else f"↩{occurrence}"
            anchor.append(structure._literal(label))
            backlinks.append(anchor)
        record["item"].append(backlinks)
    main.append(section)
    return structure._serialize(root)
