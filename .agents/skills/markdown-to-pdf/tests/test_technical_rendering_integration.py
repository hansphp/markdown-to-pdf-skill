"""Real-browser rendering with offline assets, no placeholder publication."""

import html
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote


SKILL = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("mdpdf_technical_browser_converter", SKILL / "scripts" / "convert_markdown_to_pdf.py")
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)
technical = converter.load_support_module("technical_rendering")


@unittest.skipUnless(os.environ.get("MDPDF_BROWSER_TESTS") == "1", "Requiere MDPDF_BROWSER_TESTS=1")
class TechnicalBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.playwright = sync_playwright().start()
        browsers = converter.find_browsers()
        cls.browser = cls.playwright.chromium.launch(**({"executable_path": str(browsers[0])} if browsers else {}), headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.requests = []
        self.page.on("request", lambda request: self.requests.append(request.url))
        self.page.route("http://**/*", lambda route: route.abort())
        self.page.route("https://**/*", lambda route: route.abort())

    def load(self, body):
        css = (SKILL / "assets" / "print.css").read_text()
        self.page.set_content('<!doctype html><html><head><style>' + css + '</style></head><body><main>' + body + '</main></body></html>')
        self.page.emulate_media(media="print")

    def diagram(self, source, line=11):
        return '<figure id="figure-1"><img id="fig:flow" alt="Flujo" data-source-line="' + str(line) + '" data-document-mermaid="' + html.escape(source, quote=True) + '"><figcaption>Figura 1. Flujo</figcaption></figure>'

    def formula(self, source, mode="inline", line=23):
        return '<span data-source-line="' + str(line) + '" data-document-math="' + mode + '">' + html.escape(source) + '</span>'

    def test_mermaid_and_math_finish_offline_and_preserve_figure_identity(self):
        self.load(self.diagram('flowchart TD\n A[Inicio] --> B{¿Listo?}\n B -->|Sí| C[Fin]\n B -->|No| A') + '<p>Resultado: ' + self.formula(r'\frac{a_1+b^2}{\sqrt{c}}') + '</p>' + self.formula(r'\sum_{i=1}^{n} i = \frac{n(n+1)}{2}', "display"))
        self.assertEqual(technical.render_technical(self.page), {"mermaid": 1, "math": 2})
        image = self.page.locator('img[id="fig:flow"]')
        self.assertTrue(image.evaluate("img => img.complete && img.naturalWidth > 100 && img.naturalHeight > 100"))
        svg = unquote(image.get_attribute("src").split(",", 1)[1])
        self.assertIn("Inicio", svg)
        self.assertIn("¿Listo?", svg)
        self.assertNotIn("foreignObject", svg)
        self.assertEqual(self.page.locator("figcaption").inner_text(), "Figura 1. Flujo")
        self.assertEqual(self.page.locator(".katex").count(), 2)
        self.assertEqual(self.page.locator("math").count(), 2)
        self.assertEqual(self.page.locator(".katex-display").count(), 1)
        self.assertTrue(self.page.evaluate("Array.from(document.fonts).some(font => font.family.startsWith('KaTeX') && font.status === 'loaded')"))
        self.assertEqual([url for url in self.requests if url.startswith(("http:", "https:", "file:"))], [])
        self.assertEqual(technical.render_technical(self.page), {"mermaid": 0, "math": 0})

    def test_invalid_mermaid_reports_source_line_without_error_drawing(self):
        for source in ("flowchart TD\n A[unfinished", "journeys\n title Recorrido"):
            with self.subTest(source=source):
                self.load(self.diagram(source, line=37))
                with self.assertRaisesRegex(technical.TechnicalRenderingError, r"Mermaid \(línea 37\)") as raised:
                    technical.render_technical(self.page)
                self.assertNotIn('mermaid-journey-unsupported', str(raised.exception))
                self.assertEqual(self.page.locator("svg").count(), 0)
                self.assertEqual(self.page.locator('[data-document-rendered]').count(), 0)

    def test_journey_reports_a_supported_syntax_but_unsupported_diagram_type(self):
        journey = 'journey\n title Revisión del documento\n section Preparar\n  Leer requisitos: 5: Usuario'
        prefixes = ('', '%% Comentario previo\n', '%%{init: {"theme": "neutral"}}%%\n',
                    '---\ntitle: Experiencia\nconfig:\n  theme: neutral\n---\n'
                    '%%{init: {"theme": "neutral"}}%%\n%% Comentario previo\n')
        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                self.load(self.diagram(prefix + journey, line=37))
                with self.assertRaisesRegex(technical.TechnicalRenderingError,
                                            r'Mermaid \(línea 37\).*mermaid-journey-unsupported') as raised:
                    technical.render_technical(self.page)
                message = str(raised.exception)
                self.assertIn('journey', message)
                self.assertIn('HTML', message)
                self.assertIn('PNG', message)
                self.assertNotIn('Corrija la sintaxis', message)
                self.assertEqual(self.page.locator('svg').count(), 0)
                self.assertEqual(self.page.locator('[data-document-rendered]').count(), 0)
        self.assertEqual([url for url in self.requests if url.startswith(('http:', 'https:'))], [])

    def test_journey_in_another_diagrams_labels_does_not_reject_it(self):
        source = ('---\ntitle: journey\n---\n%% journey\nflowchart LR\n'
                  ' journey["journey"] --> B[Fin]')
        self.load(self.diagram(source))
        self.assertEqual(technical.render_technical(self.page)['mermaid'], 1)
        svg = unquote(self.page.locator('img').get_attribute('src').split(',', 1)[1])
        self.assertIn('journey', svg)
        self.assertNotIn('foreignObject', svg)

    def test_missing_assets_report_original_source_line(self):
        self.load(self.formula(r'x^2', line=58))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(technical.TechnicalRenderingError, r"Contenido técnico \(línea 58\).+Restaure assets/vendor"):
                technical.render_technical(self.page, Path(directory))
        self.assertEqual(self.page.locator('.katex').count(), 0)

    def test_invalid_math_and_external_commands_fail_with_source_line(self):
        for source in (r'\frac{1}', r'\notARealCommand', r'\href{https://example.com}{link}', r'\includegraphics{https://example.com/image.png}'):
            with self.subTest(source=source):
                self.load(self.formula(source, line=42))
                with self.assertRaisesRegex(technical.TechnicalRenderingError, r"Fórmula \(línea 42\)"):
                    technical.render_technical(self.page)
                self.assertEqual(self.page.locator('[data-document-rendered]').count(), 0)
        self.assertEqual([url for url in self.requests if url.startswith(("http:", "https:"))], [])

    def test_sequence_and_class_diagrams_keep_svg_text(self):
        for source, label in (("sequenceDiagram\n participant Usuario\n participant Portal\n Usuario->>Portal: Consulta\n Portal-->>Usuario: Respuesta", "Consulta"), ("classDiagram\n class Documento {\n +String titulo\n +exportar()\n }", "Documento")):
            with self.subTest(source=source):
                self.load(self.diagram(source))
                self.assertEqual(technical.render_technical(self.page)["mermaid"], 1)
                svg = unquote(self.page.locator("img").get_attribute("src").split(",", 1)[1])
                self.assertIn(label, svg)
                self.assertNotIn("foreignObject", svg)

    def test_rendered_content_prints_a_real_pdf(self):
        from pypdf import PdfReader
        self.load('<h1>Contenido técnico</h1>' + self.diagram("flowchart LR\n A[Uno] --> B[Dos]") + '<p>Fórmula ' + self.formula(r'E=mc^2') + '</p>')
        technical.render_technical(self.page)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "technical.pdf"
            self.page.pdf(path=str(path), format="A4", print_background=True)
            pdf = PdfReader(path)
            self.assertEqual(len(pdf.pages), 1)
            text = pdf.pages[0].extract_text()
            for expected in ("Contenido técnico", "Figura 1. Flujo", "Uno", "Dos", "Fórmula"):
                self.assertIn(expected, text)

    def test_text_labels_linearize_mathml_without_tex_or_duplicated_html(self):
        cases = {
            'fraction': (r'\frac{a}{b}', '(a)/(b)'),
            'power': ('x^2', 'x^(2)'),
            'subscript': ('x_i', 'x_(i)'),
            'combined': ('x_i^2', 'x_(i)^(2)'),
            'root': (r'\sqrt{x}', 'sqrt(x)'),
            'nth-root': (r'\sqrt[3]{x}', 'root(3, x)'),
            'symbols': (r'\alpha + \beta \leq \pi', 'α+β≤π'),
            'sum': (r'\sum_{i=1}^{n} i', '∑_(i=1)^(n)i'),
            'matrix': (r'\begin{bmatrix} a & b \\ c & d \end{bmatrix}', '[a, b; c, d]'),
            'nested': (r'\frac{x_i^2}{\sqrt{a+b}}', '(x_(i)^(2))/(sqrt(a+b))'),
            'compound-power': ('{a+b}^2', '(a+b)^(2)'),
            'compound-subscript': ('{a+b}_i', '(a+b)_(i)'),
            'fraction-power': (r'\frac{a}{b}^2', '((a)/(b))^(2)'),
            'bar': (r'\bar{x}', 'over(x, ˉ)'),
            'vector': (r'\vec{x}', 'over(x, →)'),
            'underline': (r'\underline{x}', 'under(x, ‾)'),
        }
        self.load(''.join('<h2 id="' + key + '">' + self.formula(tex) + '</h2>'
                          for key, (tex, _) in cases.items()))
        technical.render_technical(self.page)
        before = self.page.locator('main').inner_html()
        labels = technical.read_text_labels(self.page, {key: key for key in cases})
        self.assertEqual(labels, {key: expected for key, (_, expected) in cases.items()})
        self.assertEqual(self.page.locator('main').inner_html(), before)

    def test_text_labels_preserve_resolved_references_and_number_each_note_once(self):
        self.load('<h2 id="title">Resultado <em>' + self.formula('x^2')
            + '</em>: <a href="#table">Tabla 2</a><sup class="document-footnote-reference">'
            '<a role="doc-noteref" href="#note">1</a></sup></h2>')
        technical.render_technical(self.page)
        self.assertEqual(technical.read_text_labels(self.page, {'titulo': 'title', 'missing': 'absent'}),
                         {'titulo': 'Resultado x^(2): Tabla 2[1]'})

    def test_text_label_reader_rejects_unrendered_math_instead_of_returning_tex(self):
        self.load('<h2 id="title">Fórmula ' + self.formula(r'\frac{a}{b}') + '</h2>')
        with self.assertRaisesRegex(technical.TechnicalRenderingError, 'debe renderizarse'):
            technical.read_text_labels(self.page, {'titulo': 'title'})

    def test_metadata_text_is_retained_when_its_body_heading_is_hidden(self):
        self.load('<h1 id="title" style="display:none">Informe ' + self.formula('x^2') + '</h1>')
        technical.render_technical(self.page)
        self.assertEqual(technical.read_text_labels(self.page, {'titulo': 'title'}), {'titulo': 'Informe x^(2)'})
        self.assertEqual(technical.read_heading_labels(self.page), [])

    def test_heading_labels_include_generated_headings_and_match_native_outline_order(self):
        from pypdf import PdfReader
        self.load('<h1 id="title">Repetido</h1><h2 id="repeated">Repetido</h2>'
            '<h2 id="empty"></h2><h2 id="blank">   </h2>'
            '<h2 style="display:none">No visible</h2><h2 style="visibility:hidden">Oculto</h2>'
            '<h2 style="opacity:0">Transparente</h2><h2 aria-hidden="true">No accesible</h2>'
            '<nav><h2 id="toc">Índice</h2></nav>'
            '<h3 id="note" data-document-role="note-content">Detalle de la nota</h3>'
            '<h2 id="formula">Energía ' + self.formula('E=mc^2')
            + '<sup><a role="doc-noteref" href="#note">1</a></sup></h2>')
        technical.render_technical(self.page)
        labels = technical.read_heading_labels(self.page)
        self.assertEqual([item['id'] for item in labels], ['title', 'repeated', 'toc', 'note', 'formula'])
        self.assertEqual([item['level'] for item in labels], [1, 2, 2, 3, 2])
        self.assertEqual([item['needs_update'] for item in labels], [False, False, False, False, True])
        self.assertEqual(labels[-1]['title'], 'Energía E=mc^(2)[1]')
        self.assertEqual(labels[-1]['native_title'], 'Energía 1')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'headings.pdf'
            self.page.pdf(path=str(path), format='A4', outline=True, tagged=True)

            def titles(outline):
                for item in outline:
                    if isinstance(item, list):
                        yield from titles(item)
                    else:
                        yield item['/Title']

            self.assertEqual(list(titles(PdfReader(path).outline)), [item['native_title'] for item in labels])

    def test_formula_only_heading_has_a_text_label_even_when_chromium_omits_its_bookmark(self):
        self.load('<h2 id="formula">' + self.formula(r'\frac{x}{y}') + '</h2>')
        technical.render_technical(self.page)
        self.assertEqual(technical.read_heading_labels(self.page), [
            {'id': 'formula', 'title': '(x)/(y)', 'native_title': '', 'level': 2, 'needs_update': True},
        ])

    def test_prepared_formula_only_heading_has_native_bookmark_and_one_named_accessible_math(self):
        from pypdf import PdfReader
        self.load('<h1 id="title">Informe</h1><h2 id="formula">' + self.formula(r'\frac{x^2}{y_i}')
            + '</h2><h2 id="mixed">Energía ' + self.formula('E=mc^2') + '</h2>')
        technical.render_technical(self.page)
        before = self.page.locator('main').screenshot()
        labels = technical.prepare_heading_labels(self.page)
        self.assertEqual(labels[1]['title'], '(x^(2))/(y_(i))')
        self.assertTrue(labels[1]['native_title'])
        self.assertEqual(technical.prepare_heading_labels(self.page), labels)
        self.assertEqual(self.page.locator('main').screenshot(), before)
        self.assertEqual(self.page.locator('#formula .katex-mathml').get_attribute('aria-hidden'), 'true')
        self.assertEqual(self.page.locator('#mixed .katex-html').get_attribute('aria-hidden'), 'true')
        self.assertEqual(self.page.locator('#formula math').count(), 1)
        session = self.page.context.new_cdp_session(self.page)
        self.addCleanup(session.detach)
        nodes = session.send('Accessibility.getFullAXTree')['nodes']
        labelled_math = [node for node in nodes if not node['ignored']
                         and node.get('role', {}).get('value') == 'math'
                         and node.get('name', {}).get('value') == '(x^(2))/(y_(i))']
        self.assertEqual(len(labelled_math), 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'formula-heading.pdf'
            self.page.pdf(path=str(path), format='A4', outline=True, tagged=True)
            pdf = PdfReader(path)
            outline = [pdf.outline[0]] + pdf.outline[1]
            self.assertEqual([item['/Title'].strip() for item in outline], [item['native_title'] for item in labels])
            self.assertTrue(all(pdf.get_destination_page_number(item) == 0 for item in outline))


if __name__ == "__main__":
    unittest.main()
