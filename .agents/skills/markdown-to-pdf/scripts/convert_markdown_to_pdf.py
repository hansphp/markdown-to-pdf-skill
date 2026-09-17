#!/usr/bin/env python3
"""Convert a practical Markdown subset to PDF without installing dependencies."""

from __future__ import annotations

import argparse
import base64
import html
import importlib.util
import os
import re
import shutil
import string
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit


SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSS = SKILL_DIR / "assets" / "print.css"
DEFAULT_LOGO = SKILL_DIR / "assets" / "logo.png"
SUPPORTED_INPUTS = {".md", ".markdown", ".mdown"}
PAPER_SIZES = ("A4", "Letter", "Legal")

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})\s*([^\s`]*)\s*$")
LIST_RE = re.compile(r"^\s*([-+*]|\d+[.)])\s+(.+)$")
QUOTE_RE = re.compile(r"^\s*>\s?(.*)$")
SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")
PAGEBREAK_RE = re.compile(r"^\s*<!--\s*pagebreak\s*-->\s*$", re.IGNORECASE)
INLINE_TEXT_RE = re.compile(r"[^\\`$\[{!*_~\n ]+")
FOOTNOTE_ID = r"[^\s\[\]]+"
MERMAID_PLACEHOLDER = "data:image/svg+xml;base64," + base64.b64encode(
    b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'
).decode("ascii")


class ConversionError(RuntimeError):
    """Raised for a user-actionable conversion failure."""


class DocumentValidationError(ConversionError):
    """A document problem must not be bypassed by falling back to another engine."""


def check_diagnostics(diagnostics, *, strict=False) -> None:
    blocking = [item for item in diagnostics if item.severity == "error" or strict]
    if blocking:
        validation = load_support_module("document_validation")
        raise DocumentValidationError("La validación impide exportar el documento:\n" +
                                      "\n".join(validation.format_diagnostic(item) for item in blocking))


def normalize_document_links(document: str, source: Path) -> str:
    """Same-Markdown file links become PDF-local fragments at export time."""
    structure = load_support_module("document_structure")
    parser = structure._DocumentParser()
    parser.feed(document)
    parser.close()
    base = source.parent.resolve().as_uri() + "/"
    for node in structure._walk(parser.root):
        if node.tag != "a" or not node.get("href"):
            continue
        href = node.get("href")
        parts = urlsplit(urljoin(base, href))
        if parts.fragment and parts.scheme == "file" and parts.netloc in {"", "localhost"}:
            if Path(unquote(parts.path)).resolve() == source.resolve():
                node.set("href", "#" + parts.fragment)
    return structure._serialize(parser.root)


def safe_url(value: str, image: bool = False) -> str:
    value = value.strip().strip("<>").replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", value):
        try:
            return Path(value).resolve().as_uri()
        except ValueError:
            return "#"

    scheme = urlsplit(value).scheme.lower()
    allowed = {"", "http", "https", "file"}
    if not image:
        allowed.update({"mailto", "tel"})
    if image and scheme == "data" and value.lower().startswith("data:image/"):
        return value
    return value if scheme in allowed else "#"


def _code_span(source: str, start: int) -> tuple[str, int] | None:
    run = re.match(r"`+", source[start:])
    if not run:
        return None
    width = len(run.group(0))
    closing = re.search(rf"(?<!`)`{{{width}}}(?!`)", source[start + width :])
    if not closing:
        return None
    end = start + width + closing.start()
    content = source[start + width : end].replace("\n", " ")
    if content.startswith(" ") and content.endswith(" ") and content.strip(" "):
        content = content[1:-1]
    return content, end + width


def _unescape_punctuation(source: str) -> str:
    return re.sub(r"\\([" + re.escape(string.punctuation) + r"])", r"\1", source)


def _link_target(source: str, start: int) -> tuple[str, str | None, int] | None:
    """Read an inline destination, balanced parentheses and an optional title."""
    index = start + 1
    while index < len(source) and source[index].isspace():
        index += 1
    url_chars: list[str] = []
    if index < len(source) and source[index] == "<":
        index += 1
        while index < len(source) and source[index] != ">":
            if source[index] == "\n":
                return None
            if source[index] == "\\" and index + 1 < len(source):
                url_chars.append(source[index : index + 2])
                index += 2
            else:
                url_chars.append(source[index])
                index += 1
        if index == len(source):
            return None
        index += 1
    else:
        depth = 0
        while index < len(source):
            char = source[index]
            if char == "\\" and index + 1 < len(source):
                url_chars.append(source[index : index + 2])
                index += 2
                continue
            if char.isspace():
                break
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            url_chars.append(char)
            index += 1
        if depth:
            return None
    url = _unescape_punctuation("".join(url_chars))
    whitespace_start = index
    while index < len(source) and source[index].isspace():
        index += 1
    if index < len(source) and source[index] == ")":
        return url, None, index + 1
    if index == whitespace_start or index >= len(source) or source[index] not in "\"'(":
        return None
    quote = ")" if source[index] == "(" else source[index]
    index += 1
    title_chars: list[str] = []
    while index < len(source) and source[index] != quote:
        if source[index] == "\\" and index + 1 < len(source):
            title_chars.append(source[index : index + 2])
            index += 2
        else:
            title_chars.append(source[index])
            index += 1
    if index == len(source):
        return None
    index += 1
    while index < len(source) and source[index].isspace():
        index += 1
    if index < len(source) and source[index] == ")":
        return url, _unescape_punctuation("".join(title_chars)), index + 1
    return None


def _closing_bracket(source: str, start: int) -> int | None:
    depth = 1
    index = start + 1
    while index < len(source):
        char = source[index]
        formula = inline_math(source, index, strict=False) if char in {"$", "\\"} else None
        if formula:
            index = formula[1]
            continue
        if char == "\\":
            index += 2
            continue
        if char == "`":
            code = _code_span(source, index)
            if code:
                index = code[1]
                continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _closing_emphasis(source: str, start: int, marker: str) -> int | None:
    index = start + len(marker)
    while index < len(source):
        formula = inline_math(source, index, strict=False) if source[index] in {"$", "\\"} else None
        if formula:
            index = formula[1]
            continue
        if source[index] == "\\":
            index += 2
            continue
        if source[index] == "`":
            code = _code_span(source, index)
            if code:
                index = code[1]
                continue
        if source.startswith(marker, index) and not source[index - 1].isspace():
            end = index + len(marker)
            if marker[0] != "_" or end == len(source) or not source[end].isalnum():
                # A third star may close an inner emphasis before the strong span.
                if marker == "**" and source.startswith("***", index):
                    return index + 1
                return index
        index += 1
    return None


def inline_math(source: str, start: int, source_line: int | None = None, *, strict=True):
    """Recognize math without interpreting escaped delimiters or ordinary prices."""
    explicit = source.startswith(r"\(", start)
    if not explicit and (source[start:start + 1] != "$" or source.startswith("$$", start)):
        return None
    opening, closing = (r"\(", r"\)") if explicit else ("$", "$")
    after = start + len(opening)
    if not explicit and (after == len(source) or source[after].isspace()):
        return None
    position = after
    while position < len(source) and source[position] != "\n":
        if source.startswith(closing, position):
            end = position + len(closing)
            valid = explicit or (not source[position - 1].isspace()
                                 and source[end:end + 1] != "$"
                                 and not source[end:end + 1].isdigit())
            if valid and source[after:position].strip():
                return source[after:position], end
        if source[position] == "\\":
            position += 2
        else:
            position += 1
    if explicit and strict:
        location = f" en la línea {source_line}" if source_line is not None else ""
        raise ConversionError(f"Fórmula matemática{location}: falta el cierre \\) en la misma línea.")
    return None


def render_inline(source: str, allow_links: bool = True, depth: int = 0, source_line: int | None = None) -> str:
    """Render the supported inline subset without user-visible token placeholders."""
    if depth > 32:
        return html.escape(source, quote=False)
    output: list[str] = []
    index = 0
    while index < len(source):
        char = source[index]
        current_line = source_line + source[:index].count("\n") if source_line is not None else None
        location = f' data-source-line="{current_line}"' if current_line is not None else ""
        formula = inline_math(source, index, current_line) if char in {"$", "\\"} else None
        if formula:
            tex, index = formula
            output.append(f'<span data-document-math="inline"{location}>{html.escape(tex, quote=False)}</span>')
            continue
        if source.startswith("$$", index):
            output.append("$$")
            index += 2
            continue
        if char == "\\" and index + 1 < len(source):
            following = source[index + 1]
            if following == "\n" or following in string.punctuation:
                output.append("<br>\n" if following == "\n" else html.escape(following, quote=False))
                index += 2
                continue
        hardbreak = re.match(r" {2,}\n", source[index:]) if char == " " else None
        if hardbreak:
            output.append("<br>\n")
            index += len(hardbreak.group(0))
            continue
        if char == "`":
            code = _code_span(source, index)
            if code:
                output.append(f"<code>{html.escape(code[0], quote=False)}</code>")
                index = code[1]
                continue
            run = re.match(r"`+", source[index:]).group(0)
            output.append(run)
            index += len(run)
            continue
        footnote = re.match(rf"\[\^({FOOTNOTE_ID})\]", source[index:]) if allow_links and char == "[" else None
        if footnote and source[index + len(footnote.group(0)):index + len(footnote.group(0)) + 1] != "(":
            identifier = html.escape(footnote.group(1), quote=True)
            output.append(f'<sup data-document-footnote="{identifier}"{location}>{html.escape(footnote.group(0), quote=False)}</sup>')
            index += len(footnote.group(0))
            continue
        reference = re.match(r"\[@((?:tbl|fig):[A-Za-z0-9][A-Za-z0-9_.:-]*)\]", source[index:]) if allow_links and char == "[" else None
        if reference and source[index + len(reference.group(0)):index + len(reference.group(0)) + 1] != "(":
            identifier = reference.group(1)
            output.append(f'<span data-document-reference="{identifier}"{location}>{reference.group(0)}</span>')
            index += len(reference.group(0))
            continue
        anchor = re.match(r"\{#((?:tbl|fig):[A-Za-z0-9][A-Za-z0-9_.:-]*)\}", source[index:]) if allow_links and char == "{" else None
        if anchor:
            output.append(f'<span data-document-anchor="{anchor.group(1)}"{location}>{anchor.group(0)}</span>')
            index += len(anchor.group(0))
            continue
        is_image = source.startswith("![", index)
        if allow_links and (char == "[" or is_image):
            bracket = index + 1 if is_image else index
            closing = _closing_bracket(source, bracket)
            if closing is not None and source[closing + 1 : closing + 2] == "(":
                target = _link_target(source, closing + 1)
                if target:
                    url, title, end = target
                    label = render_inline(source[bracket + 1 : closing], False, depth + 1, current_line)
                    title_attr = f' title="{html.escape(title, quote=True)}"' if title else ""
                    destination = html.escape(safe_url(url, image=is_image), quote=True)
                    if is_image:
                        alt = html.escape(html.unescape(re.sub(r"<[^>]*>", "", label)), quote=True)
                        output.append(f'<img src="{destination}" alt="{alt}"{title_attr}{location}>')
                    else:
                        output.append(f'<a href="{destination}"{title_attr}{location}>{label}</a>')
                    index = end
                    continue
        plain = INLINE_TEXT_RE.match(source, index)
        if plain:
            output.append(html.escape(plain.group(0), quote=False))
            index = plain.end()
            continue
        matched = False
        for marker, opening, closing in (
            ("***", "<strong><em>", "</em></strong>"),
            ("**", "<strong>", "</strong>"),
            ("__", "<strong>", "</strong>"),
            ("~~", "<del>", "</del>"),
            ("*", "<em>", "</em>"),
            ("_", "<em>", "</em>"),
        ):
            after = index + len(marker)
            if not source.startswith(marker, index) or after >= len(source) or source[after].isspace():
                continue
            if marker[0] == "_" and index and source[index - 1].isalnum():
                continue
            end = _closing_emphasis(source, index, marker)
            if end is not None and end > after:
                output.append(opening + render_inline(source[after:end], allow_links, depth + 1, current_line) + closing)
                index = end + len(marker)
                matched = True
                break
        if matched:
            continue
        output.append(" " if char == "\n" else html.escape(char, quote=False))
        index += 1
    return "".join(output)


def split_table_row(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        preceding = len(text[:-1]) - len(text[:-1].rstrip("\\"))
        if preceding % 2 == 0:
            text = text[:-1]

    cells: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        formula = inline_math(text, index, strict=False) if char in {"$", "\\"} else None
        if formula:
            current.append(text[index:formula[1]])
            index = formula[1]
            continue
        if char == "\\" and index + 1 < len(text) and text[index + 1] in "\\|":
            following = text[index + 1]
            current.append("|" if following == "|" else "\\\\")
            index += 2
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    cells.append("".join(current).strip())
    return cells


def is_table_start(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines) or "|" not in lines[index]:
        return False
    separators = split_table_row(lines[index + 1])
    return bool(separators) and all(SEPARATOR_CELL_RE.fullmatch(cell.strip()) for cell in separators)


def is_horizontal_rule(line: str) -> bool:
    compact = re.sub(r"\s", "", line)
    return (
        len(compact) >= 3
        and len(set(compact)) == 1
        and compact[0] in {"-", "*", "_"}
    )


def slugify(text: str, used: dict[str, int]) -> str:
    normalized = unicodedata.normalize("NFC", plain_heading_text(text)).strip().lower()
    base = re.sub(r"[^\w\s-]", "", normalized)
    base = re.sub(r"\s", "-", base) or "section"
    if base not in used:
        used[base] = 1
        return base
    suffix = used[base]
    while f"{base}-{suffix}" in used:
        suffix += 1
    used[base] = suffix + 1
    slug = f"{base}-{suffix}"
    used[slug] = 1
    return slug


def strip_frontmatter(lines: list[str]) -> list[str]:
    if not lines or lines[0].strip() != "---":
        return lines
    for index in range(1, min(len(lines), 200)):
        if lines[index].strip() == "---":
            meaningful = [line.strip() for line in lines[1:index] if line.strip() and not line.lstrip().startswith("#")]
            if meaningful and re.match(r"^[A-Za-z_][\w.-]*\s*:(?:\s|$)", meaningful[0]):
                return lines[index + 1 :]
            return lines
    return lines


def render_blocks(lines: list[str], used_slugs: dict[str, int] | None = None, *, line_numbers: list[int] | None = None) -> str:
    used_slugs = used_slugs if used_slugs is not None else {}
    output: list[str] = []
    index = 0

    def starts_block(position: int) -> bool:
        if position >= len(lines):
            return True
        line = lines[position]
        return bool(
            not line.strip()
            or PAGEBREAK_RE.match(line)
            or FENCE_RE.match(line)
            or line.strip().startswith(("$$", r"\["))
            or HEADING_RE.match(line)
            or QUOTE_RE.match(line)
            or LIST_RE.match(line)
            or is_horizontal_rule(line)
            or is_table_start(lines, position)
        )

    while index < len(lines):
        line = lines[index]
        source_line = line_numbers[index] if line_numbers is not None else None
        location = f' data-source-line="{source_line}"' if source_line is not None else ""
        if not line.strip():
            index += 1
            continue

        if PAGEBREAK_RE.match(line):
            output.append(f'<div class="page-break"{location}></div>')
            index += 1
            continue

        stripped = line.strip()
        if stripped.startswith(("$$", r"\[")):
            opening = "$$" if stripped.startswith("$$") else r"\["
            closing = "$$" if opening == "$$" else r"\]"
            if stripped != opening:
                if not stripped.endswith(closing) or len(stripped) <= len(opening) + len(closing):
                    raise ConversionError(f"Fórmula matemática en la línea {source_line or index + 1}: usa {opening} y {closing} en líneas independientes o alrededor de una fórmula completa.")
                tex = stripped[len(opening):-len(closing)]
                index += 1
            else:
                index += 1
                formula_lines = []
                while index < len(lines) and lines[index].strip() != closing:
                    formula_lines.append(lines[index])
                    index += 1
                if index == len(lines):
                    raise ConversionError(f"Fórmula matemática en la línea {source_line or 1}: falta el cierre {closing}.")
                index += 1
                tex = "\n".join(formula_lines)
            if not tex.strip():
                raise ConversionError(f"Fórmula matemática vacía en la línea {source_line or 1}.")
            output.append(f'<div class="document-math-display" data-document-math="display"{location}>{html.escape(tex, quote=False)}</div>')
            continue

        fence_match = FENCE_RE.match(line)
        if fence_match:
            fence = fence_match.group(1)
            language = re.sub(r"[^A-Za-z0-9_-]", "", fence_match.group(2))
            index += 1
            code_lines: list[str] = []
            closing = re.compile(rf"^\s*{re.escape(fence[0])}{{{len(fence)},}}\s*$")
            while index < len(lines) and not closing.match(lines[index]):
                code_lines.append(lines[index])
                index += 1
            closed = index < len(lines)
            if closed:
                index += 1
            class_attr = f' class="language-{language}"' if language else ""
            code = html.escape("\n".join(code_lines), quote=False)
            if language.casefold() == "mermaid":
                if not closed or not "\n".join(code_lines).strip():
                    raise ConversionError(f"Diagrama Mermaid en la línea {source_line or 1}: el bloque debe tener contenido y una cerca de cierre.")
                mermaid = html.escape("\n".join(code_lines), quote=True)
                output.append(f'<p{location}><img src="{MERMAID_PLACEHOLDER}" alt="Diagrama Mermaid" data-document-mermaid="{mermaid}"{location}></p>')
            else:
                output.append(f"<pre{location}><code{class_attr}>{code}</code></pre>")
            continue

        if is_table_start(lines, index):
            headers = split_table_row(lines[index])
            separator = split_table_row(lines[index + 1])
            alignments: list[str] = []
            for cell in separator:
                stripped = cell.strip()
                if stripped.startswith(":") and stripped.endswith(":"):
                    alignments.append("center")
                elif stripped.endswith(":"):
                    alignments.append("right")
                else:
                    alignments.append("left")
            index += 2
            rows: list[list[str]] = []
            row_lines = []
            while index < len(lines) and lines[index].strip() and "|" in lines[index]:
                rows.append(split_table_row(lines[index]))
                row_lines.append(line_numbers[index] if line_numbers is not None else None)
                index += 1
            head_cells = "".join(
                f'<th style="text-align:{alignments[pos] if pos < len(alignments) else "left"}">'
                f"{render_inline(cell, source_line=source_line)}</th>"
                for pos, cell in enumerate(headers)
            )
            body_rows: list[str] = []
            for row, row_line in zip(rows, row_lines):
                cells = row + [""] * max(0, len(headers) - len(row))
                body_cells = "".join(
                    f'<td style="text-align:{alignments[pos] if pos < len(alignments) else "left"}">'
                    f"{render_inline(cell, source_line=row_line)}</td>"
                    for pos, cell in enumerate(cells[: len(headers)])
                )
                row_location = f' data-source-line="{row_line}"' if row_line is not None else ""
                body_rows.append(f"<tr{row_location}>{body_cells}</tr>")
            output.append(
                f"<table{location}><thead><tr>{head_cells}</tr></thead>"
                f"<tbody>{''.join(body_rows)}</tbody></table>"
            )
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            content = heading_match.group(2)
            slug = slugify(content, used_slugs)
            output.append(f'<h{level} id="{slug}"{location}>{render_inline(content, source_line=source_line)}</h{level}>')
            index += 1
            continue

        if is_horizontal_rule(line):
            output.append(f"<hr{location}>")
            index += 1
            continue

        quote_match = QUOTE_RE.match(line)
        if quote_match:
            quote_lines: list[str] = []
            quote_numbers = [] if line_numbers is not None else None
            while index < len(lines):
                current = QUOTE_RE.match(lines[index])
                if not current:
                    break
                quote_lines.append(current.group(1))
                if quote_numbers is not None:
                    quote_numbers.append(line_numbers[index])
                index += 1
            output.append(f"<blockquote{location}>{render_blocks(quote_lines, used_slugs, line_numbers=quote_numbers)}</blockquote>")
            continue

        list_match = LIST_RE.match(line)
        if list_match:
            ordered = list_match.group(1)[0].isdigit()
            tag = "ol" if ordered else "ul"
            base_indent = len(line) - len(line.lstrip())
            start_match = re.match(r"\d+", list_match.group(1)) if ordered else None
            start_attr = f' start="{start_match.group(0)}"' if start_match else ""
            items: list[str] = []
            while index < len(lines):
                if not lines[index].strip():
                    following = index + 1
                    while following < len(lines) and not lines[following].strip():
                        following += 1
                    next_item = LIST_RE.match(lines[following]) if following < len(lines) else None
                    next_indent = len(lines[following]) - len(lines[following].lstrip()) if next_item else -1
                    if next_item and next_indent == base_indent and next_item.group(1)[0].isdigit() == ordered:
                        index = following
                    else:
                        break
                current = LIST_RE.match(lines[index])
                indent = len(lines[index]) - len(lines[index].lstrip())
                if not current or indent != base_indent or current.group(1)[0].isdigit() != ordered:
                    break
                content_indent = current.start(2)
                item_lines = [current.group(2)]
                item_numbers = [line_numbers[index]] if line_numbers is not None else None
                index += 1
                while index < len(lines):
                    continuation = lines[index]
                    if not continuation.strip():
                        following = index + 1
                        while following < len(lines) and not lines[following].strip():
                            following += 1
                        next_indent = (
                            len(lines[following]) - len(lines[following].lstrip())
                            if following < len(lines) else -1
                        )
                        if next_indent < content_indent:
                            break
                        item_lines.append("")
                        if item_numbers is not None:
                            item_numbers.append(line_numbers[index])
                        index += 1
                        continue
                    continuation_indent = len(continuation) - len(continuation.lstrip())
                    if continuation_indent >= content_indent:
                        item_lines.append(continuation[content_indent:])
                        if item_numbers is not None:
                            item_numbers.append(line_numbers[index])
                        index += 1
                        continue
                    if not starts_block(index):
                        item_lines.append(continuation.lstrip())
                        if item_numbers is not None:
                            item_numbers.append(line_numbers[index])
                        index += 1
                        continue
                    break
                task = re.match(r"^\[([ xX])\]\s+(.*)$", item_lines[0])
                checkbox = ""
                item_class = ""
                if task:
                    checked = " checked" if task.group(1).lower() == "x" else ""
                    item_lines[0] = task.group(2)
                    item_class = ' class="task-item"'
                    checkbox = f'<input type="checkbox" disabled{checked}>'
                item_html = render_blocks(item_lines, used_slugs, line_numbers=item_numbers)
                if "" not in item_lines:
                    item_html = re.sub(r"^<p(?: data-source-line=\"\d+\")?>(.*?)</p>", r"\1", item_html, count=1, flags=re.DOTALL)
                items.append(f"<li{item_class}>{checkbox}{item_html}</li>")
            output.append(f"<{tag}{start_attr}{location}>{''.join(items)}</{tag}>")
            continue

        paragraph_lines = [line.lstrip()]
        index += 1
        while index < len(lines) and not starts_block(index):
            paragraph_lines.append(lines[index].lstrip())
            index += 1
        output.append(f"<p{location}>{render_inline(chr(10).join(paragraph_lines), source_line=source_line)}</p>")

    return "\n".join(output)


def plain_heading_text(source: str) -> str:
    """Reduce common inline Markdown in a heading to printable plain text."""

    rendered = render_inline(source)
    plain = re.sub(r"<[^>]*>", "", rendered)
    return html.unescape(re.sub(r"\s+", " ", plain)).strip()


def heading_at_level(markdown: str, level: int) -> str:
    lines = strip_frontmatter(
        markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    )
    fence_char: str | None = None
    fence_length = 0
    for line in lines:
        marker_match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker_match:
            marker = marker_match.group(1)
            if fence_char is None:
                fence_char = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_length:
                fence_char = None
                fence_length = 0
            continue
        if fence_char is not None:
            continue
        match = HEADING_RE.match(line)
        if match and len(match.group(1)) == level:
            return plain_heading_text(match.group(2))
    return ""


def document_headings(markdown: str, fallback: str) -> tuple[str, str]:
    title = heading_at_level(markdown, 1)
    subtitle = heading_at_level(markdown, 2)
    return title or fallback, subtitle


def build_document(
    markdown_path: Path,
    custom_css: Path | None,
    paper: str,
    landscape: bool,
    with_footer: bool,
    metadata_overrides: dict[str, str] | None = None,
    *,
    auto_margins: bool = False,
    cover: bool | None = None,
    logo: Path | None = DEFAULT_LOGO,
    logo_explicit: bool = False,
    no_branding: bool = False,
) -> tuple[str, dict[str, str], dict]:
    try:
        markdown = markdown_path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ConversionError("The Markdown file must use UTF-8 encoding.") from exc

    metadata_module = load_support_module("document_metadata")
    try:
        markdown_body, config, pdf_options = metadata_module.read_configuration(markdown)
    except ValueError as exc:
        raise ConversionError(f"{markdown_path}: {exc}") from exc
    overrides = dict(metadata_overrides or {})
    with_cover = cover if cover is not None else pdf_options.get("portada", False)
    if not logo_explicit and "logo" in pdf_options:
        value = pdf_options["logo"]
        logo = Path(value).expanduser() if value is not None else None
        if logo is not None and not logo.is_absolute():
            logo = markdown_path.parent / logo
    logo_path = logo.expanduser().resolve() if logo is not None and not no_branding else None
    presentation = {"cover": with_cover, "logo": logo_path,
                    "table_index": pdf_options.get("indice_tablas", False),
                    "figure_index": pdf_options.get("indice_figuras", False),
                    "strict": pdf_options.get("validacion", "normal") == "estricta"}
    centralized = with_cover or config is not None or bool(set(overrides) - {"clasificacion"})
    presentation["centralized_metadata"] = centralized
    source_dir_uri = markdown_path.parent.resolve().as_uri().rstrip("/") + "/"
    title, subtitle = document_headings(markdown, markdown_path.stem)
    lines = markdown_body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if markdown_body == markdown:
        # Only unrelated front matter still needs the legacy stripper. Once the
        # metadata reader consumed a block, the remaining lines are all content.
        lines = strip_frontmatter(lines)
    normalized_source = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    first_line = len(normalized_source) - len(lines) + 1
    source_numbers = list(range(first_line, first_line + len(lines)))
    footnotes = load_support_module("document_footnotes")
    try:
        lines, definitions = footnotes.extract_definitions(lines, source_numbers)
        body = render_blocks(lines, line_numbers=source_numbers)
    except (ValueError, ConversionError) as exc:
        raise ConversionError(f"{markdown_path}: {exc}") from exc
    document = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <base href="{html.escape(source_dir_uri, quote=True)}">
  <title>{html.escape(title, quote=False)}</title>
</head>
<body><main>{body}</main></body>
</html>
"""
    if centralized:
        try:
            document, metadata = metadata_module.resolve_document(
                document, config if config is not None else {}, overrides, markdown_path.stem,
                load_support_module("document_structure"),
            )
        except ValueError as exc:
            raise ConversionError(f"{markdown_path}: {exc}") from exc
    else:
        # Preserve the historic first-H1/first-H2 layout, including the existing
        # --classification option, unless central metadata was requested.
        metadata = {"titulo": title, "subtitulo": subtitle,
                    "clasificacion": overrides.get("clasificacion", "CONFIDENCIAL")}

    if with_cover:
        try:
            document = load_support_module("document_cover").apply_cover(
                document, metadata, image_data_uri(logo_path) if logo_path else None,
                load_support_module("document_structure"),
            )
        except ValueError as exc:
            raise ConversionError(f"{markdown_path}: {exc}") from exc

    try:
        document = footnotes.apply_footnotes(document, definitions, render_blocks,
                                             load_support_module("document_structure"))
    except (ValueError, ConversionError) as exc:
        raise ConversionError(f"{markdown_path}: {exc}") from exc
    presentation["technical"] = load_support_module("technical_rendering").has_technical_content(document)
    presentation["footnotes"] = len(definitions)

    decorated = with_footer
    if auto_margins:
        decorated = not no_branding and bool(with_footer or logo_path or metadata["clasificacion"])
    styles = [DEFAULT_CSS.read_text(encoding="utf-8")]
    if custom_css:
        # Imports must precede ordinary rules within their own stylesheet. Keep
        # the custom sheet embedded so its URLs retain the Markdown HTML base.
        styles.append(custom_css.read_text(encoding="utf-8"))
    orientation = "landscape" if landscape else "portrait"
    page_margin = "20mm 16mm 18mm" if decorated else "18mm 16mm"
    paper_dimensions = {"A4": (210, 297), "Letter": (215.9, 279.4), "Legal": (215.9, 355.6)}
    page_height = paper_dimensions[paper][0 if landscape else 1]
    page_width = paper_dimensions[paper][1 if landscape else 0]
    image_max_height = page_height - (38 if decorated else 36) - 8
    page_rule = (
        f"@page {{ size: {paper} {orientation}; margin: {page_margin}; }}\n"
        f":root {{ --image-max-height: {image_max_height:g}mm; --paper-height: {page_height:g}mm; --paper-width: {page_width:g}mm; }}"
    )
    if with_cover:
        # Chromium can lose named-page margins when a later stylesheet defines
        # the general @page rule. Keep both together so the measured full-page
        # cover also has the full page available when printing.
        page_rule += "\n@page document-cover { margin: 0; }"
    styles.append(page_rule)
    style_markup = "\n".join(f"  <style>{css}</style>" for css in styles)
    document = document.replace("</head>", f"{style_markup}\n</head>", 1)
    return document, metadata, presentation


def build_html(
    markdown_path: Path,
    custom_css: Path | None,
    paper: str,
    landscape: bool,
    with_footer: bool,
) -> tuple[str, str, str]:
    """Compatibility helper for consumers that only need title and subtitle."""
    document, metadata, _ = build_document(markdown_path, custom_css, paper, landscape, with_footer)
    return document, metadata["titulo"], metadata["subtitulo"]


def find_browsers(explicit: Path | None = None) -> list[Path]:
    candidates: list[Path] = []
    if explicit:
        candidates.append(explicit)

    for name in ("msedge", "google-chrome", "chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))

    if sys.platform == "win32":
        roots = [
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("PROGRAMFILES"),
            os.environ.get("LOCALAPPDATA"),
        ]
        relative_paths = (
            Path("Microsoft/Edge/Application/msedge.exe"),
            Path("Google/Chrome/Application/chrome.exe"),
            Path("Chromium/Application/chrome.exe"),
        )
        for root in roots:
            if root:
                candidates.extend(Path(root) / relative for relative in relative_paths)
    elif sys.platform == "darwin":
        candidates.extend(
            [
                Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
                Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
            ]
        )

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower() if sys.platform == "win32" else str(candidate)
        if key not in seen and candidate.is_file():
            seen.add(key)
            unique.append(candidate.resolve())
    return unique


def playwright_available() -> bool:
    try:
        return importlib.util.find_spec("playwright.sync_api") is not None
    except (ModuleNotFoundError, ValueError):
        return False


def pypdf_available() -> bool:
    try:
        return importlib.util.find_spec("pypdf") is not None
    except (ModuleNotFoundError, ValueError):
        return False


def yaml_available() -> bool:
    try:
        return importlib.util.find_spec("yaml") is not None
    except (ModuleNotFoundError, ValueError):
        return False


def load_support_module(name: str):
    """Load a sibling helper without requiring it on the caller's import path."""
    module_name = f"mdpdf_{name}"
    if module_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(module_name, SKILL_DIR / "scripts" / f"{name}.py")
        if spec is None or spec.loader is None:
            raise ConversionError(f"No se pudo cargar el módulo local: {name}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            raise
    return sys.modules[module_name]


def installed_browser_version(browser_path: Path) -> str:
    if sys.platform == "win32":
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if powershell:
            command = "(Get-Item -LiteralPath $env:MDPDF_BROWSER_PATH).VersionInfo.ProductVersion"
            version_env = os.environ.copy()
            version_env["MDPDF_BROWSER_PATH"] = str(browser_path)
            result = subprocess.run(
                [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
                env=version_env,
            )
        else:
            raise ConversionError("PowerShell is required to read the browser version on Windows.")
    else:
        result = subprocess.run(
            [str(browser_path), "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    version = (result.stdout or result.stderr).strip()
    if result.returncode != 0 or not version:
        raise ConversionError(f"Could not read browser version: {browser_path}")
    return version


def image_data_uri(path: Path) -> str:
    formats = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml"}
    mime = formats.get(path.suffix.lower())
    if mime is None:
        raise ConversionError("El logotipo debe ser un archivo PNG, JPEG o SVG.")
    if not path.is_file():
        raise ConversionError(f"No se encontró el logotipo: {path}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def header_template(logo_path: Path | None = None, classification: str = "CONFIDENCIAL") -> str:
    if not logo_path and not classification:
        return "<span></span>"
    logo = (
        f'<img src="{image_data_uri(logo_path)}" alt="Logotipo" style="display:block; '
        'width:30mm; height:9.6mm; object-fit:contain; object-position:left center;">'
        if logo_path else "<span></span>"
    )
    return (
        '<div style="width:100%; height:14mm; padding:2mm 16mm 0; '
        'box-sizing:border-box; display:flex; align-items:center; '
        'justify-content:space-between; font-family:Arial,Helvetica,sans-serif; '
        'color:#111827; -webkit-print-color-adjust:exact;">'
        f'{logo}<div style="font-size:8pt; line-height:1; font-weight:700;">'
        f'{html.escape(classification, quote=False)}</div></div>'
    )


def footer_template(title: str, subtitle: str) -> str:
    safe_title = html.escape(title, quote=False)
    safe_subtitle = html.escape(subtitle, quote=False)
    line_style = "overflow:hidden; white-space:nowrap; text-overflow:ellipsis;"
    subtitle_html = (
        f'<div style="{line_style} font-size:6.5pt; font-weight:400;">{safe_subtitle}</div>'
        if safe_subtitle
        else ""
    )
    return (
        '<div style="width:100%; min-width:0; box-sizing:border-box; '
        'padding:0 16mm; margin:0 0 2mm; display:flex; '
        'align-items:flex-end; justify-content:space-between; gap:8mm; '
        'font-family:Arial,Helvetica,sans-serif; font-size:7pt; line-height:1.2; '
        'color:#374151; -webkit-print-color-adjust:exact;">'
        '<div style="flex:1 1 0; min-width:0;">'
        f'<div style="{line_style} font-weight:600;">{safe_title}</div>{subtitle_html}</div>'
        '<div style="flex:0 0 auto; text-align:right; white-space:nowrap;">'
        'Página <span class="pageNumber"></span> de <span class="totalPages"></span>'
        "</div></div>"
    )


def fit_cover(page) -> bool:
    """Fit a single cover page while retaining readable text and all its content."""
    result = page.evaluate("""() => {
        const cover = document.querySelector('.document-cover');
        if (!cover) return 'absent';
        const pageHeight = parseFloat(getComputedStyle(document.documentElement)
            .getPropertyValue('--paper-height')) * 96 / 25.4;
        for (const scale of [1, .95, .9, .85, .8, .75, .7, .65]) {
            cover.style.setProperty('--cover-scale', String(scale));
            const bounds = cover.getBoundingClientRect();
            const style = getComputedStyle(cover);
            const bottom = bounds.bottom - parseFloat(style.paddingBottom);
            const childrenFit = [...cover.children].every(child =>
                child.getBoundingClientRect().bottom <= bottom + 1);
            if (bounds.height <= pageHeight + 1 &&
                childrenFit &&
                cover.scrollHeight <= cover.clientHeight + 1 &&
                cover.scrollWidth <= cover.clientWidth + 1) return 'fits';
        }
        return 'overflow';
    }""")
    if result == "overflow":
        raise ConversionError(
            "La portada no cabe en una página con texto legible. Acorta los datos "
            "documentales, usa un papel mayor o revisa el CSS de la portada."
        )
    return result == "fits"


def render_with_playwright(
    html_path: Path,
    pdf_path: Path,
    with_footer: bool,
    title: str,
    subtitle: str,
    logo_path: Path | None = None,
    classification: str = "CONFIDENCIAL",
    browser_path: Path | None = None,
    toc_entries: list[dict] | None = None,
    bookmarks: bool = True,
    validate_rendered_page=None,
    metadata_targets: dict[str, str] | None = None,
    resolved_metadata: dict[str, str] | None = None,
) -> str:
    from playwright.sync_api import sync_playwright

    browsers = find_browsers(browser_path)
    if browser_path and not browser_path.is_file():
        raise ConversionError(f"No se encontró el navegador indicado: {browser_path}")
    executable = browser_path or (browsers[0] if browsers else None)
    launch_options: dict[str, object] = {"headless": True}
    if executable:
        launch_options["executable_path"] = str(executable)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**launch_options)
        try:
            page = browser.new_page()
            page.goto(html_path.as_uri(), wait_until="load")
            page.emulate_media(media="print")
            technical = load_support_module("technical_rendering")
            if technical.has_technical_content(html_path.read_text(encoding="utf-8")):
                try:
                    technical.render_technical(page, SKILL_DIR)
                except technical.TechnicalRenderingError as exc:
                    raise DocumentValidationError(str(exc)) from exc
            if metadata_targets:
                labels = technical.read_text_labels(page, metadata_targets)
                title = labels.get("titulo", title)
                subtitle = labels.get("subtitulo", subtitle)
                if resolved_metadata is not None:
                    resolved_metadata.update(labels)
            page.evaluate("title => { document.title = title; }", title)
            page.evaluate("document.fonts.ready")
            has_cover = fit_cover(page)
            heading_labels = technical.prepare_heading_labels(page) if bookmarks else []
            options: dict[str, object] = {
                "path": str(pdf_path),
                "print_background": True,
                "prefer_css_page_size": True,
                "outline": bookmarks,
                "tagged": True,
            }
            if with_footer or logo_path or classification:
                options.update(
                    {
                        "display_header_footer": True,
                        "header_template": header_template(logo_path, classification),
                        "footer_template": footer_template(title, subtitle) if with_footer else "<span></span>",
                        "margin": {
                            "top": "20mm",
                            "right": "16mm",
                            "bottom": "18mm",
                            "left": "16mm",
                        },
                    }
                )
            printed_pages = None
            if toc_entries:
                navigation = load_support_module("pdf_navigation")

                def render_pass(page_numbers: dict[str, int]) -> Path:
                    page.evaluate(
                        """numbers => {
                            for (const element of document.querySelectorAll('[data-toc-target]')) {
                                const id = element.getAttribute('data-toc-target');
                                element.textContent = Object.prototype.hasOwnProperty.call(numbers, id)
                                    ? String(numbers[id]) : '…';
                            }
                        }""",
                        page_numbers,
                    )
                    page.pdf(**options)
                    return pdf_path

                try:
                    _, printed_pages, _ = navigation.stabilize_toc(render_pass, toc_entries, max_passes=4)
                except navigation.NavigationError as exc:
                    raise ConversionError(str(exc)) from exc
            else:
                page.pdf(**options)
            if has_cover and options.get("display_header_footer"):
                clean_cover = pdf_path.with_name("cover-clean.pdf")
                page.pdf(**{**options, "path": str(clean_cover),
                            "page_ranges": "1", "display_header_footer": False})
                load_support_module("document_cover").replace_cover_page(pdf_path, clean_cover)
                if toc_entries:
                    navigation.validate_navigation(pdf_path, toc_entries, printed_pages)
            if any(entry.get("needs_update") for entry in heading_labels):
                load_support_module("pdf_navigation").update_bookmark_labels(pdf_path, heading_labels)
            if validate_rendered_page is not None:
                validate_rendered_page(page)
        finally:
            browser.close()
    return f"playwright/{executable.name}" if executable else "playwright/chromium"


def render_with_browser(
    html_path: Path,
    pdf_path: Path,
    browser_path: Path,
) -> str:
    profile_dir = html_path.parent / "browser-profile"
    command = [
        str(browser_path),
        "--headless=new",
        "--disable-gpu",
        "--disable-extensions",
        "--disable-background-networking",
        "--no-first-run",
        "--no-default-browser-check",
        "--no-pdf-header-footer",
        "--allow-file-access-from-files",
        f"--user-data-dir={profile_dir}",
        f"--print-to-pdf={pdf_path}",
        html_path.as_uri(),
    ]
    # Some browser versions keep running after printing. Wait for a complete,
    # stable PDF, then close only this invocation's isolated browser process.
    with (html_path.parent / "browser.log").open("w+", encoding="utf-8") as log:
        process = subprocess.Popen(
            command, stdout=log, stderr=subprocess.STDOUT,
        )
        ready = False
        last_size = -1
        failure = "El navegador excedió el tiempo de espera de 90 segundos."
        deadline = time.monotonic() + 90
        try:
            while time.monotonic() < deadline:
                returncode = process.poll()
                if pdf_path.is_file():
                    size = pdf_path.stat().st_size
                    if size == last_size or returncode is not None:
                        try:
                            validate_pdf(pdf_path)
                        except ConversionError as exc:
                            if returncode is not None:
                                failure = str(exc)
                        else:
                            ready = True
                            break
                    last_size = size
                if returncode is not None:
                    if not pdf_path.is_file():
                        failure = f"El navegador terminó con código {returncode} sin crear un PDF."
                    break
                time.sleep(0.25)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        if not ready:
            log.seek(0)
            detail = log.read()[-4000:].strip()
            if detail:
                failure += f" Detalle del navegador: {detail}"
            raise ConversionError(f"No se pudo generar el PDF: {failure}")
    return f"browser/{browser_path.name}"


def validate_pdf(path: Path) -> None:
    if not path.is_file() or path.stat().st_size < 100:
        raise ConversionError("El motor no generó un PDF con contenido suficiente.")
    with path.open("rb") as file:
        if file.read(5) != b"%PDF-":
            raise ConversionError("El archivo generado no tiene una cabecera PDF válida.")
        file.seek(max(0, path.stat().st_size - 1024))
        if not file.read().rstrip().endswith(b"%%EOF"):
            raise ConversionError("El archivo PDF está incompleto: falta el marcador final %%EOF.")


def diagnose(explicit_browser: Path | None = None) -> int:
    print(f"Playwright: {'available' if playwright_available() else 'not found'}")
    print(f"pypdf: {'disponible' if pypdf_available() else 'no encontrado'}")
    print(f"PyYAML: {'disponible' if yaml_available() else 'no encontrado'} (metadatos documento)")
    browsers = find_browsers(explicit_browser)
    if browsers:
        for browser in browsers:
            try:
                version = installed_browser_version(browser)
            except (ConversionError, OSError, subprocess.SubprocessError) as exc:
                version = str(exc)
            print(f"Browser: {browser} ({version})")
    else:
        print("Browser: not found")
    print(f"Default CSS: {'available' if DEFAULT_CSS.is_file() else 'missing'} ({DEFAULT_CSS})")
    print("Formato: encabezado, pie, índice y marcadores predeterminados; índice requiere Playwright y pypdf.")
    print(f"Logotipo predeterminado: {DEFAULT_LOGO} ({'disponible' if DEFAULT_LOGO.is_file() else 'no encontrado'})")
    print("Formato simple: --no-branding --no-toc --no-bookmarks permite usar browser sin Playwright.")
    return 0 if playwright_available() or browsers else 1


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert Markdown to a printable PDF.")
    parser.add_argument("input", nargs="?", type=Path, help="Input Markdown file")
    parser.add_argument("-o", "--output", type=Path, help="Output PDF; defaults beside input")
    parser.add_argument("--paper", choices=PAPER_SIZES, default="A4", help="Page size")
    parser.add_argument("--landscape", action="store_true", help="Use landscape orientation")
    parser.add_argument("--css", type=Path, help="Additional CSS file")
    parser.add_argument(
        "--engine",
        choices=("auto", "playwright", "browser"),
        default="auto",
        help="PDF rendering engine",
    )
    parser.add_argument("--browser", type=Path, help="Ejecutable de Chrome, Edge o Chromium para cualquier motor")
    logo = parser.add_mutually_exclusive_group()
    logo.add_argument("--logo", type=Path, default=argparse.SUPPRESS, help="Logotipo PNG, JPEG o SVG; prioridad sobre pdf.logo")
    logo.add_argument("--no-logo", dest="logo", action="store_const", const=None, default=argparse.SUPPRESS, help="Omite los logotipos del encabezado y la portada")
    cover = parser.add_mutually_exclusive_group()
    cover.add_argument("--cover", dest="cover", action="store_true", help="Activa la portada; prioridad sobre pdf.portada")
    cover.add_argument("--no-cover", dest="cover", action="store_false", help="Omite la portada y conserva los datos iniciales")
    for option, description in (("table-index", "índice de tablas"), ("figure-index", "índice de figuras")):
        group = parser.add_mutually_exclusive_group()
        group.add_argument(f"--{option}", dest=option.replace("-", "_"), action="store_true", help=f"Activa el {description}; prioridad sobre YAML")
        group.add_argument(f"--no-{option}", dest=option.replace("-", "_"), action="store_false", help=f"Omite el {description}")
    strict = parser.add_mutually_exclusive_group()
    strict.add_argument("--strict", action="store_true", help="Impide exportar también ante advertencias de validación")
    strict.add_argument("--no-strict", dest="strict", action="store_false", help="Permite exportar con advertencias; los errores siguen impidiendo exportar")
    parser.add_argument("--classification", default=None, help="Clasificación; prevalece sobre documento.clasificacion. Vacío la omite")
    metadata_options = {
        "title": "titulo", "subtitle": "subtitulo", "document-code": "codigo",
        "document-version": "version", "document-date": "fecha", "document-status": "estado",
    }
    for option, field in metadata_options.items():
        parser.add_argument(f"--{option}", metavar="TEXT", help=f"Sustituye documento.{field}; vacío lo omite")
    footer = parser.add_mutually_exclusive_group()
    footer.add_argument(
        "--footer", action="store_true",
        help="Añade título y paginación al pie (predeterminado); requiere Playwright",
    )
    footer.add_argument(
        "--no-footer", dest="footer", action="store_false", help="Omite el pie y conserva el encabezado",
    )
    parser.add_argument("--no-branding", action="store_true", help="Omite encabezado, logotipo y pie")
    for option, description in (
        ("toc", "índice automático con enlaces y páginas reales"),
        ("bookmarks", "marcadores laterales del PDF"),
        ("captions", "rótulos numerados generados de tablas y figuras"),
    ):
        group = parser.add_mutually_exclusive_group()
        group.add_argument(f"--{option}", dest=option, action="store_true", help=f"Activa {description} (predeterminado)")
        omit_help = f"Omite {description}"
        if option == "captions":
            omit_help += "; conserva los textos Tabla:/Figura:, los índices activos y las referencias"
        group.add_argument(f"--no-{option}", dest=option, action="store_false", help=omit_help)
    parser.add_argument("--toc-depth", type=int, choices=range(1, 7), default=2, metavar="1..6", help="Niveles de secciones en el índice; predeterminado: 2")
    parser.set_defaults(footer=True, cover=None, toc=True, bookmarks=True, captions=True,
                        table_index=None, figure_index=None, strict=None)
    parser.add_argument("--force", action="store_true", help="Replace an existing PDF")
    parser.add_argument("--diagnose", action="store_true", help="Show available rendering engines")
    args = parser.parse_args(argv)
    args.logo_explicit = hasattr(args, "logo")
    if not args.logo_explicit:
        args.logo = DEFAULT_LOGO
    args.metadata_overrides = {
        field: getattr(args, option.replace("-", "_"))
        for option, field in metadata_options.items()
        if getattr(args, option.replace("-", "_")) is not None
    }
    if args.classification is not None:
        args.metadata_overrides["clasificacion"] = args.classification
    else:
        args.classification = "CONFIDENCIAL"
    if args.no_branding:
        args.footer = False
        args.classification = ""
        args.logo = None
    return args


def convert(args: argparse.Namespace) -> tuple[Path, str]:
    if args.input is None:
        raise ConversionError("Provide an input Markdown file or use --diagnose.")

    source = args.input.expanduser().resolve()
    if not source.is_file():
        raise ConversionError(f"Markdown file not found: {source}")
    if source.suffix.lower() not in SUPPORTED_INPUTS:
        raise ConversionError(f"Unsupported input extension: {source.suffix or '(none)'}")
    if not DEFAULT_CSS.is_file():
        raise ConversionError(f"Default print stylesheet not found: {DEFAULT_CSS}")

    with_footer = args.footer
    browser_path = args.browser.expanduser().resolve() if args.browser else None
    if browser_path and not browser_path.is_file():
        raise ConversionError(f"No se encontró el navegador indicado: {browser_path}")
    custom_css = args.css.expanduser().resolve() if args.css else None
    if custom_css and not custom_css.is_file():
        raise ConversionError(f"Custom CSS not found: {custom_css}")

    output = (args.output or source.with_suffix(".pdf")).expanduser().resolve()
    if output.suffix.lower() != ".pdf":
        raise ConversionError("The output file must use the .pdf extension.")
    if not output.parent.is_dir():
        raise ConversionError(f"Output directory not found: {output.parent}")
    if output.exists() and not args.force:
        raise ConversionError(f"Output already exists; use --force to replace it: {output}")

    html_document, metadata, presentation = build_document(
        source, custom_css, args.paper, args.landscape, with_footer,
        args.metadata_overrides, auto_margins=True, cover=args.cover,
        logo=args.logo, logo_explicit=args.logo_explicit,
        no_branding=args.no_branding,
    )
    args.cover = presentation["cover"]
    for option in ("table_index", "figure_index", "strict"):
        if getattr(args, option) is None:
            setattr(args, option, presentation[option])
    logo_path = args.logo = presentation["logo"]
    if logo_path:
        image_data_uri(logo_path)
    args.resolved_metadata = metadata
    title, subtitle = metadata["titulo"], metadata["subtitulo"]
    classification = "" if args.no_branding else metadata["clasificacion"]
    args.classification = classification
    requires_playwright = bool(args.cover or with_footer or logo_path or classification or args.toc or args.bookmarks or args.table_index or args.figure_index or presentation["technical"])
    args.footnote_count = presentation["footnotes"]
    args.technical_counts = load_support_module("technical_rendering").technical_requirements(html_document)
    if presentation["technical"] and args.engine == "browser":
        raise ConversionError("Los diagramas Mermaid y las fórmulas matemáticas requieren Playwright y los recursos locales assets/vendor del skill; use --engine playwright o auto.")
    if requires_playwright and args.engine == "browser":
        raise ConversionError(
            "El formato solicitado requiere Playwright; para browser use --no-cover --no-branding --no-toc --no-bookmarks --no-table-index --no-figure-index."
        )
    structure_module = load_support_module("document_structure")
    try:
        html_document, structure = structure_module.prepare_document(
            html_document, with_toc=args.toc, with_captions=args.captions, toc_depth=args.toc_depth,
            with_table_index=args.table_index, with_figure_index=args.figure_index,
        )
    except ValueError as exc:
        raise ConversionError(f"{source}: {exc}") from exc
    html_document, metadata_targets = load_support_module("document_metadata").refresh_generated_metadata(
        html_document, metadata, presentation["centralized_metadata"], structure_module,
    )
    title, subtitle = metadata["titulo"], metadata["subtitulo"]
    html_document = normalize_document_links(html_document, source)
    toc_entries = structure["navigation_entries"]
    args.toc_entries_count = len(structure["entries"]) if args.toc else 0
    args.table_index_count = len(structure["tables"]) if args.table_index else 0
    args.figure_index_count = len(structure["figures"]) if args.figure_index else 0
    args.table_count = len(structure["tables"])
    args.figure_count = len(structure["figures"])
    validation = load_support_module("document_validation")
    args.validation_diagnostics = validation.validate_html(html_document, source, css_paths=[custom_css] if custom_css else [])
    check_diagnostics(args.validation_diagnostics, strict=args.strict)
    margins = (20, 16, 18, 16) if with_footer or logo_path or classification else (18, 16, 18, 16)

    def validate_rendered_page(page):
        diagnostics = validation.inspect_page(page, source, paper=args.paper,
                                              landscape=args.landscape, margins_mm=margins)
        if logo_path and not page.evaluate("""src => new Promise(resolve => {
            const image = new Image();
            image.onload = () => resolve(image.naturalWidth > 0);
            image.onerror = () => resolve(false);
            image.src = src;
        })""", image_data_uri(logo_path)):
            diagnostics.append(validation.Diagnostic(
                severity="error", code="image-load-failed", source=str(logo_path),
                message="No se pudo cargar o decodificar el logotipo del encabezado.",
            ))
        args.validation_diagnostics.extend(diagnostics)
        check_diagnostics(diagnostics, strict=args.strict)

    if (args.cover or toc_entries) and not pypdf_available():
        raise ConversionError("La portada y el índice paginado requieren pypdf en el entorno local del skill; consulte requirements.txt.")
    errors: list[str] = []
    engine_used: str | None = None

    with tempfile.TemporaryDirectory(prefix="mdpdf-", dir=output.parent) as temp_name:
        temp_dir = Path(temp_name)
        html_path = temp_dir / "document.html"
        temp_pdf = temp_dir / "document.pdf"
        html_path.write_text(html_document, encoding="utf-8")

        if args.engine in {"auto", "playwright"}:
            if playwright_available():
                try:
                    candidate_engine = render_with_playwright(
                        html_path, temp_pdf, with_footer, title, subtitle,
                        logo_path=logo_path, classification=classification, browser_path=browser_path,
                        toc_entries=toc_entries, bookmarks=args.bookmarks,
                        validate_rendered_page=validate_rendered_page,
                        metadata_targets=metadata_targets, resolved_metadata=metadata,
                    )
                    validate_pdf(temp_pdf)
                    engine_used = candidate_engine
                except DocumentValidationError as exc:
                    if str(source) not in str(exc):
                        raise DocumentValidationError(f"{source}: {exc}") from exc
                    raise
                except Exception as exc:  # Preserve browser fallback in auto mode.
                    errors.append(f"Playwright: {exc}")
                    if args.engine == "playwright":
                        raise ConversionError(errors[-1]) from exc
            elif args.engine == "playwright":
                raise ConversionError("Playwright no está disponible en el entorno de Python del skill.")

        if engine_used is None and requires_playwright:
            detail = "; ".join(errors) if errors else "Playwright no está disponible en el entorno local"
            raise ConversionError(
                "El formato solicitado requiere Playwright. " + detail
            )

        if engine_used is None and args.engine in {"auto", "browser"}:
            partial = validation.Diagnostic(
                severity="warning", code="validation-partial", source=str(source),
                message="El motor browser solo valida recursos locales y enlaces del HTML; no comprueba carga de imágenes, maquetación ni páginas vacías. Use Playwright para una revisión completa.",
            )
            args.validation_diagnostics.append(partial)
            check_diagnostics([partial], strict=args.strict)
            browsers = find_browsers(browser_path)
            if not browsers:
                errors.append("Browser: no Edge, Chrome, or Chromium executable found")
            for browser in browsers:
                if temp_pdf.exists():
                    temp_pdf.unlink()
                try:
                    candidate_engine = render_with_browser(html_path, temp_pdf, browser)
                    validate_pdf(temp_pdf)
                    engine_used = candidate_engine
                    break
                except Exception as exc:
                    errors.append(f"{browser}: {exc}")
            if args.engine == "browser" and engine_used is None:
                raise ConversionError("; ".join(errors))

        if engine_used is None:
            raise ConversionError("No PDF rendering engine succeeded. " + "; ".join(errors))

        validate_pdf(temp_pdf)
        if engine_used.startswith("playwright/"):
            diagnostics = validation.inspect_pdf(temp_pdf, source, html_document=html_document, margins_mm=margins)
            args.validation_diagnostics.extend(diagnostics)
            check_diagnostics(diagnostics, strict=args.strict)
        os.replace(temp_pdf, output)

    validate_pdf(output)
    return output, engine_used


def use_local_environment(args: argparse.Namespace, argv: list[str]) -> None:
    """Reuse this skill's existing environment without installing or retry loops."""
    needs_playwright = args.engine == "playwright" or (
        args.engine != "browser" and (args.diagnose or args.cover or args.footer or args.classification or args.logo or args.toc or args.bookmarks or args.table_index or args.figure_index or args.strict)
    )
    needs_pypdf = bool(needs_playwright or args.toc or args.cover or args.table_index or args.figure_index)
    needs_yaml = False
    if args.input and args.input.expanduser().is_file():
        try:
            # The helper detects relevant front matter without importing YAML.
            metadata_module = load_support_module("document_metadata")
            markdown = args.input.expanduser().read_text(encoding="utf-8-sig")
            needs_yaml = metadata_module.has_metadata_frontmatter(markdown)
            if args.engine != "browser" and not needs_playwright:
                # Parse the supported syntax so examples in fences and escaped
                # delimiters do not require engines they never execute.
                body = markdown
                if needs_yaml and yaml_available():
                    body, _, _ = metadata_module.read_configuration(markdown)
                markup = render_blocks(strip_frontmatter(body.splitlines()))
                if load_support_module("technical_rendering").has_technical_content(markup):
                    needs_playwright = needs_pypdf = True
            if needs_yaml and yaml_available() and args.engine != "browser":
                _, _, pdf_options = metadata_module.read_configuration(markdown)
                for argument, key in (("cover", "portada"), ("table_index", "indice_tablas"), ("figure_index", "indice_figuras")):
                    if getattr(args, argument) is None and pdf_options.get(key, False):
                        needs_playwright = needs_pypdf = True
                if args.strict is None and pdf_options.get("validacion") == "estricta":
                    needs_playwright = needs_pypdf = True
        except (OSError, UnicodeError, ValueError, ConversionError):
            pass  # convert() reports the source error with its normal diagnostic.
    ready = (not needs_playwright or (playwright_available() and (not needs_pypdf or pypdf_available()))) and (not needs_yaml or yaml_available())
    if (not needs_playwright and not needs_yaml) or ready or os.environ.get("MDPDF_LOCAL_REEXEC"):
        return
    environment_dir = SKILL_DIR / ".venv"
    if Path(sys.prefix).resolve() == environment_dir.resolve():
        return
    local_python = environment_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not local_python.is_file():
        return
    environment = os.environ.copy()
    environment["MDPDF_LOCAL_REEXEC"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    os.execve(str(local_python), [str(local_python), str(Path(__file__).resolve()), *argv], environment)


def main(argv: list[str] | None = None) -> int:
    arguments = argv if argv is not None else sys.argv[1:]
    args = parse_args(arguments)
    try:
        use_local_environment(args, arguments)
        if args.diagnose:
            return diagnose(args.browser.expanduser().resolve() if args.browser else None)
        output, engine = convert(args)
        print(f"PDF created: {output}")
        print(f"Engine: {engine}")
        if args.cover:
            print("Portada: página 1, incluida en la paginación total")
        if args.footer:
            print("Pie: título, subtítulo y numeración de páginas")
        if args.classification:
            print(f"Clasificación: {args.classification}")
        if args.logo:
            print(f"Logotipo: {args.logo}")
        if args.toc_entries_count:
            print(f"Índice: {args.toc_entries_count} entradas con páginas verificadas")
        if args.table_index_count:
            label = "entrada" if args.table_index_count == 1 else "entradas"
            print(f"Índice de tablas: {args.table_index_count} {label} con páginas verificadas")
        if args.figure_index_count:
            label = "entrada" if args.figure_index_count == 1 else "entradas"
            print(f"Índice de figuras: {args.figure_index_count} {label} con páginas verificadas")
        if args.captions:
            tables_label = "tabla" if args.table_count == 1 else "tablas"
            figures_label = "figura" if args.figure_count == 1 else "figuras"
            print(f"Identificación: {args.table_count} {tables_label} y {args.figure_count} {figures_label}")
        if args.footnote_count:
            print(f"Notas: {args.footnote_count}, numeradas al final del documento con enlaces de retorno")
        if args.validation_diagnostics:
            validation = load_support_module("document_validation")
            for diagnostic in args.validation_diagnostics:
                print(validation.format_diagnostic(diagnostic), file=sys.stderr)
        else:
            print("Validación: sin incidencias detectadas")
        return 0
    except UnicodeError as exc:
        print(f"Error: Los archivos de entrada y estilos deben estar codificados en UTF-8. {exc}", file=sys.stderr)
        return 2
    except (ConversionError, OSError, subprocess.SubprocessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
