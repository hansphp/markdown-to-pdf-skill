"""Actionable static and PDF validation, including intentional empty pages."""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location("mdpdf_validation_tests", SCRIPTS / "document_validation.py")
validation = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validation
SPEC.loader.exec_module(validation)


class StaticValidationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="mdpdf-validation-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.source = self.root / "documento.md"
        self.source.write_text("# Documento\n\n![Imagen](faltante.png)\n", encoding="utf-8")

    def test_missing_image_has_original_markdown_path_and_line(self):
        issues = validation.validate_html('<main><p data-source-line="3"><img src="faltante.png"></p></main>', self.source)
        self.assertEqual(len(issues), 1)
        issue = issues[0]
        self.assertEqual((issue.code, issue.severity, issue.line, issue.source), ("resource-missing", "error", 3, str(self.source)))
        self.assertIn("faltante.png", issue.message)
        self.assertIn(f"{self.source}:3", validation.format_diagnostic(issue))
        self.assertEqual(issue.as_dict()["severity"], "error")

    def test_source_search_is_only_a_fallback_and_does_not_invent_ambiguous_lines(self):
        issue = validation.validate_html('<img src="faltante.png">', self.source)[0]
        self.assertEqual(issue.line, 3)
        self.source.write_text("![A](faltante.png)\n![B](faltante.png)\n")
        self.assertIsNone(validation.validate_html('<img src="faltante.png">', self.source)[0].line)

    def test_all_body_links_check_decoded_fragments_and_same_file_paths(self):
        document = '<main><h2 id="sección">Sección</h2><a href="#secci%C3%B3n">Correcto</a><a href="documento.md#sección">Correcto</a><a href="./documento.md#ausente" data-source-line="9">Roto</a><a href="#otro" data-source-line="10">Otro roto</a></main>'
        issues = validation.validate_html(document, self.source)
        self.assertEqual([(issue.code, issue.line) for issue in issues], [("anchor-missing", 9), ("anchor-missing", 10)])

    def test_named_anchors_empty_fragment_and_external_links_are_not_broken(self):
        document = '<a name="legacy"></a><a href="#legacy">Correcto</a><a href="#">Arriba</a><a href="otro.md#desconocido">Otro</a><a href="https://invalid.example/#ausente">Web</a><a href="//invalid.example/#ausente">Web</a><img src="https://invalid.example/imagen.png"><img src="data:image/png;base64,aA==">'
        self.assertEqual(validation.validate_html(document, self.source), [])

    def test_local_resources_resolve_from_html_base_and_decode_spaces(self):
        assets = self.root / "recursos"
        assets.mkdir()
        (assets / "figura uno.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        document = f'<base href="{assets.as_uri()}/"><img src="figura%20uno.svg"><img src="{(assets / "figura uno.svg").as_uri()}">'
        self.assertEqual(validation.validate_html(document, self.source), [])

    def test_empty_image_and_directory_are_missing_resources(self):
        issues = validation.validate_html('<img src=""><img src="#"><img src=".">', self.source)
        self.assertEqual(len(issues), 3)
        self.assertTrue(all(issue.severity == "error" for issue in issues))

    def test_css_urls_imports_comments_and_locations_follow_embedded_browser_base(self):
        css = self.root / "styles" / "custom.css"
        css.parent.mkdir()
        css.write_text('/* url(ignored.png) */\n.hero {background: url("missing.png")}\n@import "extra.css";\n.icon {filter: url(#filter)}\n.remote {background: url(https://invalid.example/bg.png)}\n', encoding="utf-8")
        document = '<style>' + css.read_text() + '</style><p style="background:url(missing.png)">x</p>'
        issues = validation.validate_html(document, self.source, css_paths=[css])
        self.assertEqual(len(issues), 2)
        self.assertEqual([(issue.source, issue.line) for issue in issues], [(str(css), 2), (str(css), 3)])
        # Custom CSS is embedded, so URLs resolve against the Markdown directory.
        (self.root / "missing.png").write_bytes(b"exists")
        (self.root / "extra.css").write_text("p { color: red }")
        self.assertEqual(validation.validate_html(document, self.source, css_paths=[css]), [])

    def test_existing_source_file_is_never_changed(self):
        original = self.source.read_bytes()
        validation.validate_html('<img src="missing.svg"><a href="#bad">x</a>', self.source)
        self.assertEqual(self.source.read_bytes(), original)


class PDFValidationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="mdpdf-blank-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.source = self.root / "document.md"
        self.pdf = self.root / "document.pdf"

    def make_pdf(self, streams):
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
        writer = PdfWriter()
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        for data in streams:
            page = writer.add_blank_page(width=595, height=842)
            page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
            stream = DecodedStreamObject()
            stream.set_data(data)
            page[NameObject("/Contents")] = writer._add_object(stream)
        with self.pdf.open("wb") as handle:
            writer.write(handle)
        writer.close()

    @staticmethod
    def text(value, y=700):
        return f"BT /F1 12 Tf 60 {y} Td ({value}) Tj ET\n".encode("ascii")

    def test_blank_page_ignores_running_text_and_white_background(self):
        self.make_pdf([self.text("Body"), b"1 1 1 rg 0 0 595 842 re f\n" + self.text("Header", 815) + self.text("Footer", 25)])
        issues = validation.inspect_pdf(self.pdf, self.source)
        self.assertEqual([(issue.code, issue.severity, issue.page) for issue in issues], [("pdf-blank-page", "warning", 2)])

    def test_vector_drawing_counts_as_content_while_margin_logo_does_not(self):
        self.make_pdf([b"0 0 1 rg 100 200 100 100 re f\n", b"0 0 1 rg 60 805 20 20 re f\n"])
        self.assertEqual([issue.page for issue in validation.inspect_pdf(self.pdf, self.source)], [2])

    def test_consecutive_intentional_breaks_only_suppress_their_own_gap(self):
        self.make_pdf([self.text("Before"), b"", self.text("After"), b"", self.text("Later")])
        document = '<main><p>Before</p><div class="page-break"></div><div class="page-break"></div><p>After</p><p>Later</p></main>'
        # The after context spans multiple pages: use enough nearby content to
        # identify the neighboring page rather than treating all blanks as okay.
        document = document.replace('<p>After</p>', '<p>After</p><div class="page-break"></div>')
        issues = validation.inspect_pdf(self.pdf, self.source, html_document=document)
        self.assertEqual([issue.page for issue in issues], [4])

    def test_single_break_does_not_excuse_unexpected_blank_page(self):
        self.make_pdf([self.text("Before"), b"", self.text("After")])
        document = '<p>Before</p><div class="page-break"></div><p>After</p>'
        self.assertEqual([issue.page for issue in validation.inspect_pdf(self.pdf, self.source, html_document=document)], [2])

    def test_leading_intentional_break_is_recognized(self):
        self.make_pdf([b"", self.text("After")])
        document = '<div class="page-break"></div><p>After</p>'
        self.assertEqual(validation.inspect_pdf(self.pdf, self.source, html_document=document), [])

    def test_cover_page_has_zero_margins_for_content_detection(self):
        self.make_pdf([self.text("Cover title", 810)])
        document = '<section class="document-cover"><h1>Cover title</h1></section>'
        self.assertEqual(validation.inspect_pdf(self.pdf, self.source, html_document=document), [])

    def test_missing_optional_pdf_dependency_reports_partial_validation(self):
        with mock.patch.dict(sys.modules, {"pypdf": None}):
            issues = validation.inspect_pdf(self.pdf, self.source)
        self.assertEqual([(issue.code, issue.severity) for issue in issues], [("validation-partial", "warning")])

    def test_invalid_pdf_has_diagnostic_without_traceback(self):
        self.pdf.write_bytes(b"%PDF-1.4\nIncomplete PDF\n%%EOF")
        issues = validation.inspect_pdf(self.pdf, self.source)
        self.assertEqual([(issue.code, issue.severity) for issue in issues], [("pdf-read-error", "error")])


if __name__ == "__main__":
    unittest.main()
