"""Document navigation and captions preserve the converter's body content."""

import importlib.util
import re
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "document_structure.py"
SPEC = importlib.util.spec_from_file_location("mdpdf_structure_tests", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
prepare_document = module.prepare_document

METADATA = (
    '<table><thead><tr><th>Dato</th><th>Valor</th></tr></thead><tbody>'
    '<tr><td>Versión</td><td>0.1</td></tr><tr><td>Estado</td><td>Borrador</td></tr>'
    '<tr><td>Fecha</td><td>2026-09-07</td></tr></tbody></table>'
)
TABLE = '<table><thead><tr><th>Campo</th><th>Regla</th></tr></thead><tbody><tr><td>id</td><td>Único</td></tr></tbody></table>'


def wrap(body):
    return '<!doctype html><html lang="es"><head><title>Documento</title><style>body { color: #111; }</style></head><body><main>' + body + '</main></body></html>'


class ContentsTests(unittest.TestCase):
    def test_ers_subtitle_and_metadata_stay_before_index(self):
        document = wrap('<h1 id="doc">ERS</h1><h2 id="sistema">Sistema de ejemplo</h2><blockquote>Base de requisitos.</blockquote>' + METADATA + '<h2 id="alcance">1. Propósito y alcance</h2><p>Alcance real.</p><h3 id="exclusiones">1.1 Exclusiones</h3>')
        result, structure = prepare_document(document)
        self.assertEqual([entry['id'] for entry in structure['entries']], ['alcance', 'exclusiones'])
        self.assertEqual([entry['role'] for entry in structure['headings']], ['title', 'subtitle', 'section', 'section'])
        self.assertLess(result.index('Base de requisitos.'), result.index('<nav '))
        self.assertLess(result.index('</table>'), result.index('<nav '))
        self.assertLess(result.index('</nav>'), result.index('<h2 id="alcance">'))
        self.assertEqual(result.count('<table'), 1)
        self.assertNotIn('data-document-generated="toc-break"', result)

    def test_first_unnumbered_section_is_not_assumed_to_be_subtitle(self):
        result, structure = prepare_document(wrap('<h1>Documento</h1><h2>Introducción</h2><p>Texto.</p><h2>Detalles</h2>'))
        self.assertEqual([entry['title'] for entry in structure['entries']], ['Introducción', 'Detalles'])
        self.assertLess(result.index('<nav '), result.index('>Introducción</h2>'))

    def test_numbered_section_next_to_title_is_included(self):
        _, structure = prepare_document(wrap('<h1>Documento</h1><h2>1. Requisitos</h2>' + METADATA + '<h2>2. Pruebas</h2>'))
        self.assertEqual([entry['title'] for entry in structure['entries']], ['1. Requisitos', '2. Pruebas'])

    def test_depth_is_relative_to_highest_section_level(self):
        document = wrap('<h1>Documento</h1><h2>A</h2><h3>B</h3><h4>C</h4><h2>D</h2>')
        _, structure = prepare_document(document, toc_depth=2)
        self.assertEqual([entry['title'] for entry in structure['entries']], ['A', 'B', 'D'])
        self.assertEqual([entry['toc_level'] for entry in structure['entries']], [1, 2, 1])
        self.assertEqual([entry['level'] for entry in structure['entries']], [2, 3, 2])
        _, shallow = prepare_document(document, toc_depth=1)
        self.assertEqual([entry['title'] for entry in shallow['entries']], ['A', 'D'])

    def test_document_without_title_includes_its_first_heading(self):
        _, structure = prepare_document(wrap('<p>Introducción breve.</p><h2>Contenido</h2>'))
        self.assertEqual([entry['title'] for entry in structure['entries']], ['Contenido'])

    def test_document_without_sections_omits_empty_index(self):
        result, structure = prepare_document(wrap('<h1>Documento</h1><p>Solo texto.</p>'))
        self.assertNotIn('<nav', result)
        self.assertEqual(structure['entries'], [])
        self.assertIsNone(structure['toc_id'])

    def test_index_has_safe_targets_and_placeholders(self):
        result, structure = prepare_document(wrap('<h1>Documento</h1><h2 id="revisión">1. Revisión &amp; &lt;riesgos&gt;</h2>'))
        self.assertIn('href="#revisión"', result)
        self.assertIn('data-toc-target="revisión">…</span>', result)
        self.assertIn('class="document-toc-leader"', result)
        self.assertIn('data-toc-level="1"', result)
        self.assertEqual(structure['entries'][0]['title'], '1. Revisión & <riesgos>')
        self.assertNotIn('<riesgos>', result)

    def test_existing_and_generated_ids_are_unique(self):
        result, structure = prepare_document(wrap('<h1 id="doc">Documento</h1><h2 id="duplicado">A</h2><h2 id="duplicado">B</h2><p id="table-1">Registro.</p>' + TABLE))
        ids = re.findall(r'\bid="([^"]+)"', result)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(structure['tables'][0]['id'], 'table-1-1')
        for entry in structure['entries']:
            self.assertIn(f'id="{entry["id"]}"', result)
            self.assertIn(f'data-toc-target="{entry["id"]}"', result)

    def test_disabled_index_preserves_registry(self):
        result, structure = prepare_document(wrap('<h1>Documento</h1><h2>Requisitos</h2>'), with_toc=False)
        self.assertNotIn('<nav', result)
        self.assertEqual(len(structure['entries']), 1)

    def test_invalid_depth_fails_explicitly(self):
        for value in (0, 7, True, '2'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                prepare_document(wrap('<h1>Documento</h1>'), toc_depth=value)


class CaptionTests(unittest.TestCase):
    def test_metadata_table_is_numbered_without_duplication(self):
        result, structure = prepare_document(wrap('<h1>Documento</h1>' + METADATA + '<h2>1. Requisitos</h2>' + TABLE))
        self.assertEqual([row['caption'] for row in structure['tables']], ['Tabla 1. Datos del documento', 'Tabla 2. Requisitos'])
        self.assertEqual(result.count('<table'), 2)
        self.assertEqual(result.count('>0.1</td>'), 1)

    def test_explicit_table_caption_preserves_inline_markup_and_links(self):
        source = '<h1>Documento</h1><h2>Campos</h2><p><strong>Tabla:</strong> Reglas de <a href="#campo"><code>campo</code></a></p>' + TABLE
        result, structure = prepare_document(wrap(source), with_toc=False)
        self.assertEqual(structure['tables'][0]['title'], 'Reglas de campo')
        self.assertRegex(result, r'<caption[^>]*>Tabla 1\..*<a href="#campo"><code>campo</code></a></caption>')
        self.assertNotIn('Tabla:</strong>', result)
        self.assertEqual(result.count('Reglas de '), 1)

    def test_table_fallback_uses_headers_without_a_section(self):
        _, structure = prepare_document(wrap(TABLE), with_toc=False)
        self.assertEqual(structure['tables'][0]['title'], 'Campo / Regla')

    def test_only_table_section_fallback_loses_section_number(self):
        source = wrap(
            '<h1>Documento</h1><h2 id="componentes">1.2 Componentes del documento</h2>'
            + TABLE + '<p>Tabla: 2.1 Formato explícito</p>' + TABLE
        )
        result, structure = prepare_document(source)
        self.assertEqual(structure['tables'][0]['caption'], 'Tabla 1. Componentes del documento')
        self.assertEqual(structure['tables'][1]['caption'], 'Tabla 2. 2.1 Formato explícito')
        self.assertEqual(structure['headings'][1]['title'], '1.2 Componentes del documento')
        self.assertEqual(structure['entries'][0]['title'], '1.2 Componentes del documento')
        self.assertEqual(structure['entries'][0]['id'], 'componentes')
        self.assertIn('<h2 id="componentes">1.2 Componentes del documento</h2>', result)

    def test_fallback_preserves_a_leading_number_that_is_not_a_section_prefix(self):
        _, structure = prepare_document(wrap('<h1>Documento</h1><h2>2026 Plan de pruebas</h2>' + TABLE))
        self.assertEqual(structure['tables'][0]['title'], '2026 Plan de pruebas')

    def test_numbering_is_global_in_quotes_and_lists(self):
        source = '<h1>Documento</h1><h2>Reglas</h2>' + TABLE + '<blockquote>' + TABLE + '</blockquote><ul><li>' + TABLE + '</li></ul>'
        result, structure = prepare_document(wrap(source), with_toc=False)
        self.assertEqual([row['number'] for row in structure['tables']], [1, 2, 3])
        self.assertEqual(result.count('<caption'), 3)

    def test_standalone_linked_image_gets_semantic_figure(self):
        source = '<h1>Documento</h1><h2>Diseño</h2><p><a href="plano.png"><img src="plano.png" alt="Plano general"></a></p>'
        result, structure = prepare_document(wrap(source), with_toc=False)
        self.assertIn('<figure ', result)
        self.assertIn('<a href="plano.png"><img ', result)
        self.assertIn('>Figura 1. Plano general</figcaption>', result)
        self.assertEqual(structure['figures'][0]['id'], 'figure-1')
        self.assertNotRegex(result, r'<p>\s*<figure')

    def test_inline_image_preserves_prose_and_link_semantics(self):
        source = '<h1>Documento</h1><p>Consulte <a href="detalle.png"><img src="detalle.png" alt="Detalle"></a> para continuar.</p>'
        result, structure = prepare_document(wrap(source), with_toc=False)
        self.assertIn('<p>Consulte <a href="detalle.png"><span ', result)
        self.assertIn('role="figure"', result)
        self.assertIn('</span></a> para continuar.</p>', result)
        self.assertNotIn('<figure ', result)
        self.assertEqual(len(structure['figures']), 1)

    def test_explicit_figure_caption_overrides_title_and_alt(self):
        source = '<h1>Documento</h1><p>Figura: Flujo <em>principal</em></p><p><img src="flujo.png" title="Título" alt="Alternativo"></p>'
        result, structure = prepare_document(wrap(source), with_toc=False)
        self.assertEqual(structure['figures'][0]['title'], 'Flujo principal')
        self.assertIn('>Figura 1. Flujo <em>principal</em></figcaption>', result)
        self.assertEqual(result.count('Flujo '), 1)

    def test_image_title_then_alt_then_generic_fallback(self):
        source = '<p><img src="a.png" title="Título" alt="Alternativo"></p><p><img src="b.png" alt="Alternativo"></p><p><img src="c.png"></p>'
        _, structure = prepare_document(wrap(source), with_toc=False)
        self.assertEqual([row['title'] for row in structure['figures']], ['Título', 'Alternativo', 'Imagen del documento'])

    def test_template_logos_and_heading_images_are_not_figures(self):
        source = '<html><body><header><img src="header.png"></header><main><h1><img src="title.png">Documento</h1><p class="logo"><img src="logo.png"></p><p><img src="body.png" alt="Diagrama"></p></main><footer><img src="footer.png"></footer></body></html>'
        _, structure = prepare_document(source, with_toc=False)
        self.assertEqual([row['src'] for row in structure['figures']], ['body.png'])

    def test_captions_can_be_disabled_without_removing_explicit_text(self):
        source = '<h1>Documento</h1><p>Tabla: Reglas</p>' + TABLE + '<p><img src="a.png" alt="Plano"></p>'
        result, structure = prepare_document(wrap(source), with_toc=False, with_captions=False)
        self.assertIn('<p>Tabla: Reglas</p>', result)
        self.assertNotIn('<caption', result)
        self.assertNotIn('<figure', result)
        self.assertEqual(len(structure['tables']), 1)
        self.assertEqual(len(structure['figures']), 1)

    def test_repeated_preparation_does_not_duplicate_navigation_or_captions(self):
        source = wrap('<h1>Documento</h1>' + METADATA + '<h2>Requisitos</h2>' + TABLE + '<p><img src="a.png" alt="Plano"></p>')
        first, first_structure = prepare_document(source)
        second, second_structure = prepare_document(first)
        self.assertEqual(first_structure, second_structure)
        self.assertEqual(second.count('<nav '), 1)
        self.assertEqual(second.count('<caption '), 2)
        self.assertEqual(second.count('<figcaption '), 1)
        self.assertNotIn('Tabla 1. Tabla 1.', second)
        self.assertNotIn('Figura 1. Figura 1.', second)

    def test_requirement_ids_and_escaped_html_are_not_rewritten(self):
        body = '<h1>Documento</h1><h2>Reglas</h2><p><strong>RF-ADM-01.</strong> Texto &lt;script&gt; &amp; datos.</p>' + TABLE
        result, _ = prepare_document(wrap(body), with_toc=False)
        self.assertIn('<strong>RF-ADM-01.</strong> Texto &lt;script&gt; &amp; datos.', result)
        self.assertIn('<style>body { color: #111; }</style>', result)


if __name__ == '__main__':
    unittest.main()
