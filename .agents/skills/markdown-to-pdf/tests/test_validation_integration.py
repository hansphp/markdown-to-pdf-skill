"""Real Chromium checks for failed images, print geometry and blank pages."""

import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("mdpdf_validation_integration", SKILL / "scripts" / "convert_markdown_to_pdf.py")
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)
validation = converter.load_support_module("document_validation")


@unittest.skipUnless(os.environ.get("MDPDF_BROWSER_TESTS") == "1", "Requiere MDPDF_BROWSER_TESTS=1")
class ValidationIntegrationTests(unittest.TestCase):
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
        directory = tempfile.TemporaryDirectory(prefix="mdpdf-validation-browser-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.source = self.root / "document.md"
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)

    def load(self, body, extra_css=""):
        document = '<!doctype html><html><head><style>' + (SKILL / "assets" / "print.css").read_text() + '\n@page {size: A4; margin:20mm 16mm 18mm;}\n' + extra_css + '</style></head><body><main>' + body + '</main></body></html>'
        html = self.root / "document.html"
        html.write_text(document, encoding="utf-8")
        self.page.goto(html.as_uri(), wait_until="load")
        self.page.emulate_media(media="print")
        self.page.evaluate("document.fonts.ready")
        return document

    def test_existing_but_invalid_image_reports_source_line_and_restores_viewport(self):
        (self.root / "invalid.png").write_bytes(b"This is not a PNG")
        document = self.load('<p data-source-line="14"><img src="invalid.png" alt="Broken image"></p>')
        self.assertEqual(validation.validate_html(document, self.source), [])
        viewport = self.page.viewport_size
        issues = validation.inspect_page(self.page, self.source)
        self.assertEqual([(issue.code, issue.severity, issue.line) for issue in issues], [("image-load-failed", "error", 14)])
        self.assertEqual(self.page.viewport_size, viewport)

    def test_wide_and_unbreakable_tall_content_warns_but_long_table_can_paginate(self):
        self.load('<p id="wide" data-source-line="6">Wide block</p><pre id="tall" data-source-line="9">Tall block</pre><table id="long"><tbody>' + '<tr><td>Ordinary row</td></tr>' * 90 + '</tbody></table>', '#wide {width:300mm} #tall {height:400mm}')
        issues = validation.inspect_page(self.page, self.source)
        self.assertIn(("layout-horizontal-overflow", 6), [(issue.code, issue.line) for issue in issues])
        self.assertIn(("layout-unbreakable-height", 9), [(issue.code, issue.line) for issue in issues])
        self.assertFalse(any(issue.selector == "table#long" for issue in issues))

    def test_vertical_clipping_modes_report_dimensions_source_and_actual_missing_pdf_text(self):
        from pypdf import PdfReader

        lines = "\n".join(f"LINEA-{number:02d}" for number in range(1, 21))
        for overflow in ("hidden", "clip", "auto", "scroll"):
            with self.subTest(overflow=overflow):
                self.load('<pre id="clipped" data-source-line="17">' + lines + '</pre>',
                          '#clipped {height:12mm; overflow:' + overflow + '}')
                issues = validation.inspect_page(self.page, self.source)
                clipping = [issue for issue in issues if issue.code == "layout-vertical-clipping"]
                self.assertEqual(len(clipping), 1)
                self.assertEqual((clipping[0].severity, clipping[0].line, clipping[0].selector),
                                 ("warning", 17, "pre#clipped"))
                self.assertRegex(clipping[0].message, r"contenido \d+ px; altura visible \d+ px")
                self.assertIn("overflow-y: " + overflow, clipping[0].message)
                pdf = self.root / (overflow + ".pdf")
                self.page.pdf(path=str(pdf), print_background=True, prefer_css_page_size=True)
                with PdfReader(pdf) as reader:
                    text = " ".join(page.extract_text() or "" for page in reader.pages)
                self.assertIn("LINEA-01", text)
                self.assertNotIn("LINEA-20", text)

    def test_zero_height_and_max_height_clipping_are_detected_before_empty_box_filter(self):
        for size in ("height:0", "max-height:0", "max-height:12mm"):
            with self.subTest(size=size):
                self.load('<pre id="clipped" data-source-line="8">' + "Línea\n" * 20 + '</pre>',
                          '#clipped {' + size + '; padding:0; border:0; overflow:hidden}')
                issues = validation.inspect_page(self.page, self.source)
                clipping = [issue for issue in issues if issue.code == "layout-vertical-clipping"]
                self.assertEqual([(issue.selector, issue.line) for issue in clipping], [("pre#clipped", 8)])

    def test_main_and_nonpropagated_body_clipping_are_reported_once(self):
        for selector, extra in (("main", ""), ("body", "html {overflow:hidden}")):
            with self.subTest(selector=selector):
                self.load('<pre data-source-line="8">' + "Línea\n" * 20 + '</pre>',
                          extra + selector + ' {height:12mm;overflow:hidden}')
                issues = validation.inspect_page(self.page, self.source)
                self.assertEqual([issue.selector for issue in issues if issue.code == "layout-vertical-clipping"], [selector])

    def test_visible_overflow_and_viewport_propagated_body_overflow_keep_all_pdf_text(self):
        from pypdf import PdfReader

        lines = "\n".join(f"LINEA-{number:02d}" for number in range(1, 21))
        for css in ("pre {height:12mm;overflow:visible}", "body {height:12mm;overflow:hidden}"):
            with self.subTest(css=css):
                self.load('<pre>' + lines + '</pre>', css)
                issues = validation.inspect_page(self.page, self.source)
                self.assertFalse(any(issue.code == "layout-vertical-clipping" for issue in issues))
                pdf = self.root / "visible.pdf"
                self.page.pdf(path=str(pdf), print_background=True, prefer_css_page_size=True)
                with PdfReader(pdf) as reader:
                    self.assertIn("LINEA-20", " ".join(page.extract_text() or "" for page in reader.pages))

    def test_exactly_fitting_content_does_not_warn_for_any_overflow_mode(self):
        for overflow in ("hidden", "clip", "auto", "scroll"):
            with self.subTest(overflow=overflow):
                self.load('<div id="fit">Primera<br>Segunda</div>',
                          '#fit {font:12px/20px Arial;height:40px;padding:0;overflow:' + overflow + '}')
                self.assertEqual(validation.inspect_page(self.page, self.source), [])

    def test_katex_accessibility_copy_is_ignored_but_clipped_visible_math_is_reported(self):
        technical = converter.load_support_module("technical_rendering")
        self.load(r'<p data-source-line="23">Resultado: <span data-document-math="inline">\frac{a}{b}</span>.</p>')
        technical.render_technical(self.page)
        self.assertEqual(validation.inspect_page(self.page, self.source), [])
        self.page.locator(".katex-html").evaluate("element => element.id = 'visible-math'")
        self.page.add_style_tag(content="#visible-math {display:inline-block;height:1px;overflow:hidden}")
        issues = validation.inspect_page(self.page, self.source)
        clipping = [issue for issue in issues if issue.code == "layout-vertical-clipping"]
        self.assertEqual([(issue.selector, issue.line) for issue in clipping], [("span#visible-math", 23)])

    def test_positioned_element_outside_top_is_identified(self):
        self.load('<p>Normal text</p><p id="outside" data-source-line="4">Clipped</p>', '#outside {position:absolute; top:-100mm}')
        issues = validation.inspect_page(self.page, self.source)
        self.assertTrue(any(issue.code == "layout-positioned-outside" and issue.line == 4 for issue in issues))

    def test_wide_main_and_fixed_element_below_page_are_not_silently_accepted(self):
        self.load('<p>Normal text</p><p id="below" data-source-line="4">Outside</p>', 'main {width:400mm} #below {position:fixed; top:1500mm}')
        issues = validation.inspect_page(self.page, self.source)
        self.assertTrue(any(issue.code == "layout-horizontal-overflow" for issue in issues))
        self.assertTrue(any(issue.code == "layout-positioned-outside" and issue.line == 4 for issue in issues))

    def test_hidden_link_destination_fails_in_pdf_even_when_static_anchor_exists(self):
        document = self.load('<p data-source-line="5"><a href="#visible">Visible</a> <a href="#oculto">Oculto</a></p><h2 id="visible">Visible</h2><p id="oculto">Hidden target</p>', '#oculto {display:none}')
        self.assertEqual(validation.validate_html(document, self.source), [])
        pdf = self.root / "document.pdf"
        self.page.pdf(path=str(pdf), print_background=True, prefer_css_page_size=True)
        issues = validation.inspect_pdf(pdf, self.source, html_document=document)
        self.assertEqual([(issue.code, issue.severity, issue.line) for issue in issues], [("pdf-anchor-missing", "error", 5)])
        self.assertIn("#oculto", issues[0].message)

    def test_pdf_anchor_matching_distinguishes_unicode_from_literal_percent_encoded_id(self):
        document = self.load('<p><a href="#secci%C3%B3n">Unicode</a> <a href="#secci%25C3%25B3n">Literal</a></p><h2 id="sección">Unicode</h2><h2 id="secci%C3%B3n">Literal</h2>')
        pdf = self.root / "document.pdf"
        self.page.pdf(path=str(pdf), print_background=True, prefer_css_page_size=True)
        self.assertEqual(validation.inspect_pdf(pdf, self.source, html_document=document), [])

    def test_blank_real_pdf_and_explicit_break_run_are_distinguished(self):
        document = self.load('<p>Before break</p><div class="page-break"></div><div class="page-break"></div><p>After break</p>')
        pdf = self.root / "document.pdf"
        self.page.pdf(path=str(pdf), print_background=True, prefer_css_page_size=True)
        from pypdf import PdfReader
        with PdfReader(str(pdf)) as reader:
            self.assertEqual(len(reader.pages), 3)
            self.assertFalse(reader.pages[1].extract_text().strip())
        self.assertEqual(validation.inspect_pdf(pdf, self.source, html_document=document), [])
        self.assertEqual([issue.page for issue in validation.inspect_pdf(pdf, self.source)], [2])

    def test_complete_example_has_no_false_positive_with_cover_and_navigation(self):
        folder = self.root / "example"
        shutil.copytree(SKILL / "assets" / "ejemplo", folder)
        source = folder / "documento.md"
        html, _, _ = converter.build_document(source, None, "A4", False, True)
        html, _ = converter.load_support_module("document_structure").prepare_document(html)
        self.assertEqual(validation.validate_html(html, source), [])
        path = folder / "documento.html"
        path.write_text(html, encoding="utf-8")
        self.page.goto(path.as_uri(), wait_until="load")
        self.page.emulate_media(media="print")
        self.page.evaluate("document.fonts.ready")
        converter.fit_cover(self.page)
        self.assertEqual(validation.inspect_page(self.page, source), [])
        pdf = folder / "documento.pdf"
        self.page.pdf(path=str(pdf), print_background=True, prefer_css_page_size=True)
        self.assertEqual(validation.inspect_pdf(pdf, source, html_document=html), [])


if __name__ == "__main__":
    unittest.main()
