"""Independent lists and stable references follow the final document order."""

import importlib.util
import re
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "document_structure.py"
SPEC = importlib.util.spec_from_file_location("mdpdf_indices_tests", SCRIPT)
structure_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(structure_module)
prepare_document = structure_module.prepare_document

TABLE = '<table><tr><th>Campo</th><th>Regla</th></tr><tr><td>id</td><td>Único</td></tr></table>'
IMAGE = '<p><img src="flujo.svg" alt="Flujo"></p>'


def wrap(body):
    return f'<html><body><main>{body}</main></body></html>'


def anchor(identifier):
    return f'<span data-document-anchor="{identifier}">{{#{identifier}}}</span>'


def reference(identifier):
    return f'<span data-document-reference="{identifier}">[@{identifier}]</span>'


def table(identifier, title="Estados"):
    return f'<p>Tabla: {title} {anchor(identifier)}</p>{TABLE}'


def figure(identifier, title="Flujo"):
    return f'<p>Figura: {title} {anchor(identifier)}</p>{IMAGE}'


class IndependentIndexTests(unittest.TestCase):
    def test_indices_keep_inline_math_and_emphasis_without_duplicate_ids_or_links(self):
        formula = '<span id="equation" data-document-math="inline" data-source-line="7">\\frac{a}{b}</span>'
        note = ('<sup class="document-footnote-reference" id="note-call">'
                '<a href="#note" role="doc-noteref">1</a></sup>')
        source = wrap('<h1>Documento</h1><h2 id="section"><strong>Razón</strong> ' + formula + note + '</h2>'
                      + table('tbl:razon', '<em>Medidas</em> ' + formula.replace('id="equation" ', ''))
                      + figure('fig:razon', '<a href="https://example.com"><strong>Esquema</strong></a> '
                               + formula.replace('id="equation" ', ''))
                      + '<p id="note">Definición.</p>')
        for captions in (False, True):
            with self.subTest(captions=captions):
                result, registry = prepare_document(source, with_captions=captions,
                                                     with_table_index=True, with_figure_index=True)
                parser = structure_module._DocumentParser()
                parser.feed(result)
                nodes = list(structure_module._walk(parser.root))
                ids = [node.get('id') for node in nodes if node.get('id')]
                self.assertEqual(len(ids), len(set(ids)))
                labels = [node for node in nodes if node.get('class') == 'document-toc-label']
                self.assertEqual(len(labels), 3)
                for label in labels:
                    descendants = list(structure_module._walk(label))
                    self.assertTrue(any(node.get('data-document-math') == 'inline' for node in descendants))
                    self.assertFalse(any(node.tag == 'a' or node.get('id') for node in descendants))
                self.assertIn('<strong>Razón</strong>', structure_module._serialize(labels[0]))
                self.assertIn('[1]', structure_module._serialize(labels[0]))
                self.assertEqual(result.count('role="doc-noteref"'), 1)
                self.assertIn('<em>Medidas</em>', registry['tables'][0]['title_html'])
                self.assertIn('<strong>Esquema</strong>', registry['figures'][0]['title_html'])
                second, repeated = prepare_document(result, with_captions=captions,
                                                     with_table_index=True, with_figure_index=True)
                self.assertEqual(second, result)
                self.assertEqual(repeated, registry)

    def test_inferred_caption_preserves_heading_math_and_copies_notes_as_plain_text(self):
        formula = '<span id="formula" data-document-math="inline">x^2</span>'
        note = ('<sup class="document-footnote-reference"><a id="call" href="#note" '
                'role="doc-noteref">2</a></sup>')
        source = wrap('<h1>Documento</h1><h2>1. <em>Potencia</em> ' + formula + note + '</h2>'
                      + TABLE + '<p id="note">Nota.</p>')
        result, registry = prepare_document(source, with_table_index=True)
        self.assertIn('<caption data-document-caption="tabla" class="document-table-caption">'
                      'Tabla 1. <em>Potencia</em> <span data-document-math="inline">x^2</span>[2]</caption>', result)
        self.assertEqual(result.count('id="formula"'), 1)
        self.assertEqual(result.count('id="call"'), 1)
        self.assertEqual(result.count('role="doc-noteref"'), 1)
        self.assertEqual(registry['tables'][0]['title'], 'Potencia x^2[2]')
        second, repeated = prepare_document(result, with_table_index=True)
        self.assertEqual(result, second)
        self.assertEqual(registry, repeated)

    def test_inferred_header_caption_preserves_formulas_without_section_headings(self):
        source = wrap('<h1>Documento</h1><table><tr><th><em>Campo</em></th><th>'
                      '<span data-document-math="inline">a^2</span></th></tr>'
                      '<tr><td>A</td><td>B</td></tr></table>')
        for captions in (False, True):
            with self.subTest(captions=captions):
                result, registry = prepare_document(source, with_captions=captions, with_table_index=True)
                self.assertEqual(registry['tables'][0]['title'], 'Campo / a^2')
                self.assertIn('<em>Campo</em> / <span data-document-math="inline">a^2</span>', result)

    def test_each_list_has_independent_activation_and_registry(self):
        source = wrap('<h1>Documento</h1><h2>Contenido</h2>' + TABLE + IMAGE)
        for toc in (False, True):
            for tables in (False, True):
                for figures in (False, True):
                    with self.subTest(toc=toc, tables=tables, figures=figures):
                        result, registry = prepare_document(source, with_toc=toc,
                            with_table_index=tables, with_figure_index=figures)
                        self.assertEqual(bool(registry['toc_id']), toc)
                        self.assertEqual(bool(registry['table_index_id']), tables)
                        self.assertEqual(bool(registry['figure_index_id']), figures)
                        expected = (([registry['entries'][0]['id']] if toc else [])
                                    + (['table-1'] if tables else [])
                                    + (['figure-1'] if figures else []))
                        self.assertEqual([row['id'] for row in registry['navigation_entries']], expected)
                        self.assertEqual(result.count('<nav '), sum((toc, tables, figures)))
                        self.assertEqual(len(registry['entries']), 1)

    def test_lists_show_caption_numbers_titles_links_and_real_page_placeholders(self):
        result, registry = prepare_document(wrap(table('tbl:estados', 'Estados &amp; permisos')
                                                 + figure('fig:flujo', 'Flujo &lt;principal&gt;')),
                                             with_table_index=True, with_figure_index=True)
        self.assertIn('>Tabla 1. Estados &amp; permisos</span>', result)
        self.assertIn('>Figura 1. Flujo &lt;principal&gt;</span>', result)
        self.assertIn('href="#table-1"', result)
        self.assertIn('data-toc-target="figure-1">…</span>', result)
        self.assertEqual([row['kind'] for row in registry['navigation_entries']], ['table', 'figure'])

    def test_empty_lists_are_omitted(self):
        result, registry = prepare_document(wrap('<h1>Documento</h1><p>Texto.</p>'),
                                             with_table_index=True, with_figure_index=True)
        self.assertNotIn('<nav ', result)
        self.assertEqual(registry['navigation_entries'], [])
        self.assertIsNone(registry['table_index_id'])
        self.assertIsNone(registry['figure_index_id'])

    def test_lists_work_without_visible_captions_or_section_index(self):
        result, registry = prepare_document(wrap(table('tbl:estados') + figure('fig:flujo')),
                                             with_toc=False, with_captions=False,
                                             with_table_index=True, with_figure_index=True)
        self.assertEqual([row['title'] for row in registry['navigation_entries']],
                         ['Tabla 1. Estados', 'Figura 1. Flujo'])
        self.assertNotIn('<caption', result)
        self.assertNotIn('<figcaption', result)
        self.assertEqual(result.count('<nav '), 2)

    def test_all_lists_follow_cover_and_precede_introductory_body(self):
        cover = '<section data-document-role="cover"><h1 data-document-role="title">Documento</h1></section>'
        result, _ = prepare_document(wrap(cover + '<p>Introducción libre.</p><h2>Contenido</h2>' + TABLE + IMAGE),
                                     with_table_index=True, with_figure_index=True)
        self.assertLess(result.index('</section>'), result.index('data-document-generated="toc"'))
        self.assertLess(result.index('data-document-generated="toc"'), result.index('data-document-generated="table-index"'))
        self.assertLess(result.index('data-document-generated="table-index"'), result.index('data-document-generated="figure-index"'))
        self.assertLess(result.rindex('</nav>'), result.index('Introducción libre.'))

    def test_without_cover_metadata_remains_before_lists(self):
        metadata = '<table data-document-role="metadata"><tr><td>Código</td><td>DOC-1</td></tr></table>'
        result, registry = prepare_document(wrap('<h1>Documento</h1>' + metadata + '<h2>Contenido</h2>' + TABLE),
                                             with_table_index=True)
        self.assertLess(result.index('DOC-1'), result.index('<nav '))
        self.assertLess(result.rindex('</nav>'), result.index('>Contenido</h2>'))
        self.assertEqual(len(registry['tables']), 2)

    def test_without_sections_lists_follow_metadata_and_precede_body(self):
        metadata = '<table data-document-role="metadata"><tr><td>Código</td><td>DOC-1</td></tr></table>'
        result, registry = prepare_document(wrap('<h1>Documento</h1>' + metadata + '<p>Introducción libre.</p>' + IMAGE),
                                             with_table_index=True, with_figure_index=True)
        self.assertEqual(registry['entries'], [])
        self.assertLess(result.index('DOC-1'), result.index('<nav '))
        self.assertLess(result.rindex('</nav>'), result.index('Introducción libre.'))

    def test_long_lists_keep_unique_targets_and_all_rows(self):
        source = wrap('<h1>Documento</h1><h2>Catálogo</h2>' + ''.join(
            table(f'tbl:registro-{number}', f'Registro {number}') + figure(f'fig:registro-{number}')
            for number in range(95)))
        result, registry = prepare_document(source, with_table_index=True, with_figure_index=True)
        targets = re.findall(r'data-toc-target="([^"]+)"', result)
        self.assertEqual(len(targets), 191)
        self.assertEqual(len(targets), len(set(targets)))
        self.assertEqual(targets, [row['id'] for row in registry['navigation_entries']])

    def test_preparation_is_idempotent_with_all_lists_and_references(self):
        source = wrap('<h1>Documento</h1><h2>Contenido</h2><p>Ver ' + reference('tbl:estados')
                      + ' y ' + reference('fig:flujo') + '.</p>' + table('tbl:estados') + figure('fig:flujo'))
        first, first_registry = prepare_document(source, with_table_index=True, with_figure_index=True)
        second, second_registry = prepare_document(first, with_table_index=True, with_figure_index=True)
        self.assertEqual(first_registry, second_registry)
        self.assertEqual(first, second)


