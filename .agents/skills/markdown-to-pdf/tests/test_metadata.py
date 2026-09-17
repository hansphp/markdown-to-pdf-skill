"""Metadata precedence, source preservation, validation and document navigation."""

import importlib.util
import re
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name + "_tests", SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


metadata = load("document_metadata")
structure = load("document_structure")


def wrap(body):
    return '<!doctype html><html><head><title>Anterior</title></head><body><main>' + body + '</main></body></html>'


def table(rows, attrs=""):
    return '<table' + attrs + '><thead><tr><th>Dato</th><th>Valor</th></tr></thead><tbody>' + ''.join(
        '<tr><td>' + key + '</td><td>' + value + '</td></tr>' for key, value in rows
    ) + '</tbody></table>'


def resolve(body, config=None, overrides=None):
    return metadata.resolve_document(wrap(body), config, overrides or {}, "archivo", structure)


class FrontMatterTests(unittest.TestCase):
    def test_text_fields_and_literal_punctuation_preserve_their_format(self):
        source = '---\ndocumento:\n  titulo: "Informe **literal**"\n  version: "01.20"\n  fecha: "2026-09-13"\n  codigo: "001"\n---\n\n## Contenido\n'
        original = source[:]
        body, config = metadata.read_frontmatter(source)
        self.assertEqual(body, '\n## Contenido\n')
        self.assertEqual(config, {'titulo': 'Informe **literal**', 'version': '01.20',
                                  'fecha': '2026-09-13', 'codigo': '001'})
        self.assertEqual(source, original)

    def test_explicit_empty_values_remain_distinguishable_from_absent_fields(self):
        _, config = metadata.read_frontmatter('---\ndocumento:\n  titulo: null\n  version: ""\n---\nTexto')
        self.assertEqual(config, {'titulo': '', 'version': ''})
        self.assertNotIn('fecha', config)
        self.assertEqual(metadata.read_frontmatter('---\ndocumento: {}\n---\nTexto'), ('Texto', {}))

    def test_unrelated_frontmatter_needs_no_yaml_and_keeps_legacy_input(self):
        source = '---\nauthor: alguien\nother: [invalid yaml\n---\n# Documento'
        with mock.patch.dict('sys.modules', {'yaml': None}):
            self.assertFalse(metadata.has_metadata_frontmatter(source))
            self.assertEqual(metadata.read_frontmatter(source), (source, None))

    def test_fenced_examples_and_body_yaml_are_not_configuration(self):
        for source in ('# Documento\n```yaml\n---\ndocumento:\n  titulo: ejemplo\npdf:\n  portada: true\n---\n```',
                       '```yaml\n---\ndocumento:\n  titulo: ejemplo\n---\n```',
                       '> ---\n> pdf:\n>   portada: true\n> ---',
                       '```yaml\n---\npdf:\n  portada: true\n---\n```'):
            with self.subTest(source=source), mock.patch.dict('sys.modules', {'yaml': None}):
                self.assertEqual(metadata.read_frontmatter(source), (source, None))
                self.assertEqual(metadata.read_configuration(source), (source, None, {}))
                self.assertFalse(metadata.has_metadata_frontmatter(source))

    def test_missing_yaml_has_an_actionable_local_dependency_error(self):
        source = '---\ndocumento: {}\n---\nTexto'
        with mock.patch.dict('sys.modules', {'yaml': None}):
            self.assertTrue(metadata.has_metadata_frontmatter(source))
            with self.assertRaisesRegex(ValueError, r'PyYAML.*\.venv.*requirements'):
                metadata.read_frontmatter(source)

    def test_duplicate_fields_and_duplicate_document_maps_fail_with_line_number(self):
        for source, line in (
            ('---\ndocumento:\n  titulo: A\n  titulo: B\n---\nTexto', 4),
            ('---\ndocumento: {}\ndocumento: {}\n---\nTexto', 3),
        ):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, f'línea {line}.*duplicada'):
                metadata.read_frontmatter(source)

    def test_unknown_document_field_fails_but_unrelated_root_keys_are_allowed(self):
        with self.assertRaisesRegex(ValueError, r'línea 3.*documento\.autor.*desconocido'):
            metadata.read_frontmatter('---\ndocumento:\n  autor: Otra persona\n---\nTexto')
        _, config = metadata.read_frontmatter('---\nauthor: Alguien\ndocumento:\n  titulo: Informe\n---\nTexto')
        self.assertEqual(config, {'titulo': 'Informe'})

    def test_unquoted_numbers_dates_and_booleans_must_be_quoted(self):
        for field, value in (('version', '0.10'), ('fecha', '2026-09-13'), ('estado', 'true'),
                             ('codigo', '001'), ('titulo', '[a, b]')):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, r'línea 3.*entre comillas'):
                metadata.read_frontmatter(f'---\ndocumento:\n  {field}: {value}\n---\nTexto')

    def test_invalid_yaml_and_invalid_document_map_fail(self):
        for source in ('---\ndocumento:\n  titulo: [sin cierre\n---\nTexto',
                       '---\ndocumento: Texto\n---\nTexto'):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, r'Metadatos YAML inválidos.*línea'):
                metadata.read_frontmatter(source)

    def test_relevant_unclosed_frontmatter_is_an_error(self):
        with self.assertRaisesRegex(ValueError, 'cierre ---'):
            metadata.read_frontmatter('---\ndocumento:\n  titulo: Informe\n\n# Texto')

    def test_pdf_options_are_separate_from_document_metadata_and_preserve_source(self):
        source = '---\ndocumento:\n  titulo: "Informe **literal**"\npdf:\n  portada: true\n  logo: "./recursos/mi logo.svg"\n---\n\n## Contenido\n'
        original = source[:]
        body, config, options = metadata.read_configuration(source)
        self.assertEqual(body, '\n## Contenido\n')
        self.assertEqual(config, {'titulo': 'Informe **literal**'})
        self.assertEqual(options, {'portada': True, 'logo': './recursos/mi logo.svg'})
        self.assertEqual(metadata.read_frontmatter(source), (body, config))
        self.assertEqual(source, original)

    def test_absent_pdf_options_are_not_defaults_or_explicit_overrides(self):
        for options, expected in (('{}', {}), ('null', {}), ('', {}),
                                  ('{portada: false}', {'portada': False}),
                                  ('{logo: null}', {'logo': None})):
            source = f'---\npdf: {options}\n---\nTexto'
            with self.subTest(options=options):
                self.assertTrue(metadata.has_metadata_frontmatter(source))
                self.assertEqual(metadata.read_configuration(source), ('Texto', None, expected))
        self.assertEqual(metadata.read_configuration('---\ndocumento: {}\n---\nTexto'),
                         ('Texto', {}, {}))
        self.assertEqual(metadata.read_configuration('# Texto'), ('# Texto', None, {}))

    def test_pdf_only_frontmatter_requires_the_local_yaml_dependency(self):
        source = '---\npdf:\n  portada: true\n---\nTexto'
        with mock.patch.dict('sys.modules', {'yaml': None}):
            self.assertTrue(metadata.has_metadata_frontmatter(source))
            with self.assertRaisesRegex(ValueError, r'PyYAML.*\.venv.*requirements'):
                metadata.read_configuration(source)

    def test_cover_requires_a_real_true_or_false_boolean(self):
        for value, expected in (('true', True), ('false', False), ('TRUE', True), ('False', False)):
            with self.subTest(value=value):
                _, _, options = metadata.read_configuration(f'---\npdf:\n  portada: {value}\n---\nTexto')
                self.assertIs(options['portada'], expected)
        for value in ('"true"', '"false"', '1', '0', 'null', '[]', '{}', 'yes', 'no', 'on', 'off'):
            with self.subTest(value=value), self.assertRaisesRegex(
                    ValueError, r'línea 3, columna 12.*pdf\.portada.*true o false'):
                metadata.read_configuration(f'---\npdf:\n  portada: {value}\n---\nTexto')

    def test_logo_paths_remain_relative_or_absolute_until_the_caller_resolves_them(self):
        for value in ('./recursos/logo.png', '../marca/mi logo.svg', '/tmp/logos/empresa.jpg'):
            with self.subTest(value=value):
                _, _, options = metadata.read_configuration(f'---\npdf:\n  logo: "{value}"\n---\nTexto')
                self.assertEqual(options, {'logo': value})

    def test_logo_rejects_empty_nontext_and_remote_values(self):
        for value in ('""', '"  "', 'false', '123', '[]', '{}',
                      'https://example.com/logo.png', '//example.com/logo.svg',
                      'data:image/png;base64,abc', 'file:///tmp/logo.png', '"logo\\0.png"'):
            with self.subTest(value=value), self.assertRaisesRegex(
                    ValueError, r'línea 3, columna 9.*pdf\.logo.*ruta local'):
                metadata.read_configuration(f'---\npdf:\n  logo: {value}\n---\nTexto')

    def test_unsupported_pdf_configuration_fails_instead_of_disappearing(self):
        with self.assertRaisesRegex(ValueError, r'línea 3, columna 3.*pdf\.papel.*desconocida'):
            metadata.read_configuration('---\npdf:\n  papel: Letter\n---\nTexto')
        for value in ('false', '0', 'Texto', '[]'):
            with self.subTest(value=value), self.assertRaisesRegex(
                    ValueError, r'línea 2, columna 6.*pdf debe ser un mapa'):
                metadata.read_configuration(f'---\npdf: {value}\n---\nTexto')

    def test_duplicate_pdf_options_and_maps_fail_with_source_location(self):
        for source, line, column in (
            ('---\npdf:\n  portada: true\n  portada: false\n---\nTexto', 4, 3),
            ('---\npdf:\n  logo: null\n  logo: logo.png\n---\nTexto', 4, 3),
            ('---\npdf: {}\npdf: {}\n---\nTexto', 3, 1),
        ):
            with self.subTest(source=source), self.assertRaisesRegex(
                    ValueError, f'línea {line}, columna {column}.*duplicada'):
                metadata.read_configuration(source)

    def test_bom_crlf_and_yaml_end_delimiter(self):
        body, config = metadata.read_frontmatter('\ufeff---\r\ndocumento:\r\n  titulo: Informe\r\n...\r\n# Texto\r\n')
        self.assertEqual(body, '# Texto\r\n')
        self.assertEqual(config, {'titulo': 'Informe'})

    def test_flow_mapping_and_unrelated_nested_metadata_are_supported(self):
        body, config = metadata.read_frontmatter('---\n{"documento": {"titulo": "Informe"}, "otro": {2026: "dato"}}\n---\nTexto')
        self.assertEqual(body, 'Texto')
        self.assertEqual(config, {'titulo': 'Informe'})


