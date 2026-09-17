"""Custom stylesheet imports, native URL bases and their printed PDF effect."""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SKILL = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('mdpdf_css_imports', SKILL / 'scripts/convert_markdown_to_pdf.py')
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)


class CSSImportValidationTests(unittest.TestCase):
    def test_missing_import_identifies_custom_css_before_rendering_and_keeps_previous_pdf(self):
        with tempfile.TemporaryDirectory(prefix='mdpdf-css-missing-') as directory:
            root = Path(directory)
            source = root / 'document.md'
            source.write_text('# Informe\n\nContenido conservado.\n', encoding='utf-8')
            original = source.read_bytes()
            css = root / 'styles' / 'custom.css'
            css.parent.mkdir()
            output = source.with_suffix('.pdf')
            previous = b'Previous PDF remains untouched'
            output.write_bytes(previous)
            for declaration in ('@import "missing.css";', '@import url("missing.css");'):
                with self.subTest(declaration=declaration):
                    css.write_text('/* Estilos */\n' + declaration, encoding='utf-8')
                    with patch.object(converter, 'render_with_playwright') as playwright, \
                         patch.object(converter, 'render_with_browser') as browser:
                        with self.assertRaisesRegex(converter.DocumentValidationError, 'resource-missing') as raised:
                            converter.convert(converter.parse_args([str(source), '--css', str(css), '--force']))
                    self.assertIn(str(css) + ':2', str(raised.exception))
                    playwright.assert_not_called()
                    browser.assert_not_called()
                    self.assertEqual(output.read_bytes(), previous)
                    self.assertEqual(source.read_bytes(), original)


class _CSSFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='mdpdf-css-import-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / 'documents' / 'document.md'
        self.source.parent.mkdir()
        self.source.write_text('# Encabezado importado\n\n## Sección\n\nContenido conservado.\n', encoding='utf-8')
        self.original = self.source.read_bytes()
        self.css = self.root / 'separate-styles' / 'custom.css'
        self.css.parent.mkdir()


