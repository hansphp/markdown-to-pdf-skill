"""Document diagnostics without fetching resources or changing source files.

Static checks use only the standard library. Browser geometry is deliberately
reported as a warning: continuous DOM coordinates cannot predict every print
fragment. PDF checks inspect actual pages and ignore repeated margin content.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import quote, unquote, urljoin, urlsplit


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    code: str
    message: str
    source: str | None = None
    line: int | None = None
    selector: str | None = None
    page: int | None = None

    def as_dict(self):
        return {key: value for key, value in asdict(self).items() if value is not None}


def format_diagnostic(diagnostic: Diagnostic) -> str:
    location = diagnostic.source or "documento"
    if diagnostic.line is not None:
        location += f":{diagnostic.line}"
    details = []
    if diagnostic.page is not None:
        details.append(f"página {diagnostic.page}")
    if diagnostic.selector:
        details.append(diagnostic.selector)
    if details:
        location += " (" + ", ".join(details) + ")"
    level = "Error" if diagnostic.severity == "error" else "Advertencia"
    return f"{location}: {level} [{diagnostic.code}]: {diagnostic.message}"


class _Element:
    def __init__(self, tag, attrs, parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []
        self.text = ""

    @property
    def line(self):
        raw = self.attrs.get("data-source-line")
        if raw and raw.isdecimal():
            return int(raw)
        return self.parent.line if self.parent else None

    @property
    def selector(self):
        identifier = self.attrs.get("id")
        if identifier:
            return f"{self.tag}#{identifier}"
        peers = [child for child in self.parent.children if child.tag == self.tag] if self.parent else [self]
        return f"{self.tag}:nth-of-type({peers.index(self) + 1})"


class _Parser(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, document):
        super().__init__(convert_charrefs=True)
        self.root = _Element("document", [])
        self.stack = [self.root]
        self.elements = []
        self.flow = []
        self.feed(document)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = _Element(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        self.elements.append(node)
        if "page-break" in (node.attrs.get("class") or "").split():
            self.flow.append(("break", node))
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack[-1].tag == tag and tag not in self.VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].text += data
        if any(node.tag in {"style", "script", "head"} for node in self.stack):
            return
        if data.strip():
            self.flow.append(("text", data))


def _local_path(url, base):
    """Return a local filesystem path; do not interpret remote URLs as paths."""
    parts = urlsplit(urljoin(base, url))
    if parts.scheme != "file" or parts.netloc not in {"", "localhost"}:
        return None
    return Path(unquote(parts.path))


def _source_line(path, needle):
    if not needle:
        return None
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError):
        return None
    matches = [number for number, text in enumerate(lines, 1) if needle in text or unquote(needle) in text]
    # Do not invent an exact line when several references could have produced it.
    return matches[0] if len(matches) == 1 else None


def _css_references(css):
    cleaned = re.sub(r"/\*.*?\*/", lambda match: "\n" * match.group().count("\n"), css, flags=re.S)
    pattern = re.compile(r"url\(\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s)]*))\s*\)|@import\s+(?:\"([^\"]+)\"|'([^']+)')", re.I)
    for match in pattern.finditer(cleaned):
        yield next((part for part in match.groups() if part is not None), ""), cleaned.count("\n", 0, match.start()) + 1


def validate_html(html_document: str, markdown_path: Path, *, css_paths=()) -> list[Diagnostic]:
    """Check local resources and every same-document anchor, including body links.

    Embedded custom CSS URLs use the HTML base (the Markdown directory), exactly
    as the browser does. css_paths provide better diagnostic source locations.
    External hyperlinks are not opened and fragments in other files are ignored.
    """
    markdown_path = Path(markdown_path).resolve()
    parser = _Parser(html_document)
    base = markdown_path.parent.as_uri() + "/"
    base_node = next((node for node in parser.elements if node.tag == "base"), None)
    if base_node and base_node.attrs.get("href"):
        base = urljoin(base, base_node.attrs["href"])
    identifiers = {node.attrs["id"] for node in parser.elements if node.attrs.get("id")}
    identifiers.update(node.attrs["name"] for node in parser.elements if node.tag == "a" and node.attrs.get("name"))
    diagnostics = []
    css_files = [Path(path).resolve() for path in css_paths]
    seen_resources = set()

    def resource(url, node, *, css=False):
        if css and (not url or url.startswith("#")):
            return
        local = _local_path(url, base)
        invalid = not url.strip() or (not css and url.startswith("#"))
        if not invalid and (local is None or local.is_file()):
            return
        source = markdown_path
        line = node.line or _source_line(source, url)
        if css:
            for css_path in css_files:
                css_line = _source_line(css_path, url)
                if css_line is not None:
                    source, line = css_path, css_line
                    break
        key = (url, str(source), line)
        if key in seen_resources:
            return
        seen_resources.add(key)
        diagnostics.append(Diagnostic("error", "resource-missing", f"No existe el recurso local: {url or '(ruta vacía)'}." if not invalid else "La imagen no tiene una ruta válida.", str(source), line, node.selector))

    for node in parser.elements:
        if node.tag == "img":
            resource(node.attrs.get("src", ""), node)
        elif node.tag == "link" and "stylesheet" in (node.attrs.get("rel") or "").split():
            resource(node.attrs.get("href", ""), node, css=True)
        if node.tag == "style":
            for url, _ in _css_references(node.text):
                resource(url, node, css=True)
        if node.attrs.get("style"):
            for url, _ in _css_references(node.attrs["style"]):
                resource(url, node, css=True)
        if node.tag != "a" or "href" not in node.attrs:
            continue
        href = node.attrs["href"]
        parts = urlsplit(href)
        if not parts.fragment:
            continue
        same_document = not parts.path and not parts.scheme and not parts.netloc
        target_path = _local_path(href, base)
        if target_path is not None:
            same_document = same_document or target_path.resolve() == markdown_path
        anchor = unquote(parts.fragment)
        if same_document and anchor not in identifiers:
            diagnostics.append(Diagnostic("error", "anchor-missing", f"El enlace «{href}» apunta a un identificador inexistente: {anchor}.", str(markdown_path), node.line or _source_line(markdown_path, href), node.selector))
    return diagnostics


_BROWSER_INSPECTION = r"""({contentHeight, physicalWidth}) => {
    const main = document.querySelector('main') || document.body;
    const output = [];
    const selector = element => {
        if (element.id) return element.tagName.toLowerCase() + '#' + element.id;
        if (element === main || element === document.body) return element.tagName.toLowerCase();
        const path = [];
        while (element && element !== main && path.length < 4) {
            const peers = [...element.parentElement.children].filter(peer => peer.tagName === element.tagName);
            path.unshift(element.tagName.toLowerCase() + ':nth-of-type(' + (peers.indexOf(element) + 1) + ')');
            element = element.parentElement;
        }
        return 'main > ' + path.join(' > ');
    };
    const add = (element, severity, code, message) => {
        const origin = element.closest('[data-source-line]');
        output.push({severity, code, message, selector: selector(element),
            line: origin ? Number(origin.dataset.sourceLine) : null});
    };
    const bounds = main.getBoundingClientRect();
    const overflowing = [];
    const clipped = [];
    const tall = [];
    const rootStyle = getComputedStyle(document.documentElement);
    // Chromium propagates body's overflow to the viewport when html has no
    // overflow of its own. That viewport still paginates its complete content;
    // body's scrollHeight/clientHeight alone would report a false print crop.
    const bodyOverflowPropagates = rootStyle.overflowX === 'visible' && rootStyle.overflowY === 'visible';
    if (bounds.left < -2 || bounds.right > window.innerWidth + 2) {
        add(main, 'warning', 'layout-horizontal-overflow', 'El contenedor principal supera el ancho imprimible.');
        overflowing.push(main);
    }
    for (const element of new Set([document.body, main, ...main.querySelectorAll('*')])) {
        // KaTeX clips its MathML accessibility copy to one pixel; the separate
        // visible HTML is the representation whose print geometry matters.
        if (element.closest('[data-document-math] .katex-mathml')) continue;
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        if (style.display === 'none' || style.visibility === 'hidden') continue;
        const clipsVertically = ['hidden', 'clip', 'auto', 'scroll'].includes(style.overflowY) &&
            !(element === document.body && bodyOverflowPropagates);
        if (clipsVertically && element.scrollHeight > element.clientHeight + 2 &&
                !clipped.some(parent => parent.contains(element))) {
            clipped.push(element);
            add(element, 'warning', 'layout-vertical-clipping',
                'El elemento puede recortar contenido vertical (contenido ' + element.scrollHeight +
                ' px; altura visible ' + element.clientHeight + ' px; overflow-y: ' + style.overflowY + ').');
        }
        // Include these containers in clipping checks, including zero-height
        // boxes, without applying descendant positioning checks to the roots.
        if (element === main || element === document.body) continue;
        if (element.tagName === 'IMG' && (!element.complete || element.naturalWidth === 0))
            add(element, 'error', 'image-load-failed', 'No se pudo cargar o decodificar la imagen: ' + (element.getAttribute('src') || '(ruta vacía)') + '.');
        if (!rect.width || !rect.height) continue;
        const cover = element.closest('.document-cover');
        const allowed = cover ? cover.getBoundingClientRect() : bounds;
        // Cover uses a named zero-margin page; its physical width is intentional.
        if (element === cover) continue;
        const outside = rect.left < allowed.left - 2 || rect.right > allowed.right + 2;
        const internal = element.clientWidth && element.scrollWidth > element.clientWidth + 2;
        if ((outside || internal) && !overflowing.some(parent => parent.contains(element))) {
            overflowing.push(element);
            add(element, 'warning', 'layout-horizontal-overflow',
                'El elemento puede sobresalir del ancho imprimible o recortar contenido (' + Math.round(Math.max(rect.width, element.scrollWidth)) + ' px).');
        }
        if (cover) continue; // fit_cover validates the complete first page separately.
        const unbreakable = ['IMG', 'SVG', 'CANVAS', 'TR'].includes(element.tagName) ||
            /avoid/.test(style.breakInside) || /avoid/.test(style.pageBreakInside);
        if (unbreakable && rect.height > contentHeight + 2 && !tall.some(parent => parent.contains(element))) {
            tall.push(element);
            add(element, 'warning', 'layout-unbreakable-height',
                'El elemento evita los saltos y supera la altura imprimible (' + Math.round(rect.height) + ' px; disponible ' + Math.round(contentHeight) + ' px).');
        }
        if (rect.top < -2 || (['fixed', 'absolute'].includes(style.position) &&
                (rect.height > contentHeight + 2 || (style.position === 'fixed' && rect.bottom > contentHeight + 2))))
            add(element, 'warning', 'layout-positioned-outside', 'El elemento puede quedar fuera del área imprimible por su posición.');
    }
    return output;
}"""


def inspect_page(page, markdown_path: Path, *, paper="A4", landscape=False, margins_mm=(20, 16, 18, 16)) -> list[Diagnostic]:
    """Inspect images and geometry at print-content width, restoring the viewport."""
    width, height = {"A4": (210, 297), "Letter": (215.9, 279.4), "Legal": (215.9, 355.6)}[paper]
    if landscape:
        width, height = height, width
    top, right, bottom, left = margins_mm
    viewport = page.viewport_size
    try:
        page.set_viewport_size({"width": max(1, round((width - left - right) * 96 / 25.4)), "height": max(1, round(height * 96 / 25.4))})
        raw = page.evaluate(_BROWSER_INSPECTION, {"contentHeight": (height - top - bottom) * 96 / 25.4, "physicalWidth": width * 96 / 25.4})
        return [Diagnostic(source=str(Path(markdown_path).resolve()), **item) for item in raw]
    finally:
        if viewport is not None:
            page.set_viewport_size(viewport)


def _normalized(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _intentional_blank_pages(html_document, page_texts, blank_pages):
    """Match explicit break runs to their immediate content gap in the real PDF."""
    flow = _Parser(html_document).flow
    allowed = set()
    index = 0
    while index < len(flow):
        if flow[index][0] != "break":
            index += 1
            continue
        start = index
        while index < len(flow) and flow[index][0] == "break":
            index += 1
        before = next((_normalized(value)[-80:] for kind, value in reversed(flow[:start]) if kind == "text"), "")
        after = next((_normalized(value)[:80] for kind, value in flow[index:] if kind == "text"), "")
        # A normal isolated break starts the following page. Only consecutive
        # or leading breaks express a request that can produce an empty page.
        budget = index - start - (1 if before else 0)
        if budget <= 0:
            continue
        left_pages = [page for page, text in enumerate(page_texts, 1) if before and before in text] if before else [0]
        right_pages = [page for page, text in enumerate(page_texts, 1) if after and after in text] if after else [len(page_texts) + 1]
        for left in left_pages:
            right = next((page for page in right_pages if page > left), None)
            if right is None:
                continue
            gap = set(range(left + 1, right))
            if gap and gap <= blank_pages and len(gap) <= budget:
                allowed.update(gap)
    return allowed


def _page_has_content(page, margins_mm):
    """Ignore white backgrounds and painting confined to header/footer margins."""
    top, right, bottom, left = (value * 72 / 25.4 for value in margins_mm)
    box = page.mediabox
    # Chromium rounds millimetre margins to device units. Permit one PDF point
    # so left-aligned text on the nominal boundary remains body content.
    xmin, ymin = float(box.left) + left - 1, float(box.bottom) + bottom - 1
    xmax, ymax = float(box.right) - right + 1, float(box.top) - top + 1
    visible = False
    path = []
    fill = [0.0]
    stroke = [0.0]
    states = []

    def point(x, y, matrix):
        return (matrix[0] * x + matrix[2] * y + matrix[4], matrix[1] * x + matrix[3] * y + matrix[5])

    def intersects(points):
        if not points:
            return False
        xs, ys = zip(*points)
        return max(xs) >= xmin and min(xs) <= xmax and max(ys) >= ymin and min(ys) <= ymax

    def colored(color):
        if len(color) == 4:
            return any(value > 0.01 for value in color)
        return not all(value >= 0.99 for value in color)

    def text_visitor(text, cm, tm, font, size):
        nonlocal visible
        if text.strip() and intersects([point(tm[4], tm[5], cm)]):
            visible = True

    def operation(operator, operands, cm, tm):
        nonlocal visible, path, fill, stroke
        if operator == b"q":
            states.append((fill[:], stroke[:]))
        elif operator == b"Q" and states:
            fill, stroke = states.pop()
        elif operator in {b"g", b"rg", b"k"}:
            fill = [float(value) for value in operands]
        elif operator in {b"G", b"RG", b"K"}:
            stroke = [float(value) for value in operands]
        elif operator == b"re":
            x, y, width, height = map(float, operands)
            path.extend(point(px, py, cm) for px, py in ((x, y), (x + width, y), (x, y + height), (x + width, y + height)))
        elif operator in {b"m", b"l", b"c", b"v", b"y"}:
            path.extend(point(float(operands[index]), float(operands[index + 1]), cm) for index in range(0, len(operands), 2))
        elif operator in {b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*", b"n"}:
            paint_fill = operator in {b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"} and colored(fill)
            paint_stroke = operator in {b"S", b"s", b"B", b"B*", b"b", b"b*"} and colored(stroke)
            if (paint_fill or paint_stroke) and intersects(path):
                visible = True
            path = []
        elif operator == b"Do":
            resources = page.get("/Resources", {})
            resources = resources.get_object() if hasattr(resources, "get_object") else resources
            objects = resources.get("/XObject", {})
            objects = objects.get_object() if hasattr(objects, "get_object") else objects
            obj = objects.get(operands[0])
            if obj is not None:
                obj = obj.get_object()
                bounds = obj.get("/BBox", [0, 0, 1, 1])
                corners = [point(float(x), float(y), cm) for x, y in ((bounds[0], bounds[1]), (bounds[2], bounds[3]))]
                if intersects(corners):
                    visible = True
        elif operator == b"INLINE IMAGE":
            if intersects([point(0, 0, cm), point(1, 1, cm)]):
                visible = True

    text = page.extract_text(visitor_text=text_visitor, visitor_operand_before=operation) or ""
    return visible, _normalized(text)


def _pdf_anchor_diagnostics(reader, html_document, markdown_path):
    parser = _Parser(html_document)
    markdown_path = Path(markdown_path).resolve()
    base = markdown_path.parent.as_uri() + "/"
    base_node = next((node for node in parser.elements if node.tag == "base"), None)
    if base_node and base_node.attrs.get("href"):
        base = urljoin(base, base_node.attrs["href"])
    named = reader.named_destinations
    checked = set()
    diagnostics = []
    for node in parser.elements:
        href = node.attrs.get("href", "") if node.tag == "a" else ""
        parts = urlsplit(href)
        if not parts.fragment:
            continue
        local = _local_path(href, base)
        if (parts.path or parts.scheme or parts.netloc) and (local is None or local.resolve() != markdown_path):
            continue
        anchor = unquote(parts.fragment)
        if anchor in checked:
            continue
        checked.add(anchor)
        encoded = quote(anchor, safe="-._~")
        key = next((value for value in (anchor, "/" + anchor, encoded, "/" + encoded) if value in named), None)
        if key is None:
            matches = [name for name in named if unquote(str(name).removeprefix("/")) == anchor]
            key = matches[0] if len(matches) == 1 else None
        page = reader.get_destination_page_number(named[key]) if key is not None else None
        if page is None or page < 0 or page >= len(reader.pages):
            diagnostics.append(Diagnostic("error", "pdf-anchor-missing", f"El enlace «{href}» no tiene un destino verificable en el PDF final; revisa si el elemento está oculto o fuera del documento.", str(markdown_path), node.line or _source_line(markdown_path, href), node.selector))
    return diagnostics


def inspect_pdf(pdf_path: Path, markdown_path: Path, *, html_document=None, margins_mm=(20, 16, 18, 16)) -> list[Diagnostic]:
    """Warn about actual blank pages; pypdf is loaded only when called."""
    source = str(Path(markdown_path).resolve())
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError:
        return [Diagnostic("warning", "validation-partial", "No se pudieron comprobar las páginas vacías ni los destinos internos del PDF porque falta pypdf. Usa las dependencias del entorno local del skill para completar la validación.", source)]

    diagnostics = []
    blank_pages = set()
    texts = []
    has_cover = bool(html_document and any("document-cover" in (node.attrs.get("class") or "").split() for node in _Parser(html_document).elements))
    try:
        with PdfReader(str(pdf_path)) as reader:
            if not reader.pages:
                return [Diagnostic("error", "pdf-read-error", f"El PDF no contiene páginas: {pdf_path}.", source)]
            for number, page in enumerate(reader.pages, 1):
                present, text = _page_has_content(page, (0, 0, 0, 0) if number == 1 and has_cover else margins_mm)
                texts.append(text)
                if not present:
                    blank_pages.add(number)
            if html_document:
                diagnostics.extend(_pdf_anchor_diagnostics(reader, html_document, markdown_path))
    except (PdfReadError, OSError, ValueError, TypeError, KeyError, IndexError) as exc:
        return [Diagnostic("error", "pdf-read-error", f"No se pudo inspeccionar el PDF «{pdf_path}»: {exc}.", source)]
    intentional = _intentional_blank_pages(html_document, texts, blank_pages) if html_document else set()
    for number in sorted(blank_pages - intentional):
        diagnostics.append(Diagnostic("warning", "pdf-blank-page", "La página no contiene texto ni gráficos detectables dentro del área imprimible y no corresponde a un grupo de saltos explícitos reconocido.", source, page=number))
    return diagnostics
