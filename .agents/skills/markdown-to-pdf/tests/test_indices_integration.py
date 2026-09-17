"""Verify all three indices and stable references against final browser PDFs."""

import importlib.util
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('mdpdf_indices_integration', SKILL / 'scripts/convert_markdown_to_pdf.py')
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)


def normalized(value):
    return re.sub(r'\s+', ' ', value or '').strip()


@unittest.skipUnless(os.environ.get('MDPDF_BROWSER_TESTS') == '1', 'Requiere MDPDF_BROWSER_TESTS=1')
class IndicesIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='mdpdf-indices-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'document.md'
        shutil.copyfile(SKILL / 'assets/ejemplo/recursos/flujo.svg', self.root / 'flujo.svg')
        self.navigation = converter.load_support_module('pdf_navigation')
        self.structure = converter.load_support_module('document_structure')

    def render(self, markdown, flags=()):
        self.source.write_text(markdown, encoding='utf-8')
        args = converter.parse_args([str(self.source), *flags])
        output, _ = converter.convert(args)
        self.assertEqual(self.source.read_text(encoding='utf-8'), markdown)
        return output, args

    def test_cover_and_three_indices_keep_physical_pages_and_both_anchor_styles(self):
        from pypdf import PdfReader
        source = '''---
documento:
  titulo: "Documento integrado"
  codigo: "DOC-03"
pdf:
  portada: true
  indice_tablas: true
  indice_figuras: true
  validacion: estricta
---
Introducción conservada.

## 1. Contenido

Consulte [@tbl:estados] y [@fig:flujo].

Tabla: Estados {#tbl:estados}

| Estado | Detalle |
| --- | --- |
| Listo | Comprobado |

Figura: Flujo {#fig:flujo}

![Flujo](flujo.svg)

[Enlace anterior a la tabla](#table-2) y [a la figura](#figure-1).
'''
        output, args = self.render(source)
        self.assertFalse(args.validation_diagnostics)
        entries = [{'id': value, 'title': value} for value in
                   ['1-contenido', 'table-1', 'table-2', 'tbl:estados', 'figure-1', 'fig:flujo']]
        pages = self.navigation.resolve_toc_pages(output, entries)
        self.assertEqual(pages['table-1'], 1)
        self.assertEqual(pages['1-contenido'], 5)
        self.assertEqual(pages['table-2'], pages['tbl:estados'])
        self.assertEqual(pages['figure-1'], pages['fig:flujo'])
        with PdfReader(str(output)) as reader:
            texts = [normalized(page.extract_text()) for page in reader.pages]
        self.assertIn('Índice de tablas', texts[2])
        self.assertIn('Índice de figuras', texts[3])
        self.assertIn('Tabla 1. Datos del documento 1', texts[2])
        self.assertIn('Tabla 2. Estados 5', texts[2])
        self.assertIn('Figura 1. Flujo 5', texts[3])
        self.assertIn('Consulte Tabla 2 y Figura 1.', texts[4])
        self.assertNotIn('Página 1 de', texts[0])
        self.assertNotIn('{#tbl:', ' '.join(texts))

    def test_indices_are_independent_of_toc_captions_and_yaml_overrides(self):
        from pypdf import PdfReader
        source = '''---
pdf:
  indice_tablas: true
  indice_figuras: true
  validacion: estricta
---
# Informe

## Resultados

Consulte [@tbl:datos].

Tabla: Datos {#tbl:datos}

| A | B |
| --- | --- |
| Uno | Dos |

![Proceso](flujo.svg)
'''
        output, args = self.render(source, ['--no-toc', '--no-figure-index', '--no-captions', '--no-strict'])
        self.assertFalse(args.strict)
        self.assertEqual(args.toc_entries_count, 0)
        self.assertEqual(args.table_index_count, 1)
        self.assertEqual(args.figure_index_count, 0)
        with PdfReader(str(output)) as reader:
            text = normalized(' '.join(page.extract_text() for page in reader.pages))
        self.assertIn('Índice de tablas', text)
        self.assertNotIn('Índice de figuras', text)
        self.assertIn('Consulte Tabla 1.', text)
        self.assertNotIn('{#tbl:', text)
        self.navigation.validate_navigation(output, [{'id': 'tbl:datos', 'title': 'Datos'}])

    def test_multipage_lists_print_the_final_page_of_every_table_and_figure(self):
        from pypdf import PdfReader
        parts = ['---', 'documento:', '  titulo: "Listados extensos"', 'pdf:',
                 '  portada: true', '  indice_tablas: true', '  indice_figuras: true', '---',
                 '## Inventario', '']
        for number in range(1, 71):
            parts.extend([f'Tabla: Registro {number:02d} {{#tbl:registro-{number}}}', '',
                          '| A | B |', '| --- | --- |', '| Uno | Dos |', '',
                          f'Figura: Proceso {number:02d} {{#fig:proceso-{number}}}', '',
                          '![Proceso](flujo.svg)', ''])
        css = self.root / 'compact.css'
        css.write_text('main figure img { height: 12mm; width: auto; }', encoding='utf-8')
        output, args = self.render('\n'.join(parts), ['--css', str(css)])
        html, _, _ = converter.build_document(self.source, css, 'A4', False, True)
        _, structure = self.structure.prepare_document(html, with_table_index=True, with_figure_index=True)
        pages = self.navigation.validate_navigation(output, structure['navigation_entries'])
        with PdfReader(str(output)) as reader:
            texts = [normalized(page.extract_text()) for page in reader.pages]
        first_body = pages['inventario'] - 1
        index_text = ' '.join(texts[1:first_body])
        self.assertGreaterEqual(first_body, 6)
        for entry in structure['navigation_entries']:
            with self.subTest(identifier=entry['id']):
                self.assertRegex(index_text, re.escape(entry['title']) + r'\s+' + str(pages[entry['id']]) + r'\b')
        self.assertEqual(args.table_index_count, 70)
        self.assertEqual(args.figure_index_count, 70)

    def test_reordering_updates_visible_reference_and_keeps_destination(self):
        from pypdf import PdfReader
        table = lambda label, identifier: f'Tabla: {label} {{#tbl:{identifier}}}\n\n| A | B |\n| --- | --- |\n| Uno | Dos |\n\n'
        for first in ('base', 'extra'):
            source = '# Informe\n\n## Datos\n\nConsulte [@tbl:base].\n\n'
            source += table('Base', 'base') + table('Extra', 'extra') if first == 'base' else table('Extra', 'extra') + table('Base', 'base')
            output, _ = self.render(source, ['--no-toc', '--force'])
            with PdfReader(str(output)) as reader:
                text = normalized(' '.join(page.extract_text() for page in reader.pages))
            number = 1 if first == 'base' else 2
            self.assertIn(f'Consulte Tabla {number}.', text)
            self.navigation.validate_navigation(output, [{'id': 'tbl:base', 'title': 'Base'}])


if __name__ == '__main__':
    unittest.main()
