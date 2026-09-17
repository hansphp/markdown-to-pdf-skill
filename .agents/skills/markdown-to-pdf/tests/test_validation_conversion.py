"""Diagnostics must block publication and cannot be bypassed by engine fallback."""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('mdpdf_validation_conversion', SKILL / 'scripts/convert_markdown_to_pdf.py')
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)


class ValidationConversionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='mdpdf-validation-convert-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.source = self.root / 'document.md'
        self.output = self.root / 'document.pdf'
        self.previous = b'Previously delivered PDF must remain intact'
        self.output.write_bytes(self.previous)

    def test_source_failures_report_location_before_starting_any_renderer(self):
        for content, diagnostic in [
            ('![Falta](missing.png)', 'resource-missing'),
            ('[Destino](#ausente)', 'anchor-missing'),
            ('[@tbl:ausente]', 'Referencia sin destino'),
        ]:
            with self.subTest(content=content):
                self.source.write_text('# Informe\n\n' + content + '\n', encoding='utf-8')
                with patch.object(converter, 'render_with_playwright') as playwright, \
                     patch.object(converter, 'render_with_browser') as browser:
                    with self.assertRaisesRegex(converter.ConversionError, diagnostic) as raised:
                        converter.convert(converter.parse_args([str(self.source), '--force']))
                self.assertIn('document.md', str(raised.exception))
                self.assertRegex(str(raised.exception), r'(?::3|línea 3)')
                playwright.assert_not_called()
                browser.assert_not_called()
                self.assertEqual(self.output.read_bytes(), self.previous)

    def test_strict_basic_engine_reports_partial_validation_before_rendering(self):
        self.source.write_text('# Informe\n\nTexto.', encoding='utf-8')
        with patch.object(converter, 'render_with_browser') as browser:
            with self.assertRaisesRegex(converter.DocumentValidationError, 'validation-partial'):
                converter.convert(converter.parse_args([str(self.source), '--engine', 'browser',
                                  '--no-branding', '--no-toc', '--no-bookmarks', '--strict', '--force']))
        browser.assert_not_called()
        self.assertEqual(self.output.read_bytes(), self.previous)

    @unittest.skipUnless(os.environ.get('MDPDF_BROWSER_TESTS') == '1', 'Requiere MDPDF_BROWSER_TESTS=1')
    def test_warning_mode_exports_and_strict_mode_preserves_that_pdf(self):
        self.source.write_text('# Informe\n\nPárrafo demasiado ancho.', encoding='utf-8')
        css = self.root / 'wide.css'
        css.write_text('main > p { width: 300mm; }', encoding='utf-8')
        flags = [str(self.source), '--css', str(css), '--force']
        normal = converter.parse_args(flags)
        converter.convert(normal)
        self.assertTrue(any(item.code == 'layout-horizontal-overflow' for item in normal.validation_diagnostics))
        delivered = self.output.read_bytes()
        with patch.object(converter, 'render_with_browser') as browser:
            with self.assertRaisesRegex(converter.DocumentValidationError, 'layout-horizontal-overflow'):
                converter.convert(converter.parse_args(flags + ['--strict', '--no-branding', '--no-toc', '--no-bookmarks']))
        browser.assert_not_called()
        self.assertEqual(self.output.read_bytes(), delivered)

    @unittest.skipUnless(os.environ.get('MDPDF_BROWSER_TESTS') == '1', 'Requiere MDPDF_BROWSER_TESTS=1')
    def test_vertical_clipping_warns_in_normal_mode_and_strict_mode_preserves_previous_pdf(self):
        from pypdf import PdfReader

        markdown = '# Informe\n\nTexto conservado.\n\n```text\n' + '\n'.join(
            f'LINEA-{number:02d} contenido importante' for number in range(1, 21)
        ) + '\n```\n'
        self.source.write_text(markdown, encoding='utf-8')
        css = self.root / 'clipped.css'
        css.write_text('pre {height:12mm;overflow:hidden}', encoding='utf-8')
        flags = [str(self.source), '--css', str(css), '--no-logo', '--no-toc']
        normal = converter.parse_args(flags + ['--output', str(self.root / 'warning.pdf')])
        warning_pdf, engine = converter.convert(normal)
        self.assertTrue(engine.startswith('playwright/'))
        clipping = [item for item in normal.validation_diagnostics if item.code == 'layout-vertical-clipping']
        self.assertEqual([(item.severity, item.line) for item in clipping], [('warning', 5)])
        self.assertIn('pre', clipping[0].selector)
        with PdfReader(warning_pdf) as reader:
            text = ' '.join(page.extract_text() or '' for page in reader.pages)
        self.assertIn('LINEA-01', text)
        self.assertNotIn('LINEA-20', text)
        with patch.object(converter, 'render_with_browser') as browser:
            with self.assertRaisesRegex(converter.DocumentValidationError, 'layout-vertical-clipping'):
                converter.convert(converter.parse_args(flags + ['--strict', '--force']))
        browser.assert_not_called()
        self.assertEqual(self.output.read_bytes(), self.previous)
        self.assertEqual(self.source.read_text(encoding='utf-8'), markdown)

    @unittest.skipUnless(os.environ.get('MDPDF_BROWSER_TESTS') == '1', 'Requiere MDPDF_BROWSER_TESTS=1')
    def test_corrupt_header_logo_is_an_error_even_without_cover(self):
        self.source.write_text('# Informe\n\nTexto.', encoding='utf-8')
        logo = self.root / 'corrupt.png'
        logo.write_bytes(b'Not an image')
        with self.assertRaisesRegex(converter.DocumentValidationError, 'image-load-failed') as raised:
            converter.convert(converter.parse_args([str(self.source), '--logo', str(logo), '--force']))
        self.assertIn('corrupt.png', str(raised.exception))
        self.assertEqual(self.output.read_bytes(), self.previous)

    @unittest.skipUnless(os.environ.get('MDPDF_BROWSER_TESTS') == '1', 'Requiere MDPDF_BROWSER_TESTS=1')
    def test_hidden_body_target_fails_final_pdf_validation(self):
        self.source.write_text('# Informe\n\n[Sección oculta](#destino)\n\n## Destino\n\nTexto.', encoding='utf-8')
        css = self.root / 'hidden.css'
        css.write_text('#destino { display: none; }', encoding='utf-8')
        with self.assertRaisesRegex(converter.DocumentValidationError, 'pdf-anchor-missing'):
            converter.convert(converter.parse_args([str(self.source), '--css', str(css), '--no-toc', '--force']))
        self.assertEqual(self.output.read_bytes(), self.previous)

    @unittest.skipUnless(os.environ.get('MDPDF_BROWSER_TESTS') == '1', 'Requiere MDPDF_BROWSER_TESTS=1')
    def test_links_to_the_source_file_become_native_pdf_destinations(self):
        from pypdf import PdfReader
        self.source.write_text('# Informe\n\n[Ir a sección](document.md#destino)\n\n## Destino\n\nTexto.', encoding='utf-8')
        output, _ = converter.convert(converter.parse_args([str(self.source), '--no-toc', '--force', '--strict']))
        navigation = converter.load_support_module('pdf_navigation')
        self.assertEqual(navigation.resolve_toc_pages(output, [{'id': 'destino'}]), {'destino': 1})
        with PdfReader(str(output)) as reader:
            annotations = [ref.get_object() for page in reader.pages for ref in page.get('/Annots', [])]
            self.assertTrue(annotations)
            for annotation in annotations:
                self.assertNotIn('document.md', str(annotation.get('/A', {}).get('/URI', '')))


if __name__ == '__main__':
    unittest.main()
