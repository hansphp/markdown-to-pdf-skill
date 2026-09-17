"""Technical syntax through the Markdown parser and converter entrypoint."""

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('mdpdf_technical_conversion', SKILL / 'scripts/convert_markdown_to_pdf.py')
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)


class TechnicalConversionTests(unittest.TestCase):
    def test_inline_math_preserves_tex_and_prices(self):
        rendered = converter.render_inline(r'Razón $a_b+\frac{1}{2}$ y \(x^2\); precios $5 y $10, o $25.00.')
        self.assertEqual(rendered.count('data-document-math="inline"'), 2)
        self.assertIn(r'a_b+\frac{1}{2}</span>', rendered)
        self.assertIn('x^2</span>', rendered)
        self.assertIn('precios $5 y $10, o $25.00.', rendered)
        self.assertNotIn('<em>', rendered)

    def test_emphasis_keeps_math_delimiters_and_tex_intact(self):
        for opening, closing in [('$', '$'), (r'\(', r'\)')]:
            for marker, before, after, tex in [
                ('*', '<em>', '</em>', 'x*y'),
                ('_', '<em>', '</em>', 'x_i+y_j'),
                ('**', '<strong>', '</strong>', 'x**y'),
                ('__', '<strong>', '</strong>', 'x__i'),
                ('***', '<strong><em>', '</em></strong>', 'x***y'),
                ('~~', '<del>', '</del>', 'x~~y'),
            ]:
                source = f'{marker}Producto {opening}{tex}{closing}{marker}'
                with self.subTest(source=source):
                    rendered = converter.render_inline(source)
                    self.assertEqual(rendered, before + 'Producto '
                        + f'<span data-document-math="inline">{tex}</span>' + after)

    def test_link_labels_keep_unbalanced_tex_brackets_inside_math(self):
        for opening, closing in [('$', '$'), (r'\(', r'\)')]:
            for tex in [r'\left[0,1\right)', r'\left(0,1\right]']:
                source = f'[Intervalo {opening}{tex}{closing}](https://example.com "Intervalo")'
                with self.subTest(source=source):
                    self.assertEqual(converter.render_inline(source),
                        '<a href="https://example.com" title="Intervalo">Intervalo '
                        + f'<span data-document-math="inline">{tex}</span></a>')

    def test_nested_emphasis_in_link_labels_preserves_math(self):
        rendered = converter.render_inline(r'[**Producto $x*y$**, intervalo \(\left[0,1\right)\)](#intervalo)')
        self.assertEqual(rendered, '<a href="#intervalo"><strong>Producto '
            '<span data-document-math="inline">x*y</span></strong>, intervalo '
            r'<span data-document-math="inline">\left[0,1\right)</span></a>')

    def test_delimiter_scanning_keeps_inline_code_and_escapes_literal(self):
        self.assertEqual(converter.render_inline(r'*Literal `$x*y$` y `\(a*b\)`*'),
            r'<em>Literal <code>$x*y$</code> y <code>\(a*b\)</code></em>')
        self.assertEqual(converter.render_inline(r'[Código `$[0,1)$` y `\([0,1)\)`](#codigo)'),
            r'<a href="#codigo">Código <code>$[0,1)$</code> y <code>\([0,1)\)</code></a>')
        self.assertEqual(converter.render_inline(r'*Literal \$x\*y\$ y \\(x\\)*'),
            r'<em>Literal $x*y$ y \(x\)</em>')

    def test_unclosed_explicit_math_within_formatting_reports_its_source(self):
        for source in [r'*Producto \(x*y*', r'[Producto \(x*y](#producto)']:
            with self.subTest(source=source), self.assertRaisesRegex(converter.ConversionError, 'línea 19'):
                converter.render_inline(source, source_line=19)

    def test_technical_syntax_in_code_and_escaped_syntax_stays_literal(self):
        rendered = converter.render_inline(r'`$a_b$` `\(x\)` `[^nota]` \$x\$ \\(x\\) \[^nota]')
        self.assertNotIn('data-document-math', rendered)
        self.assertNotIn('data-document-footnote', rendered)
        blocks = converter.render_blocks(['````markdown', '```mermaid', 'flowchart LR', 'A --> B', '```', '$x$', '[^nota]', '````'])
        self.assertNotIn('data-document-mermaid', blocks)
        self.assertNotIn('data-document-math', blocks)
        self.assertNotIn('data-document-footnote', blocks)

    def test_math_pipes_do_not_split_table_cells(self):
        row = converter.split_table_row(r'| Norma | $|x|$ y \(\lVert y\rVert\) |')
        self.assertEqual(row, ['Norma', r'$|x|$ y \(\lVert y\rVert\)'])
        document = converter.render_blocks([r'| Norma | $|x|$ |', '| --- | --- |', '| A | $a_b$ |'])
        self.assertEqual(document.count('<th '), 2)
        self.assertEqual(document.count('<td '), 2)
        self.assertEqual(document.count('data-document-math'), 2)

    def test_display_forms_preserve_tex_and_source_locations(self):
        for lines in ([r'$$\frac{a}{b}$$'], [r'\[\frac{a}{b}\]'],
                      ['$$', r'\frac{a}{b}', '$$'], [r'\[', r'\frac{a}{b}', r'\]']):
            with self.subTest(lines=lines):
                document = converter.render_blocks(lines, line_numbers=list(range(12, 12 + len(lines))))
                self.assertEqual(document.count('data-document-math="display"'), 1)
                self.assertIn('data-source-line="12"', document)
                self.assertIn(r'\frac{a}{b}</div>', document)

    def test_mermaid_is_an_image_that_receives_ordinary_figure_identity(self):
        body = converter.render_blocks(['Figura: Flujo {#fig:flujo}', '', '```mermaid',
                                        'flowchart LR', 'A[Inicio] --> B[Fin]', '```'])
        document, structure = converter.load_support_module('document_structure').prepare_document(
            '<main>' + body + '<p>Consulte ' + converter.render_inline('[@fig:flujo]') + '</p></main>')
        self.assertEqual(structure['figures'][0]['reference_id'], 'fig:flujo')
        self.assertIn('Figura 1. Flujo', document)
        self.assertIn('data-document-mermaid=', document)
        self.assertNotIn('language-mermaid', document)

    def test_explicit_unclosed_or_empty_technical_blocks_fail_with_location(self):
        for lines in (['```mermaid', 'flowchart LR'], ['```mermaid', '```'],
                      ['$$', 'x'], ['$$', '$$'], [r'\[', 'x']):
            with self.subTest(lines=lines), self.assertRaisesRegex(converter.ConversionError, 'línea 7'):
                converter.render_blocks(lines, line_numbers=list(range(7, 7 + len(lines))))
        with self.assertRaisesRegex(converter.ConversionError, 'línea 9'):
            converter.render_inline(r'Texto \(x', source_line=9)

    def test_engine_browser_reports_technical_dependency_without_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'technical.md'
            source.write_text('# Informe\n\n$x$\n', encoding='utf-8')
            with patch.object(converter, 'render_with_browser') as browser:
                with self.assertRaisesRegex(converter.ConversionError, 'fórmulas.*requieren Playwright'):
                    converter.convert(converter.parse_args([str(source), '--engine', 'browser',
                        '--no-branding', '--no-toc', '--no-bookmarks']))
            browser.assert_not_called()
            self.assertFalse(source.with_suffix('.pdf').exists())

    def test_math_alone_reuses_the_local_environment_but_literal_examples_do_not(self):
        converter.load_support_module('document_metadata')
        converter.load_support_module('technical_rendering')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'document.md'
            local = root / '.venv' / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
            local.parent.mkdir(parents=True)
            local.write_text('placeholder')
            for body, expected in [('$x$', True), ('`$x$`', False), (r'\$5', False),
                                   ('```mermaid\nflowchart LR\nA --> B\n```', True),
                                   ('````markdown\n```mermaid\nA --> B\n```\n````', False)]:
                source.write_text('# Informe\n\n' + body, encoding='utf-8')
                args = converter.parse_args([str(source), '--no-branding', '--no-toc', '--no-bookmarks'])
                with self.subTest(body=body), patch.object(converter, 'SKILL_DIR', root), \
                     patch.object(converter, 'playwright_available', return_value=False), \
                     patch.object(converter, 'pypdf_available', return_value=False), \
                     patch.dict(os.environ, {}, clear=True), patch.object(converter.os, 'execve') as execute:
                    converter.use_local_environment(args, [str(source)])
                self.assertEqual(execute.called, expected)


if __name__ == '__main__':
    unittest.main()
