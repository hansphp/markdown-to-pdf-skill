"""Comprueba encabezados, pies y entorno local sin iniciar navegadores."""

import base64
import contextlib
import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "convert_markdown_to_pdf.py"
SPEC = importlib.util.spec_from_file_location("mdpdf_layout_tests", SCRIPT)
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)


class LayoutTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mdpdf-layout-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.html = self.root / "document.html"
        self.html.write_text("<h1>Prueba</h1>", encoding="utf-8")
        self.pdf = self.root / "document.pdf"
        self.logo = self.root / "logo.png"
        self.logo.write_bytes(b"\x89PNG\r\n\x1a\nexample")
        self.browser = self.root / "chrome"
        self.browser.write_text("browser placeholder", encoding="utf-8")

    @contextlib.contextmanager
    def playwright_context(self):
        playwright = MagicMock()
        sync = MagicMock()
        sync.return_value.__enter__.return_value = playwright
        module = types.ModuleType("playwright.sync_api")
        module.sync_playwright = sync
        modules = {"playwright": types.ModuleType("playwright"), "playwright.sync_api": module}
        with patch.dict(sys.modules, modules), patch.object(converter, "find_browsers", return_value=[self.browser]):
            yield playwright, playwright.chromium.launch.return_value.new_page.return_value

    def test_default_layout_has_logo_classification_and_footer(self):
        args = converter.parse_args(["document.md"])
        self.assertTrue(args.footer)
        self.assertEqual(args.logo, converter.DEFAULT_LOGO)
        self.assertEqual(args.classification, "CONFIDENCIAL")
        self.assertTrue(args.toc)
        self.assertTrue(args.bookmarks)
        self.assertTrue(args.captions)

    def test_navigation_and_captions_can_be_omitted_independently(self):
        args = converter.parse_args(["document.md", "--no-toc", "--no-bookmarks", "--no-captions"])
        self.assertFalse(args.toc)
        self.assertFalse(args.bookmarks)
        self.assertFalse(args.captions)
        self.assertTrue(args.footer)
        self.assertEqual(args.logo, converter.DEFAULT_LOGO)
        args = converter.parse_args(["document.md", "--no-branding"])
        self.assertTrue(args.toc)
        self.assertTrue(args.bookmarks)

    def test_layout_parts_can_be_omitted_independently(self):
        args = converter.parse_args(["document.md", "--no-logo"])
        self.assertIsNone(args.logo)
        self.assertTrue(args.footer)
        self.assertEqual(args.classification, "CONFIDENCIAL")
        args = converter.parse_args(["document.md", "--no-footer", "--classification", ""])
        self.assertFalse(args.footer)
        self.assertEqual(args.logo, converter.DEFAULT_LOGO)
        self.assertEqual(args.classification, "")

    def test_no_branding_omits_all_parts_even_with_explicit_options(self):
        args = converter.parse_args(["document.md", "--no-branding", "--logo", "custom.svg", "--footer"])
        self.assertIsNone(args.logo)
        self.assertFalse(args.footer)
        self.assertEqual(args.classification, "")

    def test_image_data_uri_accepts_supported_formats(self):
        for extension, mime in [("png", "image/png"), ("jpg", "image/jpeg"), ("jpeg", "image/jpeg"), ("svg", "image/svg+xml")]:
            with self.subTest(extension=extension):
                logo = self.root / f"image.{extension}"
                logo.write_bytes(b"image content")
                uri = converter.image_data_uri(logo)
                self.assertTrue(uri.startswith(f"data:{mime};base64,"))
                self.assertEqual(base64.b64decode(uri.split(",", 1)[1]), logo.read_bytes())

    def test_logo_rejects_unsupported_format(self):
        with self.assertRaisesRegex(converter.ConversionError, "PNG, JPEG o SVG"):
            converter.image_data_uri(self.root / "logo.txt")

    def test_header_embeds_logo_and_escapes_classification(self):
        header = converter.header_template(self.logo, "Uso <interno> & revisión")
        self.assertIn("data:image/png;base64,", header)
        self.assertIn("Uso &lt;interno&gt; &amp; revisión", header)
        self.assertEqual(converter.header_template(None, ""), "<span></span>")

    def test_playwright_uses_explicit_browser_and_complete_layout(self):
        with self.playwright_context() as (playwright, page):
            converter.render_with_playwright(self.html, self.pdf, True, "Título", "Subtítulo", self.logo, "CONFIDENCIAL", self.browser)
        self.assertEqual(playwright.chromium.launch.call_args.kwargs["executable_path"], str(self.browser))
        options = page.pdf.call_args.kwargs
        self.assertTrue(options["display_header_footer"])
        self.assertIn("CONFIDENCIAL", options["header_template"])
        self.assertIn("data:image/png", options["header_template"])
        self.assertIn("Título", options["footer_template"])
        self.assertIn("Subtítulo", options["footer_template"])
        self.assertIn('class="pageNumber"', options["footer_template"])
        self.assertIn('class="totalPages"', options["footer_template"])
        self.assertTrue(options["outline"])
        self.assertTrue(options["tagged"])

    def test_bookmarks_can_be_disabled_without_changing_the_footer(self):
        with self.playwright_context() as (_, page):
            converter.render_with_playwright(self.html, self.pdf, True, "Título", "", bookmarks=False)
        options = page.pdf.call_args.kwargs
        self.assertFalse(options["outline"])
        self.assertTrue(options["display_header_footer"])
        self.assertIn('class="pageNumber"', options["footer_template"])

    def test_playwright_reuses_detected_browser_and_can_omit_footer(self):
        with self.playwright_context() as (playwright, page):
            converter.render_with_playwright(self.html, self.pdf, False, "Título", "", None, "CONFIDENCIAL")
        self.assertEqual(playwright.chromium.launch.call_args.kwargs["executable_path"], str(self.browser))
        self.assertEqual(page.pdf.call_args.kwargs["footer_template"], "<span></span>")

    def test_plain_playwright_output_omits_header_and_footer(self):
        with self.playwright_context() as (_, page):
            converter.render_with_playwright(self.html, self.pdf, False, "Título", "", None, "")
        self.assertNotIn("display_header_footer", page.pdf.call_args.kwargs)

    def test_browser_engine_rejects_decorated_layout(self):
        source = self.root / "source.md"
        source.write_text("# Prueba", encoding="utf-8")
        with self.assertRaisesRegex(converter.ConversionError, "--no-branding"):
            converter.convert(converter.parse_args([str(source), "--engine", "browser"]))

    def test_existing_local_environment_is_reused_once(self):
        local_python = self.root / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        local_python.parent.mkdir(parents=True)
        local_python.write_text("python placeholder", encoding="utf-8")
        args = converter.parse_args(["source.md"])
        with patch.object(converter, "SKILL_DIR", self.root), \
             patch.object(converter, "playwright_available", return_value=False), \
             patch.dict(os.environ, {}, clear=True), patch.object(converter.os, "execve") as execute:
            converter.use_local_environment(args, ["source.md"])
        self.assertEqual(execute.call_args.args[0], str(local_python))
        self.assertEqual(execute.call_args.args[1][-1], "source.md")
        self.assertEqual(execute.call_args.args[2]["MDPDF_LOCAL_REEXEC"], "1")
        with patch.object(converter, "playwright_available", return_value=False), \
             patch.dict(os.environ, {"MDPDF_LOCAL_REEXEC": "1"}), patch.object(converter.os, "execve") as execute:
            converter.use_local_environment(args, ["source.md"])
        execute.assert_not_called()

    def test_plain_browser_does_not_switch_python_environment(self):
        args = converter.parse_args(["source.md", "--engine", "browser", "--no-branding"])
        with patch.object(converter.os, "execve") as execute:
            converter.use_local_environment(args, ["source.md", "--engine", "browser", "--no-branding"])
        execute.assert_not_called()

    def test_toc_reuses_local_environment_when_only_pypdf_is_missing(self):
        local_python = self.root / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        local_python.parent.mkdir(parents=True)
        local_python.write_text("python placeholder", encoding="utf-8")
        args = converter.parse_args(["source.md"])
        with patch.object(converter, "SKILL_DIR", self.root), \
             patch.object(converter, "playwright_available", return_value=True), \
             patch.object(converter, "pypdf_available", return_value=False), \
             patch.dict(os.environ, {}, clear=True), patch.object(converter.os, "execve") as execute:
            converter.use_local_environment(args, ["source.md"])
        self.assertEqual(execute.call_args.args[0], str(local_python))


if __name__ == "__main__":
    unittest.main()
