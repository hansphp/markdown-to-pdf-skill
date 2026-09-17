"""Real PDFs combining technical content, navigation, notes and validation."""

import importlib.util
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('mdpdf_technical_conversion_integration', SKILL / 'scripts/convert_markdown_to_pdf.py')
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)


@unittest.skipUnless(os.environ.get('MDPDF_BROWSER_TESTS') == '1', 'Requiere MDPDF_BROWSER_TESTS=1')
class TechnicalConversionIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='mdpdf-technical-integration-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'document.md'

    def test_math_diagram_and_notes_share_final_navigation_without_false_warnings(self):
        from pypdf import PdfReader
        markdown = r'''---
documento:
  titulo: "Documento técnico"
  codigo: "DOC-06"
pdf:
  portada: true
  indice_tablas: true
  indice_figuras: true
---
## 1. Proceso

Consulte [@fig:proceso].[^revisión]

Figura: Proceso técnico {#fig:proceso}

```mermaid
flowchart LR
 A[Inicio] --> B[Fin]
```

## 2. Fórmulas

La energía es $E=mc^2$ y la razón es \(\frac{a}{b}\).[^revisión]

$$
\int_0^1 x^2\,dx=\frac{1}{3}
$$

Los precios $5 y $10 son texto. La muestra `[@fig:inexistente]` es literal.

[^revisión]: Nota con **énfasis**, $a^2+b^2=c^2$ y [vuelta al proceso](#fig:proceso).
'''
        self.source.write_text(markdown, encoding='utf-8')
        args = converter.parse_args([str(self.source), '--strict'])
        output, _ = converter.convert(args)
        self.assertEqual(args.validation_diagnostics, [])
        self.assertEqual(args.footnote_count, 1)
        self.assertEqual(args.figure_count, 1)
        self.assertEqual(self.source.read_text(encoding='utf-8'), markdown)
        navigation = converter.load_support_module('pdf_navigation')
        targets = ['fig:proceso', 'figure-1', 'document-notes', 'document-note-1',
                   'document-note-ref-1-1', 'document-note-ref-1-2']
        pages = navigation.resolve_toc_pages(output, [{'id': name} for name in targets])
        self.assertEqual(pages['fig:proceso'], pages['figure-1'])
        self.assertGreaterEqual(pages['document-note-1'], pages['fig:proceso'])
        with PdfReader(output) as reader:
            text = re.sub(r'\s+', ' ', ' '.join(page.extract_text() for page in reader.pages))
            self.assertIn('Inicio', text)
            self.assertIn('Fin', text)
            self.assertIn('Los precios $5 y $10 son texto.', text)
            self.assertIn('[@fig:inexistente]', text)
            self.assertIn('Notas', text)
            self.assertNotIn('flowchart LR', text)
            self.assertNotIn(r'\frac', text)

    def test_invalid_technical_syntax_keeps_previous_pdf_and_never_falls_back(self):
        output = self.source.with_suffix('.pdf')
        previous = b'Previous output'
        output.write_bytes(previous)
        for body, diagnostic in [('```mermaid\nflowchart LR\nA --> [\n```', 'Mermaid'),
                                  (r'$\frac{1}{$', 'Fórmula')]:
            with self.subTest(body=body):
                self.source.write_text('# Informe\n\n' + body, encoding='utf-8')
                with patch.object(converter, 'render_with_browser') as browser:
                    with self.assertRaisesRegex(converter.DocumentValidationError, diagnostic) as raised:
                        converter.convert(converter.parse_args([str(self.source), '--force',
                            '--no-branding', '--no-toc', '--no-bookmarks']))
                self.assertIn('document.md', str(raised.exception))
                self.assertIn('línea 3', str(raised.exception))
                browser.assert_not_called()
                self.assertEqual(output.read_bytes(), previous)

    def test_unsupported_journey_keeps_previous_pdf_and_reports_source_without_syntax_advice(self):
        markdown = ('# Informe\n\n```mermaid\njourney\n title Revisión\n'
                    ' section Preparar\n  Leer requisitos: 5: Usuario\n```\n')
        self.source.write_text(markdown, encoding='utf-8')
        output = self.source.with_suffix('.pdf')
        previous = b'Previous output'
        output.write_bytes(previous)
        for strict in (False, True):
            with self.subTest(strict=strict):
                args = converter.parse_args([str(self.source), '--force', '--no-branding',
                    '--no-toc', '--no-bookmarks', *(['--strict'] if strict else [])])
                with patch.object(converter, 'render_with_browser') as browser:
                    with self.assertRaisesRegex(converter.DocumentValidationError,
                                                'mermaid-journey-unsupported') as raised:
                        converter.convert(args)
                self.assertIn(str(self.source), str(raised.exception))
                self.assertIn('línea 3', str(raised.exception))
                self.assertNotIn('Corrija la sintaxis', str(raised.exception))
                browser.assert_not_called()
                self.assertEqual(output.read_bytes(), previous)
                self.assertEqual(self.source.read_text(encoding='utf-8'), markdown)

    def test_math_inside_emphasis_and_links_survives_pdf_export(self):
        from pypdf import PdfReader
        markdown = r'''# Prueba de contenido

*Producto $x*y$*.

[Intervalo $\left[0,1\right)$](https://example.com/intervalo).

**Cociente \(\frac{a}{b}\)**.
'''
        self.source.write_text(markdown, encoding='utf-8')
        args = converter.parse_args([str(self.source), '--strict', '--no-branding',
                                     '--no-toc', '--no-bookmarks'])
        output, _ = converter.convert(args)
        self.assertEqual(args.validation_diagnostics, [])
        self.assertEqual(self.source.read_text(encoding='utf-8'), markdown)
        with PdfReader(output) as reader:
            text = ' '.join(page.extract_text() or '' for page in reader.pages)
            for label in ('Producto', 'Intervalo', 'Cociente'):
                self.assertIn(label, text)
            for token in ('$', r'\left', r'\right', r'\frac', '**', 'https://'):
                self.assertNotIn(token, text)
            uris = [annotation.get_object().get('/A', {}).get('/URI')
                    for page in reader.pages for annotation in page.get('/Annots', [])]
            self.assertIn('https://example.com/intervalo', uris)

    def test_inherited_metadata_math_and_notes_survive_with_and_without_cover(self):
        from pypdf import PdfReader
        markdown = r'''---
documento: {}
---
| Dato | Valor |
| --- | --- |
| Título | Informe $\frac{a}{b}$[^titulo] |
| Subtítulo | Análisis \(x^2\)[^subtitulo] |
| Versión | 1.0 |

## Cuerpo

Contenido conservado.

[^titulo]: Fuente del título.
[^subtitulo]: Fuente del subtítulo.
'''
        self.source.write_text(markdown, encoding='utf-8')
        navigation = converter.load_support_module('pdf_navigation')
        targets = ['document-note-1', 'document-note-2',
                   'document-note-ref-1-1', 'document-note-ref-2-1']
        for cover in (False, True):
            with self.subTest(cover=cover):
                output = self.root / ('cover.pdf' if cover else 'body.pdf')
                args = converter.parse_args([str(self.source), '--output', str(output),
                    '--cover' if cover else '--no-cover', '--strict', '--no-branding',
                    '--no-toc', '--no-bookmarks'])
                converter.convert(args)
                self.assertEqual(args.validation_diagnostics, [])
                self.assertEqual(args.footnote_count, 2)
                self.assertEqual(self.source.read_text(encoding='utf-8'), markdown)
                pages = navigation.resolve_toc_pages(output, [{'id': name} for name in targets])
                self.assertEqual(pages['document-note-ref-1-1'], 1)
                self.assertEqual(pages['document-note-ref-2-1'], 1)
                if cover:
                    self.assertGreater(pages['document-note-1'], 1)
                with PdfReader(output) as reader:
                    first_page = reader.pages[0].extract_text() or ''
                    text = ' '.join(page.extract_text() or '' for page in reader.pages)
                    self.assertIn('Informe', first_page)
                    self.assertIn('Análisis', first_page)
                    for label in ('Contenido conservado.', 'Fuente del título.',
                                  'Fuente del subtítulo.'):
                        self.assertIn(label, text)
                    for token in ('$', r'\frac', r'\(', '[^titulo]', '[^subtitulo]'):
                        self.assertNotIn(token, text)

    def test_wide_visible_formula_still_triggers_strict_validation(self):
        self.source.write_text('# Informe\n\n$$\n' + '+'.join(['x'] * 160) + '\n$$', encoding='utf-8')
        with self.assertRaisesRegex(converter.DocumentValidationError, 'layout-horizontal-overflow'):
            converter.convert(converter.parse_args([str(self.source), '--strict']))
        self.assertFalse(self.source.with_suffix('.pdf').exists())


if __name__ == '__main__':
    unittest.main()