@unittest.skipUnless(os.environ.get('MDPDF_BROWSER_TESTS') == '1', 'Requiere MDPDF_BROWSER_TESTS=1')
class CSSImportBrowserTests(_CSSFixture):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.playwright = sync_playwright().start()
        browsers = converter.find_browsers()
        cls.browser = cls.playwright.chromium.launch(
            **({'executable_path': str(browsers[0])} if browsers else {}), headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        super().setUp()
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.requests = []
        self.page.on('request', lambda request: self.requests.append(request.url))
        self.page.route('http://**/*', lambda route: route.abort())
        self.page.route('https://**/*', lambda route: route.abort())

    def load(self, *, paper='A4', landscape=False):
        document, _, _ = converter.build_document(self.source, self.css, paper, landscape, False)
        html_path = self.root / 'preview.html'
        html_path.write_text(document, encoding='utf-8')
        self.page.emulate_media(media='print')
        self.page.goto(html_path.as_uri(), wait_until='networkidle')
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual([url for url in self.requests if url.startswith(('http:', 'https:'))], [])
        return document

    def test_imports_and_direct_urls_use_markdown_base_while_imported_sheets_use_their_own_base(self):
        theme = self.source.parent / 'theme'
        (theme / 'nested').mkdir(parents=True)
        (theme / 'media').mkdir()
        (self.source.parent / 'textures').mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10" fill="white"/></svg>'
        imported_image = theme / 'media' / 'imported.svg'
        imported_image.write_text(svg, encoding='utf-8')
        direct_image = self.source.parent / 'textures' / 'direct.svg'
        direct_image.write_text(svg, encoding='utf-8')
        (theme / 'nested' / 'type.css').write_text('h1 { letter-spacing: 3px; }', encoding='utf-8')
        (theme / 'palette.css').write_text(
            '@import "nested/type.css";\n'
            'h1 { color: rgb(255, 0, 0); background-image: url("media/imported.svg"); }', encoding='utf-8')
        # This decoy makes an accidental change to CSS-file-relative resolution visible.
        decoy = self.css.parent / 'theme'
        decoy.mkdir()
        (decoy / 'palette.css').write_text('h1 { color: rgb(0, 0, 255); }', encoding='utf-8')
        self.css.write_text('@import "theme/palette.css";\np { background-image: url("textures/direct.svg"); }', encoding='utf-8')
        document = self.load()
        actual = self.page.evaluate('''() => ({
            color: getComputedStyle(document.querySelector('h1')).color,
            spacing: getComputedStyle(document.querySelector('h1')).letterSpacing,
            imported: getComputedStyle(document.querySelector('h1')).backgroundImage,
            direct: getComputedStyle(document.querySelector('p')).backgroundImage
        })''')
        self.assertEqual(actual['color'], 'rgb(255, 0, 0)')
        self.assertEqual(actual['spacing'], '3px')
        self.assertEqual(actual['imported'], 'url("' + imported_image.as_uri() + '")')
        self.assertEqual(actual['direct'], 'url("' + direct_image.as_uri() + '")')
        for resource in (theme / 'palette.css', theme / 'nested' / 'type.css', imported_image, direct_image):
            self.assertIn(resource.as_uri(), self.requests)
        self.assertNotIn((decoy / 'palette.css').as_uri(), self.requests)
        validation = converter.load_support_module('document_validation')
        self.assertEqual(validation.validate_html(document, self.source, css_paths=[self.css]), [])

    def test_custom_rules_follow_imported_and_default_rules_but_paper_options_remain_last(self):
        (self.source.parent / 'palette.css').write_text('h1, h2 { color: rgb(255, 0, 0); }', encoding='utf-8')
        self.css.write_text('@import url("palette.css") print;\n'
            'h2 { color: rgb(0, 128, 0); }\n'
            ':root { --paper-height: 1mm; }\n'
            '@page { size: A4 portrait; margin: 1mm; }', encoding='utf-8')
        self.load(paper='Letter', landscape=True)
        actual = self.page.evaluate('''() => ({
            h1: getComputedStyle(document.querySelector('h1')).color,
            h2: getComputedStyle(document.querySelector('h2')).color,
            height: getComputedStyle(document.documentElement).getPropertyValue('--paper-height'),
            page: Array.from(document.styleSheets).flatMap(sheet => Array.from(sheet.cssRules))
                .filter(rule => rule.type === CSSRule.PAGE_RULE).at(-1).cssText
        })''')
        self.assertEqual(actual['h1'], 'rgb(255, 0, 0)')
        self.assertEqual(actual['h2'], 'rgb(0, 128, 0)')
        self.assertEqual(actual['height'].strip(), '215.9mm')
        self.assertIn('letter landscape', actual['page'].lower())
        self.assertIn('18mm 16mm', actual['page'])


@unittest.skipUnless(os.environ.get('MDPDF_BROWSER_TESTS') == '1', 'Requiere MDPDF_BROWSER_TESTS=1')
class CSSImportPDFTests(_CSSFixture):
    def test_imported_styles_preserve_single_page_cover_and_index_destinations(self):
        from pypdf import PdfReader
        title = 'Evaluación de documentos y requisitos de la operación ' * 9
        markdown = (f'---\ndocumento:\n  titulo: "{title.strip()}"\n  codigo: "DOC-LARGO"\n'
                    'pdf:\n  portada: true\n---\n## 1. Contenido\n\n'
                    'Texto final conservado. [Datos del documento](#table-1).\n')
        self.source.write_text(markdown, encoding='utf-8')
        (self.source.parent / 'palette.css').write_text(
            '.document-cover [data-document-role="title"] { color: rgb(255, 0, 0); }\n'
            '@page { size: A4 portrait; margin: 1mm; }', encoding='utf-8')
        self.css.write_text('@import "palette.css";', encoding='utf-8')
        args = converter.parse_args([
            str(self.source), '--css', str(self.css), '--paper', 'Letter', '--landscape',
            '--table-index', '--strict',
        ])
        output, _ = converter.convert(args)
        self.assertEqual(args.validation_diagnostics, [])
        self.assertEqual(self.source.read_text(encoding='utf-8'), markdown)
        with PdfReader(output) as reader:
            self.assertEqual(len(reader.pages), 4)
            texts = [' '.join(page.extract_text().split()) for page in reader.pages]
            self.assertIn(title.strip(), texts[0])
            self.assertIn('DOC-LARGO', texts[0])
            self.assertNotIn('Página 1 de', texts[0])
            self.assertIn('Índice', texts[1])
            self.assertIn('Índice de tablas', texts[2])
            self.assertIn('Texto final conservado.', texts[3])
            for page in reader.pages:
                self.assertAlmostEqual(float(page.mediabox.width), 792, delta=1)
                self.assertAlmostEqual(float(page.mediabox.height), 612, delta=1)
            from pypdf.generic import ContentStream
            colors = [tuple(float(value) for value in operands)
                      for operands, operator in ContentStream(reader.pages[0].get_contents(), reader).operations
                      if operator == b'rg']
            self.assertIn((1.0, 0.0, 0.0), colors)
        navigation = converter.load_support_module('pdf_navigation')
        destinations = navigation.resolve_toc_pages(output, [
            {'id': 'table-1', 'title': 'Datos del documento'},
            {'id': '1-contenido', 'title': '1. Contenido'},
        ])
        self.assertEqual(destinations, {'table-1': 1, '1-contenido': 4})

    def test_import_changes_final_pdf_and_later_missing_import_preserves_that_pdf(self):
        from pypdf import PdfReader
        from pypdf.generic import ContentStream
        (self.source.parent / 'palette.css').write_text(
            'h1 { color: rgb(255, 0, 0); text-transform: uppercase; }', encoding='utf-8')
        self.css.write_text('@import "palette.css";\n@page { size: A4 portrait; }', encoding='utf-8')
        flags = [str(self.source), '--css', str(self.css), '--no-branding', '--no-toc',
                 '--no-bookmarks', '--strict', '--paper', 'Letter', '--landscape']
        args = converter.parse_args(flags)
        output, engine = converter.convert(args)
        self.assertEqual(args.validation_diagnostics, [])
        self.assertTrue(engine.startswith('playwright/'))
        with PdfReader(output) as reader:
            self.assertEqual(len(reader.pages), 1)
            page = reader.pages[0]
            self.assertIn('ENCABEZADO IMPORTADO', page.extract_text())
            self.assertIn('Contenido conservado.', page.extract_text())
            self.assertAlmostEqual(float(page.mediabox.width), 792, places=1)
            self.assertAlmostEqual(float(page.mediabox.height), 612, places=1)
            colors = [tuple(float(value) for value in operands)
                      for operands, operator in ContentStream(page.get_contents(), reader).operations
                      if operator == b'rg']
            self.assertIn((1.0, 0.0, 0.0), colors)
        delivered = output.read_bytes()
        self.css.write_text('@import "missing.css";', encoding='utf-8')
        with self.assertRaisesRegex(converter.DocumentValidationError, 'resource-missing'):
            converter.convert(converter.parse_args(flags + ['--force']))
        self.assertEqual(output.read_bytes(), delivered)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_imported_vertical_clipping_is_inspected_before_publication(self):
        lines = '\n'.join('LINEA-' + str(number).zfill(2) + ' contenido importante' for number in range(1, 21))
        self.source.write_text('# Informe\n\n```text\n' + lines + '\n```\n', encoding='utf-8')
        original = self.source.read_bytes()
        (self.source.parent / 'clipping.css').write_text(
            'pre { height: 12mm; overflow: hidden; }', encoding='utf-8')
        self.css.write_text('@import "clipping.css";', encoding='utf-8')
        flags = [str(self.source), '--css', str(self.css), '--no-branding', '--no-toc', '--no-bookmarks']
        normal = converter.parse_args(flags)
        output, _ = converter.convert(normal)
        self.assertTrue(any(item.code == 'layout-vertical-clipping' for item in normal.validation_diagnostics))
        delivered = output.read_bytes()
        with self.assertRaisesRegex(converter.DocumentValidationError, 'layout-vertical-clipping'):
            converter.convert(converter.parse_args(flags + ['--strict', '--force']))
        self.assertEqual(output.read_bytes(), delivered)
        self.assertEqual(self.source.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
