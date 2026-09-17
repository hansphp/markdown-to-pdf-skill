"""Pruebas del motor y los reintentos sin iniciar navegadores ni usar la red."""

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "convert_markdown_to_pdf.py"
SPEC = importlib.util.spec_from_file_location("mdpdf_runtime_tests", SCRIPT)
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)

# Suficiente para probar la comprobación de cabecera/final; no simula un lector PDF.
COMPLETE_PDF = b"%PDF-1.7\n" + b"x" * 200 + b"\n%%EOF\n"
TRUNCATED_PDF = b"%PDF-1.7\n" + b"x" * 200


class FakeClock:
    def __init__(self):
        self.elapsed = 0
        self.sleeps = []

    def monotonic(self):
        return self.elapsed

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.elapsed += seconds


class FakeProcess:
    def __init__(self, returncode):
        self.returncode = returncode
        self.terminated = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mdpdf-runtime-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source.md"
        self.source.write_text("# Documento de prueba\n\nTexto en español.\n", encoding="utf-8")
        self.html = self.root / "source.html"
        self.html.write_text("<h1>Documento de prueba</h1>", encoding="utf-8")
        self.pdf = self.root / "source.pdf"

    @contextlib.contextmanager
    def browser_context(self, content, returncode):
        if content is not None:
            self.pdf.write_bytes(content)
        clock = FakeClock()
        process = FakeProcess(returncode)
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(converter.subprocess, "Popen", return_value=process))
            stack.enter_context(patch.object(converter.time, "monotonic", side_effect=clock.monotonic))
            stack.enter_context(patch.object(converter.time, "sleep", side_effect=clock.sleep))
            yield clock, process

    def test_truncated_pdf_fails_immediately_after_browser_exits(self):
        with self.browser_context(TRUNCATED_PDF, 1) as (clock, process):
            with self.assertRaisesRegex(converter.ConversionError, "%%EOF"):
                converter.render_with_browser(self.html, self.pdf, Path("/mock/chrome"))
        self.assertEqual(clock.sleeps, [])
        self.assertFalse(process.terminated)

    def test_invalid_pdf_fails_immediately_after_browser_exits(self):
        with self.browser_context(b"invalid" * 40, 0) as (clock, _):
            with self.assertRaisesRegex(converter.ConversionError, "cabecera PDF"):
                converter.render_with_browser(self.html, self.pdf, Path("/mock/chrome"))
        self.assertEqual(clock.sleeps, [])

    def test_missing_pdf_fails_immediately_after_browser_exits(self):
        with self.browser_context(None, 3) as (clock, _):
            with self.assertRaisesRegex(converter.ConversionError, "código 3"):
                converter.render_with_browser(self.html, self.pdf, Path("/mock/chrome"))
        self.assertEqual(clock.sleeps, [])

    def test_complete_pdf_is_accepted_despite_browser_exit_code(self):
        with self.browser_context(COMPLETE_PDF, 1) as (clock, _):
            engine = converter.render_with_browser(self.html, self.pdf, Path("/mock/chrome"))
        self.assertEqual(engine, "browser/chrome")
        self.assertEqual(clock.sleeps, [])

    def test_browser_that_remains_open_is_closed_after_complete_pdf(self):
        with self.browser_context(COMPLETE_PDF, None) as (clock, process):
            converter.render_with_browser(self.html, self.pdf, Path("/mock/chrome"))
        self.assertEqual(clock.elapsed, 0.25)
        self.assertTrue(process.terminated)

    def test_unresponsive_browser_has_bounded_wait(self):
        with self.browser_context(None, None) as (clock, process):
            with self.assertRaisesRegex(converter.ConversionError, "90 segundos"):
                converter.render_with_browser(self.html, self.pdf, Path("/mock/chrome"))
        self.assertEqual(clock.elapsed, 90)
        self.assertTrue(process.terminated)

    def test_pdf_marker_must_be_at_end(self):
        self.pdf.write_bytes(COMPLETE_PDF + b"unexpected data")
        with self.assertRaisesRegex(converter.ConversionError, "%%EOF"):
            converter.validate_pdf(self.pdf)
        self.pdf.write_bytes(COMPLETE_PDF + b" \t\r\n")
        converter.validate_pdf(self.pdf)

    def test_invalid_browser_result_is_removed_before_next_attempt(self):
        attempts = []

        def render(html, pdf, browser):
            attempts.append(browser.name)
            self.assertFalse(pdf.exists(), "Cada intento debe comenzar sin el PDF anterior")
            pdf.write_bytes(TRUNCATED_PDF if browser.name == "first" else COMPLETE_PDF)
            return f"browser/{browser.name}"

        with patch.object(converter, "find_browsers", return_value=[Path("/first"), Path("/second")]), \
             patch.object(converter, "render_with_browser", side_effect=render):
            output, engine = converter.convert(converter.parse_args([str(self.source), "--engine", "browser", "--no-branding", "--no-toc", "--no-bookmarks"]))
        self.assertEqual(attempts, ["first", "second"])
        self.assertEqual(engine, "browser/second")
        self.assertEqual(output.read_bytes(), COMPLETE_PDF)

    def test_invalid_playwright_result_falls_back_to_browser(self):
        def render_playwright(html, pdf, *args, **kwargs):
            pdf.write_bytes(TRUNCATED_PDF)
            return "playwright/chromium"

        def render_browser(html, pdf, browser):
            self.assertFalse(pdf.exists())
            pdf.write_bytes(COMPLETE_PDF)
            return "browser/chrome"

        with patch.object(converter, "playwright_available", return_value=True), \
             patch.object(converter, "render_with_playwright", side_effect=render_playwright), \
             patch.object(converter, "find_browsers", return_value=[Path("/chrome")]), \
             patch.object(converter, "render_with_browser", side_effect=render_browser):
            output, engine = converter.convert(converter.parse_args([str(self.source), "--no-branding", "--no-toc", "--no-bookmarks"]))
        self.assertEqual(engine, "browser/chrome")
        self.assertEqual(output.read_bytes(), COMPLETE_PDF)

    def test_failed_forced_conversion_preserves_existing_output(self):
        original = b"original output"
        self.pdf.write_bytes(original)

        def render(html, pdf, browser):
            pdf.write_bytes(TRUNCATED_PDF)
            return "browser/chrome"

        with patch.object(converter, "find_browsers", return_value=[Path("/chrome")]), \
             patch.object(converter, "render_with_browser", side_effect=render):
            with self.assertRaises(converter.ConversionError):
                converter.convert(converter.parse_args([str(self.source), "--engine", "browser", "--force", "--no-branding", "--no-toc", "--no-bookmarks"]))
        self.assertEqual(self.pdf.read_bytes(), original)

    def test_invalid_css_encoding_is_reported_without_traceback(self):
        css = self.root / "invalid.css"
        css.write_bytes(b"\xff\xfe")
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            code = converter.main([str(self.source), "--css", str(css), "--no-branding", "--no-toc", "--no-bookmarks"])
        self.assertEqual(code, 2)
        self.assertIn("UTF-8", error.getvalue())
        self.assertNotIn("Traceback", error.getvalue())


if __name__ == "__main__":
    unittest.main()