class StableReferenceTests(unittest.TestCase):
    def test_forward_references_update_inferred_captions_and_all_navigation_labels(self):
        source = wrap('<h1>Documento</h1><h2>1. <em>Detalle de</em> ' + reference('tbl:otra') + '</h2>'
                      + TABLE + table('tbl:otra', 'Otra'))
        for captions in (False, True):
            with self.subTest(captions=captions):
                result, registry = prepare_document(source, with_captions=captions, with_table_index=True)
                self.assertNotIn('[@tbl:otra]', result)
                self.assertEqual(registry['entries'][0]['title'], '1. Detalle de Tabla 2')
                self.assertEqual(registry['tables'][0]['title'], 'Detalle de Tabla 2')
                self.assertEqual(registry['navigation_entries'][1]['title'], 'Tabla 1. Detalle de Tabla 2')
                if captions:
                    self.assertIn('Tabla 1. <em>Detalle de</em>', result)
                second, repeated = prepare_document(result, with_captions=captions, with_table_index=True)
                self.assertEqual(result, second)
                self.assertEqual(registry, repeated)

    def test_forward_references_resolve_to_stable_aliases_and_keep_legacy_targets(self):
        source = wrap('<p>Véase ' + reference('tbl:estados') + ' y ' + reference('fig:flujo') + '.</p>'
                      + table('tbl:estados') + figure('fig:flujo'))
        result, registry = prepare_document(source, with_toc=False)
        self.assertIn('href="#tbl:estados" class="document-reference">Tabla 1</a>', result)
        self.assertIn('href="#fig:flujo" class="document-reference">Figura 1</a>', result)
        for identifier in ('tbl:estados', 'fig:flujo', 'table-1', 'figure-1'):
            self.assertEqual(len(re.findall(rf'\sid="{re.escape(identifier)}"', result)), 1)
        self.assertEqual(registry['tables'][0]['reference_id'], 'tbl:estados')
        self.assertNotIn('{#tbl:estados}', result)

    def test_reordering_and_insertion_update_numbers_without_rewriting_reference_source(self):
        references = '<p>' + reference('tbl:estados') + ', ' + reference('fig:flujo') + '</p>'
        original = wrap(references + table('tbl:estados') + figure('fig:flujo'))
        reordered = wrap(references + table('tbl:otra') + figure('fig:otra')
                         + table('tbl:estados') + figure('fig:flujo'))
        first, _ = prepare_document(original, with_toc=False)
        second, registry = prepare_document(reordered, with_toc=False)
        self.assertIn('class="document-reference">Tabla 1</a>', first)
        self.assertIn('class="document-reference">Figura 1</a>', first)
        self.assertIn('href="#tbl:estados" class="document-reference">Tabla 2</a>', second)
        self.assertIn('href="#fig:flujo" class="document-reference">Figura 2</a>', second)
        self.assertEqual(registry['tables'][1]['reference_id'], 'tbl:estados')

    def test_caption_markup_and_escaped_characters_survive_id_removal(self):
        source = wrap(table('tbl:estados', '<strong>Estados</strong> &amp; <em>permisos</em>'))
        result, registry = prepare_document(source, with_toc=False)
        self.assertIn('Tabla 1. <strong>Estados</strong> &amp; <em>permisos</em></caption>', result)
        self.assertEqual(registry['tables'][0]['title'], 'Estados & permisos')

    def test_caption_id_can_be_inside_inline_emphasis(self):
        source = wrap('<p>Tabla: <strong>Estados ' + anchor('tbl:estados') + '</strong></p>' + TABLE)
        result, registry = prepare_document(source, with_toc=False)
        self.assertIn('Tabla 1. <strong>Estados</strong></caption>', result)
        self.assertEqual(registry['tables'][0]['reference_id'], 'tbl:estados')

    def test_references_work_without_captions_and_preparation_remains_stable(self):
        source = wrap('<p>' + reference('tbl:estados') + ' y ' + reference('fig:flujo') + '</p>'
                      + table('tbl:estados') + figure('fig:flujo'))
        first, registry = prepare_document(source, with_toc=False, with_captions=False)
        second, again = prepare_document(first, with_toc=False, with_captions=False)
        self.assertEqual(first, second)
        self.assertEqual(registry, again)
        self.assertNotIn('<caption', first)
        self.assertNotIn('<figure ', first)
        self.assertIn('class="document-reference">Tabla 1</a>', first)
        self.assertIn('id="tbl:estados"', first)
        self.assertIn('id="fig:flujo"', first)
        self.assertIn('<p>Tabla: Estados</p>', first)

    def test_missing_reference_reports_id_and_block(self):
        with self.assertRaisesRegex(ValueError, r'Referencia sin destino: tbl:ausente.*Véase'):
            prepare_document(wrap('<p>Véase ' + reference('tbl:ausente') + '.</p>'))

    def test_duplicate_explicit_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, r'duplicado: tbl:estados'):
            prepare_document(wrap(table('tbl:estados') + table('tbl:estados')))

    def test_explicit_id_collision_with_an_existing_html_target_is_rejected(self):
        with self.assertRaisesRegex(ValueError, r'tbl:estados.*otro elemento'):
            prepare_document(wrap('<h2 id="tbl:estados">Estados</h2>' + table('tbl:estados')))

    def test_invalid_explicit_declarations_include_source_line(self):
        marked_table = table('tbl:estados').replace('<p>', '<p data-source-line="42">', 1)
        wrong_kind = table('fig:estados').replace('<p>', '<p data-source-line="42">', 1)
        for source in (table('tbl:estados') + marked_table,
                       '<h2 id="tbl:estados">Estados</h2>' + marked_table,
                       wrong_kind):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'línea 42'):
                prepare_document(wrap(source))

    def test_table_and_figure_identifiers_have_distinct_namespaces(self):
        with self.assertRaisesRegex(ValueError, 'Identificador de tabla no válido'):
            prepare_document(wrap(table('fig:estados')))
        with self.assertRaisesRegex(ValueError, 'Identificador de figura no válido'):
            prepare_document(wrap(figure('tbl:flujo')))

    def test_code_and_escaped_caption_id_syntax_stays_literal(self):
        for literal in ('<code>{#tbl:literal}</code>', '{#tbl:literal}'):
            with self.subTest(literal=literal):
                result, registry = prepare_document(wrap('<p>Tabla: Ejemplo ' + literal + '</p>' + TABLE),
                                                     with_toc=False)
                self.assertNotIn('reference_id', registry['tables'][0])
                self.assertIn(literal, result)

    def test_code_reference_is_not_resolved_even_if_marked_by_external_html(self):
        literal = '<pre><code>' + reference('tbl:ausente') + '</code></pre>'
        result, _ = prepare_document(wrap(literal))
        self.assertIn(literal, result)
        self.assertNotIn('document-reference"', result)

    def test_nonterminal_caption_anchor_is_literal(self):
        source = wrap('<p>Tabla: ' + anchor('tbl:literal') + ' se escribe al final</p>' + TABLE)
        result, registry = prepare_document(source, with_toc=False)
        self.assertNotIn('reference_id', registry['tables'][0])
        self.assertIn('{#tbl:literal}', result)

    def test_reference_inside_section_heading_updates_the_index_label(self):
        source = wrap('<h1>Documento</h1><h2>Explicación de ' + reference('tbl:estados') + '</h2>'
                      + table('tbl:estados'))
        result, registry = prepare_document(source)
        self.assertEqual(registry['entries'][0]['title'], 'Explicación de Tabla 1')
        self.assertIn('>Explicación de Tabla 1</span>', result)

    def test_caption_with_reference_uses_resolved_text_in_its_list(self):
        source = wrap(table('tbl:estados', 'Estados del ' + reference('fig:flujo')) + figure('fig:flujo'))
        result, registry = prepare_document(source, with_table_index=True)
        self.assertEqual(registry['tables'][0]['caption'], 'Tabla 1. Estados del Figura 1')
        self.assertIn('>Tabla 1. Estados del Figura 1</span>', result)


if __name__ == '__main__':
    unittest.main()
