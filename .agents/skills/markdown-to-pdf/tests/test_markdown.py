"""Fidelity regressions for the dependency-free Markdown subset."""

import importlib.util
import re
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "convert_markdown_to_pdf.py"
SPEC = importlib.util.spec_from_file_location("mdpdf_markdown_tests", SCRIPT)
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)


class InlineTests(unittest.TestCase):
    def test_literal_backticks_inside_code(self):
        self.assertEqual(converter.render_inline("`` `texto` ``"), "<code>`texto`</code>")
        self.assertEqual(converter.render_inline("``a ` b``"), "<code>a ` b</code>")

    def test_code_preserves_backslashes_and_markup(self):
        self.assertEqual(
            converter.render_inline(r'`\ / **texto** <dato>`'),
            '<code>\\ / **texto** &lt;dato&gt;</code>',
        )

    def test_unmatched_code_delimiter_is_literal(self):
        self.assertEqual(converter.render_inline("``sin cierre `"), "``sin cierre `")

    def test_escaped_punctuation_is_not_formatted(self):
        self.assertEqual(
            converter.render_inline(r'\*literal\* y \_campo\_ y \\servidor'),
            '*literal* y _campo_ y \\servidor',
        )

    def test_text_cannot_collide_with_internal_tokens(self):
        self.assertEqual(
            converter.render_inline('Literal @@MDPDFTOKEN0@@ y `campo`'),
            'Literal @@MDPDFTOKEN0@@ y <code>campo</code>',
        )

    def test_link_label_supports_code_and_emphasis(self):
        self.assertEqual(
            converter.render_inline('[`equipo_id` y **regla**](#equipo_id)'),
            '<a href="#equipo_id"><code>equipo_id</code> y <strong>regla</strong></a>',
        )

    def test_link_destination_preserves_balanced_parentheses(self):
        self.assertEqual(
            converter.render_inline('[ruta](docs/informe_(final).md)'),
            '<a href="docs/informe_(final).md">ruta</a>',
        )
        self.assertEqual(
            converter.render_inline(r'[ruta](docs/informe_\(final\).md)'),
            '<a href="docs/informe_(final).md">ruta</a>',
        )

    def test_angle_destination_and_title(self):
        self.assertEqual(
            converter.render_inline('[ruta](<docs/informe final.md> "Versión final")'),
            '<a href="docs/informe final.md" title="Versión final">ruta</a>',
        )

    def test_image_keeps_escaped_safe_attributes(self):
        self.assertEqual(
            converter.render_inline('![Plano "A"](images/plano_(1).png)'),
            '<img src="images/plano_(1).png" alt="Plano &quot;A&quot;">',
        )

    def test_html_and_script_urls_remain_inert(self):
        self.assertEqual(converter.render_inline('<script>texto</script>'), '&lt;script&gt;texto&lt;/script&gt;')
        self.assertEqual(converter.render_inline('[texto](javascript:alert(1))'), '<a href="#">texto</a>')

    def test_hard_breaks_and_soft_line_wrapping(self):
        self.assertEqual(converter.render_inline('uno  \ndos\\\ntres\ncuatro'), 'uno<br>\ndos<br>\ntres cuatro')

    def test_nested_basic_emphasis(self):
        self.assertEqual(converter.render_inline('**texto *énfasis***'), '<strong>texto <em>énfasis</em></strong>')
        self.assertEqual(converter.render_inline('***texto***'), '<strong><em>texto</em></strong>')


class TableTests(unittest.TestCase):
    def test_requirement_characters_are_not_lost(self):
        line = r'| Campo | Excepto `\ / : * ? " < >` y la barra vertical. |'
        self.assertEqual(converter.split_table_row(line)[1], r'Excepto `\ / : * ? " < >` y la barra vertical.')

    def test_escaped_pipe_remains_in_code_cell(self):
        rendered = converter.render_blocks([
            '| Campo | Regla |', '| --- | --- |', r'| `valor` | `a\|b` y `C:\datos` |',
        ])
        self.assertIn('<code>a|b</code> y <code>C:\\datos</code>', rendered)
        self.assertEqual(rendered.count('<td '), 2)

    def test_even_backslashes_do_not_escape_a_delimiter(self):
        self.assertEqual(converter.split_table_row(r'| a\\| b |'), [r'a\\', 'b'])

    def test_final_escaped_pipe_is_content(self):
        self.assertEqual(converter.split_table_row(r'| a | b\|'), ['a', 'b|'])