class ResolutionTests(unittest.TestCase):
    def test_unconfigured_document_is_identical_and_keeps_legacy_footer(self):
        source = wrap('<h1 id="doc">Documento <em>actual</em></h1><h2>Introducción</h2>' + table([
            ('Versión', '0.1'), ('Estado', 'Borrador'), ('Clasificación', 'PÚBLICO')]))
        result, data = metadata.resolve_document(source, None, {}, 'archivo', structure)
        self.assertEqual(result, source)
        self.assertEqual(data['titulo'], 'Documento actual')
        self.assertEqual(data['subtitulo'], 'Introducción')
        self.assertEqual(data['clasificacion'], 'CONFIDENCIAL')
        self.assertEqual(resolve('<p>Texto.</p>')[1]['titulo'], 'archivo')

    def test_cli_then_yaml_then_initial_markdown_fields(self):
        body = '<h1 id="documento">Anterior</h1>' + table([
            ('Código del documento', 'ERS-001'), ('Versión', '0.1'), ('Fecha', '2025-01-01'),
            ('Estado', 'Borrador'), ('Clasificación', 'INTERNO'), ('Organización', 'Proyecto')
        ]) + '<h2 id="alcance">1. Alcance</h2><p>Versión del cuerpo: 0.1.</p>'
        result, data = resolve(body, {'titulo': 'Nuevo', 'version': '0.2', 'estado': 'Revisión'},
                               {'version': '1.0', 'estado': 'Aprobado'})
        self.assertEqual(data, {'titulo': 'Nuevo', 'subtitulo': '', 'codigo': 'ERS-001',
                                'version': '1.0', 'fecha': '2025-01-01', 'estado': 'Aprobado',
                                'clasificacion': 'INTERNO'})
        self.assertIn('<title>Nuevo</title>', result)
        self.assertIn('<h1 id="documento" data-document-role="title">Nuevo</h1>', result)
        self.assertEqual(result.count('<table'), 1)
        self.assertEqual(result.count('>1.0</td>'), 1)
        self.assertNotIn('>Revisión</td>', result)
        self.assertIn('<td>Organización</td><td>Proyecto</td>', result)
        self.assertIn('<p>Versión del cuerpo: 0.1.</p>', result)

    def test_change_in_one_source_updates_all_generated_title_values(self):
        body = '<h1 id="doc">Original</h1>' + table([('Título', 'Original'), ('Versión', '0.1')]) + '<h2>1. Requisitos</h2>'
        for title in ('Primera entrega', 'Segunda entrega'):
            result, data = resolve(body, {'titulo': title})
            self.assertEqual(data['titulo'], title)
            self.assertEqual(result.count(title), 2)  # HTML title and H1; no duplicate table row.
            self.assertNotIn('Original', result)

    def test_table_only_title_and_subtitle_move_into_headings_without_duplicate_rows(self):
        body = table([('Título', '<strong id="nombre">Viejo</strong>'), ('Subtítulo', 'Anterior'),
                      ('Estado', 'Borrador')]) + '<h2 id="alcance">1. Alcance</h2>'
        result, data = resolve(body, {'titulo': 'Nuevo', 'subtitulo': 'Sistema'})
        self.assertEqual(data['titulo'], 'Nuevo')
        self.assertEqual(result.count('>Nuevo</h1>'), 1)
        self.assertEqual(result.count('>Sistema</h2>'), 1)
        self.assertNotIn('<td>Título</td>', result)
        self.assertNotIn('<td>Subtítulo</td>', result)
        self.assertIn('id="nombre"', result)
        self.assertIn('<td>Estado</td><td>Borrador</td>', result)

    def test_inherited_table_headings_keep_inline_content_and_anchors(self):
        title = ('<strong id="nombre">Informe</strong> '
                 '<span data-document-math="inline">\\frac{a}{b}</span>'
                 '<sup data-document-footnote="titulo">[^titulo]</sup>')
        subtitle = ('<a id="referencia" href="#alcance"><em>Sistema</em></a> '
                    '<span data-document-math="inline">x^2</span>'
                    '<sup data-document-footnote="subtitulo">[^subtitulo]</sup>')
        result, _ = resolve(table([('Título', title), ('Subtítulo', subtitle),
                                   ('Estado', 'Borrador')]) + '<h2 id="alcance">1. Alcance</h2>', {})
        self.assertIn('<h1 data-document-role="title">' + title + '</h1>', result)
        self.assertIn('<h2 data-document-role="subtitle">' + subtitle + '</h2>', result)
        self.assertEqual(result.count('id="nombre"'), 1)
        self.assertEqual(result.count('id="referencia"'), 1)
        self.assertEqual(result.count('data-document-footnote="titulo"'), 1)
        self.assertEqual(result.count('data-document-footnote="subtitulo"'), 1)
        self.assertNotIn('<td>Título</td>', result)
        self.assertNotIn('<td>Subtítulo</td>', result)
        self.assertIn('<td>Estado</td><td>Borrador</td>', result)

    def test_explicit_table_heading_overrides_remain_plain_text_when_text_matches(self):
        for field, label, tag in (('titulo', 'Título', 'h1'), ('subtitulo', 'Subtítulo', 'h2')):
            value = r'Informe \frac{a}{b}[^nota]'
            cell = ('<strong id="anterior">Informe</strong> '
                    '<span data-document-math="inline">\\frac{a}{b}</span>'
                    '<sup data-document-footnote="nota">[^nota]</sup>')
            for config, overrides in (({field: value}, {}), ({}, {field: value})):
                with self.subTest(field=field, config=config, overrides=overrides):
                    result, _ = resolve(table([(label, cell)]), config, overrides)
                    self.assertIn('>' + value + '</' + tag + '>', result)
                    self.assertNotIn('data-document-math', result)
                    self.assertNotIn('data-document-footnote', result)
                    self.assertNotIn('<strong', result)
                    self.assertEqual(result.count('id="anterior"'), 1)

    def test_generated_metadata_omits_absent_fields_and_does_not_invent_a_title(self):
        result, data = resolve('<h2>1. Alcance</h2><p>Texto.</p>', {'version': '01.20'})
        self.assertEqual(data['titulo'], '')
        self.assertEqual(data['subtitulo'], '')
        self.assertEqual(data['fecha'], '')
        self.assertEqual(data['clasificacion'], 'CONFIDENCIAL')
        self.assertNotIn('<h1', result)
        self.assertNotIn('CONFIDENCIAL', result)
        self.assertEqual(result.count('<td>'), 2)
        enriched, registry = structure.prepare_document(result)
        self.assertEqual(registry['tables'][0]['title'], 'Datos del documento')
        self.assertEqual([entry['title'] for entry in registry['entries']], ['1. Alcance'])
        self.assertLess(enriched.index('</table>'), enriched.index('<nav '))

    def test_existing_first_h2_is_preserved_as_section_when_yaml_adds_subtitle(self):
        result, data = resolve('<h1 id="doc">Documento</h1><h2 id="intro">Introducción</h2><p>Texto.</p>',
                               {'subtitulo': 'Sistema de ejemplo', 'version': '1.0'})
        self.assertEqual(data['subtitulo'], 'Sistema de ejemplo')
        self.assertEqual(result.count('<h2'), 2)
        enriched, registry = structure.prepare_document(result)
        self.assertEqual([entry['id'] for entry in registry['entries']], ['intro'])
        self.assertEqual([entry['role'] for entry in registry['headings']], ['title', 'subtitle', 'section'])
        self.assertLess(enriched.index('Sistema de ejemplo'), enriched.index('<nav '))

    def test_adding_metadata_does_not_turn_a_section_into_a_subtitle(self):
        result, _ = resolve('<h1>Documento</h1><h2>Detalles generales</h2><p>Sección real.</p><h2>1. Requisitos</h2>',
                            {'version': '1.0', 'estado': 'Borrador'})
        _, registry = structure.prepare_document(result)
        self.assertEqual([entry['title'] for entry in registry['entries']], ['Detalles generales', '1. Requisitos'])

    def test_recognized_ers_subtitle_updates_without_duplication(self):
        body = '<h1 id="ers">ERS</h1><h2 id="sistema">Sistema anterior</h2><blockquote>Contexto.</blockquote>' + table([
            ('Versión', '0.1'), ('Estado', 'Borrador')]) + '<h2 id="alcance">1. Alcance</h2>'
        result, data = resolve(body, {'subtitulo': 'Sistema actual'})
        self.assertEqual(data['subtitulo'], 'Sistema actual')
        self.assertEqual(result.count('<h2'), 2)
        self.assertIn('<h2 id="sistema" data-document-role="subtitle">Sistema actual</h2>', result)
        self.assertIn('<blockquote>Contexto.</blockquote>', result)
        _, registry = structure.prepare_document(result)
        self.assertEqual([entry['id'] for entry in registry['entries']], ['alcance'])

    def test_body_tables_and_change_history_are_never_metadata_sources_or_targets(self):
        body = '<h1>Documento</h1><h2 id="historia">Control de cambios</h2>' + table([
            ('Versión', '0.1'), ('Estado', 'Anterior')]) + '<h2>1. Alcance</h2><p>Original.</p>'
        original_table = table([('Versión', '0.1'), ('Estado', 'Anterior')])
        result, data = resolve(body, {'version': '1.0'})
        self.assertEqual(data['estado'], '')
        self.assertIn(original_table, result)
        self.assertEqual(result.count('<table'), 2)
        self.assertLess(result.index('>1.0</td>'), result.index('>Control de cambios</h2>'))

    def test_quoted_or_listed_headings_and_tables_are_preserved_as_body_content(self):
        for container in ('blockquote', 'li'):
            quoted_table = table([('Versión', '0.1'), ('Estado', 'Anterior')])
            body = f'<{container}><h1 id="cita">Cita</h1>' + quoted_table + f'</{container}><h2 id="alcance">1. Alcance</h2>'
            result, data = resolve(body, {'titulo': 'Nuevo', 'version': '1.0'})
            self.assertIn('id="cita" data-document-role="section">Cita</h1>', result)
            self.assertIn(quoted_table, result)
            self.assertEqual(data['estado'], '')
            self.assertEqual(result.count('<table'), 2)
            self.assertLess(result.index('>Nuevo</h1>'), result.index(f'<{container}>'))
            _, registry = structure.prepare_document(result)
            self.assertEqual([entry['id'] for entry in registry['entries']], ['cita', 'alcance'])

    def test_explicit_empty_values_remove_layout_keep_link_targets_and_do_not_fall_back(self):
        body = '<h1 id="doc">Documento</h1><h2 id="sistema">Sistema</h2>' + table([
            ('Versión', '<strong id="version-anterior">0.1</strong>'), ('Estado', 'Borrador'),
            ('Clasificación', 'INTERNO')], ' id="datos"') + '<h2 id="alcance">1. Alcance</h2><p><a href="#doc">Inicio</a></p>'
        result, data = resolve(body, {'titulo': '', 'subtitulo': '', 'version': '', 'estado': '', 'clasificacion': ''})
        self.assertTrue(all(data[field] == '' for field in ('titulo', 'subtitulo', 'version', 'estado', 'clasificacion')))
        self.assertNotIn('<h1', result)
        self.assertNotIn('<table', result)
        for identifier in ('doc', 'sistema', 'version-anterior', 'datos', 'alcance'):
            self.assertIn(f'id="{identifier}"', result)
        self.assertNotIn('CONFIDENCIAL', result)
        _, registry = structure.prepare_document(result)
        self.assertEqual([entry['id'] for entry in registry['entries']], ['alcance'])

    def test_removing_title_does_not_reclassify_a_body_h1_as_title(self):
        result, _ = resolve('<h1 id="doc">Documento</h1><h1 id="seccion">Primera sección</h1><p>Texto.</p>', {'titulo': ''})
        _, registry = structure.prepare_document(result)
        self.assertEqual([entry['id'] for entry in registry['entries']], ['seccion'])

    def test_literal_html_and_markdown_in_metadata_are_not_executed_or_formatted(self):
        value = '<script>alert("x")</script> & **texto**'
        result, data = resolve('<h2>1. Alcance</h2>', {'titulo': value, 'codigo': value})
        self.assertEqual(data['titulo'], value)
        self.assertNotIn('<script>', result)
        self.assertNotIn('<strong>', result)
        self.assertIn('&lt;script&gt;alert("x")&lt;/script&gt; &amp; **texto**', result)

    def test_new_generated_ids_do_not_break_existing_links_and_remain_stable(self):
        result, _ = resolve('<h2 id="section-1">1. Alcance</h2><p><a href="#section-1">Ver alcance</a></p>',
                            {'titulo': 'Informe', 'subtitulo': 'Sistema', 'version': '1.0'})
        enriched, registry = structure.prepare_document(result)
        ids = re.findall(r'\bid="([^"]+)"', enriched)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(registry['entries'][0]['id'], 'section-1')
        self.assertIn('href="#section-1"', enriched)
        second, _ = metadata.resolve_document(result, {'titulo': 'Informe', 'subtitulo': 'Sistema', 'version': '1.0'},
                                               {}, 'archivo', structure)
        self.assertEqual(second, result)


if __name__ == '__main__':
    unittest.main()
