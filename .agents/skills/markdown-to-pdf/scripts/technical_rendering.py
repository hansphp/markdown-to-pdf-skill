"""Render technical placeholders with pinned, offline browser assets."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]


class TechnicalRenderingError(ValueError):
    """Technical content cannot be rendered faithfully; do not publish it."""


class _RequirementsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.requirements = {"mermaid": False, "math": False}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "img" and "data-document-mermaid" in attrs:
            self.requirements["mermaid"] = True
        if tag in {"span", "div"} and attrs.get("data-document-math") in {"inline", "display"}:
            self.requirements["math"] = True

    handle_startendtag = handle_starttag


def technical_requirements(html_document: str) -> dict[str, bool]:
    parser = _RequirementsParser()
    parser.feed(html_document)
    parser.close()
    return parser.requirements


def has_technical_content(html_document: str) -> bool:
    return any(technical_requirements(html_document).values())


def _verified_assets(skill_dir: Path, packages: list[str]) -> dict[str, dict[str, bytes]]:
    """Read only requested packages; hashes also diagnose incomplete skill copies."""
    vendor = Path(skill_dir) / "assets" / "vendor"
    try:
        manifest = json.loads((vendor / "manifest.json").read_text(encoding="utf-8"))
        result = {}
        for package in packages:
            files = manifest["packages"][package]["files"]
            result[package] = {}
            for filename, digest in files.items():
                relative = Path(filename)
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError("ruta inválida en manifest.json")
                path = vendor / package / relative
                contents = path.read_bytes()
                if hashlib.sha256(contents).hexdigest() != digest:
                    raise ValueError(f"integridad SHA-256 incorrecta: {path}")
                result[package][filename] = contents
        return result
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise TechnicalRenderingError(
            f"No se pudieron cargar los recursos técnicos locales: {exc}. "
            "Restaure assets/vendor completo desde el skill; no se descargan recursos durante la conversión."
        ) from exc


def _embedded_math_css(files: dict[str, bytes]) -> str:
    css = files["katex.min.css"].decode("utf-8")

    def embed(match):
        filename = match.group(1).strip("\"'")
        if filename not in files:
            raise TechnicalRenderingError(f"Falta la fuente local de KaTeX: {filename}.")
        extension = Path(filename).suffix.lstrip(".")
        encoded = base64.b64encode(files[filename]).decode("ascii")
        return f'url("data:font/{extension};base64,{encoded}")'

    return re.sub(r"url\(([^)]+)\)", embed, css)


_RENDER = r"""async () => {
    const lineOf = element => element.closest('[data-source-line]')?.getAttribute('data-source-line');
    const failure = (kind, element, error) => ({kind, line: lineOf(element), message: String(error?.message || error)});
    const result = {mermaid: 0, math: 0};
    await document.fonts.ready;
    if (document.querySelector('img[data-document-mermaid]:not([data-document-rendered])')) {
        mermaid.initialize({
            startOnLoad: false, securityLevel: 'strict', suppressErrorRendering: true,
            htmlLabels: false, flowchart: {htmlLabels: false}, layout: 'dagre',
            fontFamily: 'Arial, sans-serif', deterministicIds: true,
            maxTextSize: 50000, maxEdges: 500,
            secure: ['secure', 'securityLevel', 'startOnLoad', 'maxTextSize', 'maxEdges',
                'suppressErrorRendering', 'htmlLabels', 'flowchart', 'layout',
                'fontFamily', 'themeCSS', 'dompurifyConfig']
        });
        let serial = 0;
        for (const element of document.querySelectorAll('img[data-document-mermaid]:not([data-document-rendered])')) {
            const source = element.getAttribute('data-document-mermaid');
            let host;
            try {
                if (!source.trim()) throw new Error('El bloque Mermaid está vacío.');
                if (source.length > 50000) throw new Error('El bloque Mermaid supera 50 000 caracteres; divídalo en diagramas menores.');
                host = document.createElement('div');
                host.style.cssText = 'position:absolute;left:-100000px;top:0;width:1000px;visibility:hidden';
                document.body.append(host);
                let renderId;
                do { renderId = 'mdpdf-mermaid-render-' + (++serial); } while (document.getElementById(renderId));
                const {svg, diagramType} = await mermaid.render(renderId, source, host);
                if (diagramType === 'journey') {
                    return {...result, error: {
                        ...failure('Mermaid', element,
                            'El tipo «journey» no es compatible con este conversor: genera etiquetas HTML dentro del SVG. ' +
                            'Exporte el diagrama como imagen PNG local y enlácela desde el Markdown.'),
                        code: 'mermaid-journey-unsupported'
                    }};
                }
                const parsed = new DOMParser().parseFromString(svg, 'image/svg+xml');
                if (parsed.querySelector('parsererror')) throw new Error('Mermaid produjo SVG inválido.');
                const drawing = parsed.documentElement;
                // Image-backed SVG cannot faithfully display foreignObject labels.
                if (drawing.querySelector('foreignObject')) throw new Error('Este diagrama necesita etiquetas HTML no compatibles; use etiquetas de texto SVG.');
                const dimensions = drawing.getAttribute('viewBox')?.trim().split(/[\s,]+/).map(Number);
                if (!dimensions || dimensions.length !== 4 || !dimensions.every(Number.isFinite) || dimensions[2] <= 0 || dimensions[3] <= 0)
                    throw new Error('Mermaid produjo un diagrama sin dimensiones imprimibles.');
                drawing.setAttribute('width', String(dimensions[2]));
                drawing.setAttribute('height', String(dimensions[3]));
                drawing.style.maxWidth = 'none';
                const serialized = new XMLSerializer().serializeToString(drawing);
                element.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(serialized);
                await element.decode();
                if (!element.naturalWidth || !element.naturalHeight) throw new Error('El diagrama no se pudo cargar como imagen.');
                element.setAttribute('data-document-rendered', 'true');
                result.mermaid += 1;
            } catch (error) {
                return {...result, error: failure('Mermaid', element, error)};
            } finally {
                host?.remove();
            }
        }
    }
    for (const element of document.querySelectorAll('[data-document-math]:not([data-document-rendered])')) {
        try {
            let deniedCommand = null;
            katex.render(element.textContent, element, {
                displayMode: element.getAttribute('data-document-math') === 'display',
                throwOnError: true, strict: 'error',
                trust: context => { deniedCommand = context.command; return false; },
                output: 'htmlAndMathml', maxExpand: 1000, maxSize: 100, macros: {}
            });
            // KaTeX may represent unsupported, untrusted commands in red instead of throwing.
            if (deniedCommand || element.querySelector('.katex-error, .katex-unsupported'))
                throw new Error('La fórmula contiene un comando no admitido' + (deniedCommand ? ': ' + deniedCommand : '') + '.');
            element.setAttribute('data-document-rendered', 'true');
            result.math += 1;
        } catch (error) {
            return {...result, error: failure('Fórmula', element, error)};
        }
    }
    await document.fonts.ready;
    const failedFonts = Array.from(document.fonts).filter(font => font.family.startsWith('KaTeX') && font.status === 'error');
    if (failedFonts.length) return {...result, error: {kind: 'Fuentes KaTeX', message: 'No se cargaron las fuentes locales: ' + failedFonts.map(font => font.family).join(', ')}};
    return result;
}"""


def render_technical(page, skill_dir: Path = SKILL_DIR) -> dict[str, int]:
    """Render before measuring or paginating; never use a network dependency.

    The caller already opened its local HTML and selected print media. Source
    placeholders and their IDs remain in place, preserving figure destinations.
    Repeated calls do not re-render successful elements or load unused assets.
    """
    pending = page.evaluate("""() => ({
        mermaid: !!document.querySelector('img[data-document-mermaid]:not([data-document-rendered])'),
        math: !!document.querySelector('[data-document-math]:not([data-document-rendered])'),
        line: document.querySelector('img[data-document-mermaid]:not([data-document-rendered]), [data-document-math]:not([data-document-rendered])')?.closest('[data-source-line]')?.getAttribute('data-source-line')
    })""")
    packages = [name for kind, name in (("mermaid", "mermaid"), ("math", "katex")) if pending[kind]]
    if not packages:
        return {"mermaid": 0, "math": 0}
    try:
        assets = _verified_assets(skill_dir, packages)
    except TechnicalRenderingError as exc:
        location = f" (línea {pending['line']})" if pending.get("line") else ""
        raise TechnicalRenderingError(f"Contenido técnico{location}: {exc}") from exc
    try:
        if pending["mermaid"]:
            page.add_script_tag(content=assets["mermaid"]["mermaid.min.js"].decode("utf-8"))
        if pending["math"]:
            page.add_style_tag(content=_embedded_math_css(assets["katex"]))
            page.add_script_tag(content=assets["katex"]["katex.min.js"].decode("utf-8"))
        result = page.evaluate(_RENDER)
    except Exception as exc:
        raise TechnicalRenderingError(f"No se pudo renderizar el contenido técnico con los recursos locales: {exc}") from exc
    error = result.pop("error", None)
    if error:
        location = f" (línea {error['line']})" if error.get("line") else ""
        if error.get("code") == "mermaid-journey-unsupported":
            raise TechnicalRenderingError(
                f"{error['kind']}{location} [{error['code']}]: {error['message']}"
            )
        raise TechnicalRenderingError(
            f"{error['kind']}{location}: {error['message']}. Corrija la sintaxis del Markdown y vuelva a convertir."
        )
    return result


_READ_TEXT_LABELS = r"""request => {
    const clean = text => text.replace(/[\u200b\u200c\u200d\ufeff]/g, '')
        .replace(/\u2061/g, ' ').replace(/\u2062/g, '·').replace(/\u2063/g, ', ')
        .replace(/\u2064/g, '+').replace(/\s+/g, ' ').trim();
    const children = node => Array.from(node.children);
    const matrixRows = node => children(node).map(row => children(row).map(mathText).join(', ')).join('; ');
    const compoundBase = node => node && (node.localName === 'mfrac'
        || (node.localName === 'mrow' && children(node).filter(child => child.localName !== 'mspace').length > 1)
        || (['mstyle', 'mpadded'].includes(node.localName) && children(node).some(compoundBase)));
    const operatorBase = node => node && (node.getAttribute('movablelimits') === 'true'
        || node.getAttribute('largeop') === 'true' || /^[∑∏∐⋂⋃∫∬∭∮]$/.test(node.textContent));
    const mathText = node => {
        if (node.nodeType === Node.TEXT_NODE) return node.textContent;
        const tag = node.localName;
        const parts = children(node);
        const read = index => parts[index] ? mathText(parts[index]) : '';
        const base = () => compoundBase(parts[0]) ? '(' + read(0) + ')' : read(0);
        switch (tag) {
            case 'annotation': case 'annotation-xml': case 'mphantom': return '';
            case 'mo': return node.textContent.replace(/[\u20d6\u20d7\u20e1]/g,
                symbol => ({'\u20d6': '←', '\u20d7': '→', '\u20e1': '↔'})[symbol]);
            case 'semantics': return parts.find(child => !['annotation', 'annotation-xml'].includes(child.localName))
                ? mathText(parts.find(child => !['annotation', 'annotation-xml'].includes(child.localName))) : '';
            case 'mfrac': return '(' + read(0) + ')/(' + read(1) + ')';
            case 'msup': return base() + '^(' + read(1) + ')';
            case 'msub': return base() + '_(' + read(1) + ')';
            case 'msubsup': return base() + '_(' + read(1) + ')^(' + read(2) + ')';
            case 'mover': return operatorBase(parts[0]) ? base() + '^(' + read(1) + ')'
                : 'over(' + read(0) + ', ' + read(1) + ')';
            case 'munder': return operatorBase(parts[0]) ? base() + '_(' + read(1) + ')'
                : 'under(' + read(0) + ', ' + read(1) + ')';
            case 'munderover': return operatorBase(parts[0]) ? base() + '_(' + read(1) + ')^(' + read(2) + ')'
                : 'over(under(' + read(0) + ', ' + read(1) + '), ' + read(2) + ')';
            case 'msqrt': return 'sqrt(' + parts.map(mathText).join('') + ')';
            case 'mroot': return 'root(' + read(1) + ', ' + read(0) + ')';
            case 'mtable': return '[' + matrixRows(node) + ']';
            case 'mspace': return ' ';
            case 'mrow': {
                // Delimited matrices already have their visible brackets.
                const hasFence = parts.some(child => child.localName === 'mo'
                    && child.getAttribute('fence') === 'true');
                return parts.map(child => hasFence && child.localName === 'mtable'
                    ? matrixRows(child) : mathText(child)).join('');
            }
            default: return Array.from(node.childNodes).map(mathText).join('');
        }
    };
    const visible = node => node.checkVisibility({checkOpacity: true, checkVisibilityCSS: true})
        && !node.closest('[aria-hidden="true"]');
    const textOf = (node, native = false) => {
        if (node.nodeType === Node.TEXT_NODE) return node.textContent;
        if (node.nodeType !== Node.ELEMENT_NODE) return '';
        if (node.matches('script, style, template, .katex-html, annotation, annotation-xml')) return '';
        if (request.headings && !visible(node)) return '';
        if (node.matches('[data-document-math], .katex')) {
            if (native) return node.querySelector('[data-document-bookmark-math]')?.textContent || '';
            const math = node.querySelector('.katex-mathml math, math');
            if (!math) throw new Error('La fórmula debe renderizarse antes de obtener su etiqueta textual.');
            return mathText(math);
        }
        if (node.getAttribute('role') === 'doc-noteref') {
            const number = clean(Array.from(node.childNodes).map(child => textOf(child, native)).join(''));
            return native ? number : '[' + number + ']';
        }
        if (node.localName === 'img') return node.getAttribute('alt') || '';
        if (node.localName === 'br') return ' ';
        return Array.from(node.childNodes).map(child => textOf(child, native)).join('');
    };
    if (request.prepare) {
        for (const heading of document.querySelectorAll('h1, h2, h3, h4, h5, h6')) {
            if (!visible(heading) || clean(textOf(heading, true))) continue;
            for (const formula of heading.querySelectorAll('[data-document-math]')) {
                const math = formula.querySelector('.katex-mathml math');
                const rendered = formula.querySelector('.katex-html');
                if (!math || !rendered) continue;
                rendered.removeAttribute('aria-hidden');
                rendered.setAttribute('role', 'math');
                rendered.setAttribute('aria-label', clean(mathText(math)));
                rendered.setAttribute('data-document-bookmark-math', 'true');
                formula.querySelector('.katex-mathml').setAttribute('aria-hidden', 'true');
            }
        }
    }
    if (request.headings) {
        return Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6')).filter(visible)
            .map(element => ({id: element.id, title: clean(textOf(element)),
                level: Number(element.localName.slice(1)),
                needs_update: !!element.querySelector('[data-document-math], [role="doc-noteref"]'),
                native_title: textOf(element, true).replace(/\s+/g, ' ').trim()}))
            .filter(heading => heading.title);
    }
    const result = {};
    for (const [key, identifier] of Object.entries(request.mapping)) {
        const element = document.getElementById(identifier);
        if (element) result[key] = clean(textOf(element));
    }
    return result;
}"""


def read_text_labels(page, mapping: dict[str, str]) -> dict[str, str]:
    """Read labels by DOM ID after technical rendering, without changing the page.

    ``mapping`` assigns a caller-defined result key to an element ID; missing
    elements are omitted. Math is linearized from KaTeX's MathML, excluding its
    TeX annotation and duplicated HTML: ``(a)/(b)``, ``x^(2)``, ``x_(i)``,
    ``sqrt(x)``, ``root(3, x)`` and matrices with comma-separated columns and
    semicolon-separated rows. Note calls become ``[n]`` exactly once.

    The labels are suitable for plain-text footers and PDF bookmark titles.
    Chromium does not use a heading's aria-label for its native PDF bookmark;
    the caller must update bookmark titles while retaining their destinations.
    """
    if not mapping:
        return {}
    try:
        return page.evaluate(_READ_TEXT_LABELS, {"mapping": mapping})
    except Exception as exc:
        raise TechnicalRenderingError(f"No se pudieron obtener las etiquetas textuales del documento: {exc}") from exc


def read_heading_labels(page) -> list[dict]:
    """Read visible, nonempty H1–H6 labels in DOM order, including generated ones.

    Each record contains ``id``, ``title``, ``level`` and ``needs_update`` (math
    or note calls). ``native_title`` omits formulas and uses bare note numbers,
    matching Chromium's native outline text; an empty native title identifies
    formula-only headings for which Chromium creates no bookmark. Hidden and
    aria-hidden headings are excluded without modifying page content or IDs.
    """
    try:
        return page.evaluate(_READ_TEXT_LABELS, {"headings": True})
    except Exception as exc:
        raise TechnicalRenderingError(f"No se pudieron obtener los títulos de los marcadores: {exc}") from exc


def prepare_heading_labels(page) -> list[dict]:
    """Let Chromium create native destinations for formula-only headings.

    Only those headings expose KaTeX's rendered HTML as a named ``math`` node;
    the redundant MathML accessibility copy is hidden, while its DOM and the
    visible formula stay intact. Formula labels continue to use that MathML.
    No text or geometry is inserted. Repeated calls are idempotent. Return the
    same records as ``read_heading_labels`` for the caller's bookmark update.
    """
    try:
        return page.evaluate(_READ_TEXT_LABELS, {"headings": True, "prepare": True})
    except Exception as exc:
        raise TechnicalRenderingError(f"No se pudieron preparar los títulos de los marcadores: {exc}") from exc