class HeadingTests(unittest.TestCase):
    def test_accented_internal_link_resolves(self):
        rendered = converter.render_blocks([
            '[Revisión](#10-lista-de-revisión-y-criterio-de-terminación)', '',
            '## 10. Lista de revisión y criterio de terminación',
        ])
        target = re.search(r'href="#([^"]+)"', rendered).group(1)
        self.assertIn(f'id="{target}"', rendered)

    def test_duplicate_and_naturally_numbered_headings_are_unique(self):
        used = {}
        headings = ['Configuración', 'Configuración', 'Configuración-1', 'Configuración']
        slugs = [converter.slugify(heading, used) for heading in headings]
        self.assertEqual(slugs, ['configuración', 'configuración-1', 'configuración-1-1', 'configuración-2'])
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_slug_uses_visible_heading_text(self):
        self.assertEqual(converter.slugify('`equipo_id`', {}), 'equipo_id')
        self.assertEqual(converter.slugify('[Revisión](docs/informe_(final).md)', {}), 'revisión')
        self.assertEqual(converter.plain_heading_text('**Campo** `equipo_id`'), 'Campo equipo_id')

    def test_spanish_guide_anchors(self):
        headings = [
            '3. Estructura que deberá tener cada ERS',
            '6. Criterios de aceptación y trazabilidad',
            'Anexo B. Instrucción reutilizable para generar una ERS',
        ]
        expected = [
            '3-estructura-que-deberá-tener-cada-ers',
            '6-criterios-de-aceptación-y-trazabilidad',
            'anexo-b-instrucción-reutilizable-para-generar-una-ers',
        ]
        self.assertEqual([converter.slugify(heading, {}) for heading in headings], expected)


class BlockTests(unittest.TestCase):
    def test_nested_list_preserves_parent_child_relationship(self):
        rendered = converter.render_blocks(['- Padre', '  - Hijo', '    detalle', '  - Otro', '- Siguiente'])
        self.assertIn('<li>Padre\n<ul><li>Hijo detalle</li><li>Otro</li></ul></li>', rendered)
        self.assertTrue(rendered.endswith('<li>Siguiente</li></ul>'))

    def test_ordered_list_can_contain_tasks(self):
        rendered = converter.render_blocks(['3. Revisión', '   - [x] Verificado', '   - [ ] Pendiente', '4. Entrega'])
        self.assertTrue(rendered.startswith('<ol start="3"><li>Revisión\n<ul>'))
        self.assertIn('<input type="checkbox" disabled checked>Verificado', rendered)
        self.assertIn('<input type="checkbox" disabled>Pendiente', rendered)
        self.assertTrue(rendered.endswith('<li>Entrega</li></ol>'))

    def test_acceptance_continuation_stays_inside_its_item(self):
        rendered = converter.render_blocks([
            '- **CA-01.** Requisitos: RF-01.',
            '  Dado un registro, cuando se consulta, entonces se muestra.',
            '- **CA-02.** Otra condición.',
        ])
        self.assertEqual(rendered.count('<ul>'), 1)
        self.assertIn('RF-01. Dado un registro, cuando se consulta, entonces se muestra.</li>', rendered)

    def test_list_can_contain_a_second_paragraph(self):
        rendered = converter.render_blocks(['- Regla', '', '  Detalle de la regla.', '', 'Fuera de la lista.'])
        self.assertIn('<li><p>Regla</p>\n<p>Detalle de la regla.</p></li>', rendered)
        self.assertTrue(rendered.endswith('<p>Fuera de la lista.</p>'))

    def test_code_fence_inside_list_is_not_reinterpreted(self):
        rendered = converter.render_blocks(['- Ejemplo', '', '  ```text', '  **literal**', '  ```', '- Otra regla'])
        self.assertIn('<pre><code class="language-text">**literal**</code></pre>', rendered)
        self.assertIn('<li>Otra regla</li>', rendered)

    def test_paragraph_hardbreak_survives_block_processing(self):
        self.assertEqual(converter.render_blocks(['Primera línea  ', 'Segunda línea']), '<p>Primera línea<br>\nSegunda línea</p>')

    def test_frontmatter_is_not_confused_with_horizontal_rules(self):
        ordinary = ['---', 'Texto importante', '---', 'Fin']
        self.assertEqual(converter.strip_frontmatter(ordinary), ordinary)
        self.assertIn('Texto importante', converter.render_blocks(converter.strip_frontmatter(ordinary)))

    def test_mapping_frontmatter_is_removed(self):
        self.assertEqual(
            converter.strip_frontmatter(['---', '# Metadatos', 'title: Informe', 'version: 1', '---', '# Texto']),
            ['# Texto'],
        )

    def test_unclosed_frontmatter_is_preserved(self):
        original = ['---', 'title: Informe', '# Contenido']
        self.assertEqual(converter.strip_frontmatter(original), original)


if __name__ == '__main__':
    unittest.main()
