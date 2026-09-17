"""Configuration, source locations and inline syntax for PDF-03/04/05."""

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "convert_markdown_to_pdf.py"
SPEC = importlib.util.spec_from_file_location("mdpdf_advanced_conversion", SCRIPT)
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)


class AdvancedConversionTests(unittest.TestCase):
    def test_reference_and_anchor_syntax_respects_code_escapes_and_link_labels(self):
        rendered = converter.render_inline(
            r"[@tbl:datos] `[@tbl:codigo]` \[@tbl:literal] [@tbl:enlace](https://example.com) "
            r"{#fig:flujo} `{#fig:codigo}` \{#fig:literal}")
        self.assertEqual(rendered.count('data-document-reference='), 1)
        self.assertEqual(rendered.count('data-document-anchor='), 1)
        self.assertIn('<code>[@tbl:codigo]</code>', rendered)
        self.assertIn('href="https://example.com">@tbl:enlace</a>', rendered)
        self.assertIn('<code>{#fig:codigo}</code>', rendered)

    def test_source_lines_include_yaml_and_nested_blocks(self):
        source = ('---\npdf:\n  indice_tablas: true\n---\n# Documento\n\n'
                  '> ![Imagen](missing.png)\n\n- Texto\n  [Destino](#ausente)\n\n'
                  '| Dato | Valor |\n| --- | --- |\n| A | [Enlace](#otro) |\n')
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'document.md'
            path.write_text(source, encoding='utf-8')
            document, _, presentation = converter.build_document(path, None, 'A4', False, False)
        parser = converter.load_support_module('document_structure')._DocumentParser()
        parser.feed(document)
        nodes = list(converter.load_support_module('document_structure')._walk(parser.root))
        self.assertEqual(next(n.get('data-source-line') for n in nodes if n.tag == 'img'), '7')
        self.assertEqual([n.get('data-source-line') for n in nodes if n.tag == 'a'], ['10', '14'])
        self.assertTrue(presentation['table_index'])
        self.assertFalse(presentation['figure_index'])
        self.assertFalse(presentation['strict'])

    def test_yaml_options_preserve_explicit_false_and_strict_mode(self):
        metadata = converter.load_support_module('document_metadata')
        _, _, options = metadata.read_configuration(
            '---\npdf:\n  indice_tablas: false\n  indice_figuras: true\n  validacion: estricta\n---\nTexto')
        self.assertEqual(options, {'indice_tablas': False, 'indice_figuras': True, 'validacion': 'estricta'})
        for option, value in [('indice_tablas', 'yes'), ('indice_figuras', '"true"'),
                              ('indice_tablas', 'null'), ('validacion', 'false'), ('validacion', '{}')]:
            with self.subTest(option=option, value=value), self.assertRaisesRegex(ValueError, 'línea 3'):
                metadata.read_configuration(f'---\npdf:\n  {option}: {value}\n---\nTexto')

    def test_cli_distinguishes_absence_from_overrides(self):
        absent = converter.parse_args(['document.md'])
        self.assertIsNone(absent.table_index)
        self.assertIsNone(absent.figure_index)
        self.assertIsNone(absent.strict)
        explicit = converter.parse_args(['document.md', '--table-index', '--no-figure-index', '--no-strict'])
        self.assertTrue(explicit.table_index)
        self.assertFalse(explicit.figure_index)
        self.assertFalse(explicit.strict)

    def test_strict_validation_reuses_local_dependencies_without_page_furniture(self):
        converter.load_support_module('document_metadata')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'document.md'
            source.write_text('---\npdf:\n  validacion: estricta\n---\nTexto.', encoding='utf-8')
            local = root / '.venv' / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
            local.parent.mkdir(parents=True)
            local.write_text('placeholder', encoding='utf-8')
            for flags, expected in [([], True), (['--strict'], True), (['--no-strict'], False)]:
                args = converter.parse_args([str(source), '--no-branding', '--no-toc', '--no-bookmarks', *flags])
                with self.subTest(flags=flags), patch.object(converter, 'SKILL_DIR', root), \
                     patch.object(converter, 'playwright_available', return_value=False), \
                     patch.object(converter, 'pypdf_available', return_value=False), \
                     patch.object(converter, 'yaml_available', return_value=True), \
                     patch.dict(os.environ, {}, clear=True), patch.object(converter.os, 'execve') as execute:
                    converter.use_local_environment(args, [str(source)])
                self.assertEqual(execute.called, expected)


if __name__ == '__main__':
    unittest.main()
