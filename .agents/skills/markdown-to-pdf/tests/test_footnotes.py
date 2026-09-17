"""Markdown note parsing, source diagnostics and linked document-end notes."""

import importlib.util
import re
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "convert_markdown_to_pdf.py"
SPEC = importlib.util.spec_from_file_location("mdpdf_footnotes_converter_tests", SCRIPT)
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)
notes = converter.load_support_module("document_footnotes")
structure = converter.load_support_module("document_structure")


def wrap(body):
    return '<!doctype html><html><head><title>Documento</title></head><body><main>' + body + '</main></body></html>'


def marker(identifier, line=1):
    return f'<sup data-document-footnote="{identifier}" data-source-line="{line}">[^{identifier}]</sup>'


def definitions(source):
    return notes.extract_definitions(source.split("\n"))[1]


def apply(body, source, renderer=converter.render_blocks):
    return notes.apply_footnotes(wrap(body), definitions(source), renderer, structure)


class DefinitionTests(unittest.TestCase):
    def test_definition_extraction_preserves_input_and_original_line_positions(self):
        lines = ["Texto[^a].", "", "[^a]: Explicación.", "    Continuación.", "", "## Después"]
        original = lines[:]
        body, result = notes.extract_definitions(lines, list(range(11, 17)))
        self.assertEqual(lines, original)
        self.assertEqual(body, ["Texto[^a].", "", "", "", "", "## Después"])
        self.assertEqual(result["a"].lines, ["Explicación.", "Continuación."])
        self.assertEqual(result["a"].line_numbers, [13, 14])
        self.assertEqual(result["a"].source_line, 13)

    def test_multiple_paragraphs_list_and_code_have_their_continuation_indent_removed(self):
        body, result = notes.extract_definitions([
            "[^rich]: Primer párrafo.", "", "    Segundo párrafo.", "", "    - Primero", "    - Segundo",
            "", "    ```python", "    print('conservado')", "    ```", "", "Cuerpo.",
        ])
        self.assertEqual(result["rich"].lines, [
            "Primer párrafo.", "", "Segundo párrafo.", "", "- Primero", "- Segundo", "",
            "```python", "print('conservado')", "```",
        ])
        self.assertEqual(body[-1], "Cuerpo.")
        rendered = converter.render_blocks(result["rich"].lines)
        self.assertEqual(rendered.count("<p>"), 2)
        self.assertIn("<ul>", rendered)
        self.assertIn('<code class="language-python">', rendered)

    def test_tab_continuations_and_blank_initial_definition_are_valid(self):
        result = definitions("[^x]:\n\tPrimer párrafo.\n\n\tSegundo párrafo.")
        self.assertEqual(result["x"].lines, ["", "Primer párrafo.", "", "Segundo párrafo."])

    def test_fenced_examples_with_both_markers_and_longer_closing_fences_are_literal(self):
        for fence, close in (("```markdown", "````"), ("~~~~", "~~~~")):
            with self.subTest(fence=fence):
                lines = [fence, "[^literal]: No es una nota.", close, "[^real]: Sí es una nota."]
                body, result = notes.extract_definitions(lines)
                self.assertEqual(set(result), {"real"})
                self.assertEqual(body[:3], lines[:3])

    def test_wrong_fence_closer_does_not_enable_definition_parsing(self):
        source = "````\n[^a]: Código.\n```\n[^b]: Sigue siendo código."
        self.assertEqual(definitions(source), {})

    def test_list_code_fences_preserve_definitions_and_real_notes_after_the_list(self):
        for marker in ("-", "+", "*", "1.", "9)", "12.", "- -", "- [ ]", "1. [x]"):
            for opening, closing in (("```markdown", "````"), ("~~~~text", "~~~~")):
                with self.subTest(marker=marker, opening=opening):
                    # Task markers are removed from the item, without changing
                    # the indentation required for its continuation lines.
                    indent = " " * (len(marker.split()[0]) + 1)
                    if marker == "- -":
                        indent = "    "
                    lines = [marker + " " + opening, indent + "[^literal]: Código.",
                             indent + closing, "", "[^real]: Nota real."]
                    body, result = notes.extract_definitions(lines)
                    self.assertEqual(set(result), {"real"})
                    self.assertEqual(body[:4], lines[:4])
                    self.assertEqual(result["real"].source_line, 5)

    def test_fences_in_nested_lists_and_paragraph_continuations_are_literal(self):
        cases = (
            ["- Exterior", "  1. Interior", "", "     ~~~markdown", "     [^literal]: Código.", "     ~~~"],
            ["1. Ejemplo", "", "   ```markdown", "   [^literal]: Código.", "   ```"],
        )
        for code_lines in cases:
            with self.subTest(lines=code_lines):
                lines = code_lines + ["", "[^real]: Nota real."]
                body, result = notes.extract_definitions(lines)
                self.assertEqual(set(result), {"real"})
                self.assertEqual(body[:len(code_lines)], code_lines)

    def test_unclosed_list_fence_does_not_hide_a_note_outside_its_item(self):
        for following in ([], ["- Otro elemento."], ["## Después"], ["| A | B |", "| --- | --- |"]):
            with self.subTest(following=following):
                lines = ["- ```markdown", "  [^literal]: Código."] + following + ["", "[^real]: Nota real."]
                body, result = notes.extract_definitions(lines)
                self.assertEqual(set(result), {"real"})
                self.assertEqual(body[:2], lines[:2])

    def test_inline_code_in_a_list_protects_only_its_own_item(self):
        lines = ["- Código `abierto", "  [^literal]: Dentro del código.", "  cerrado`.",
                 "- Otro elemento.", "  [^real]: Nota real."]
        body, result = notes.extract_definitions(lines)
        self.assertEqual(set(result), {"real"})
        self.assertEqual(body[:4], lines[:4])

    def test_inline_code_in_a_list_cannot_span_a_rendered_block_boundary(self):
        for block in (
            ["## Sección"], ["> Cita"], ["---"], ["<!-- pagebreak -->"],
            ["$$x$$"], ["| A | B |", "| --- | --- |"], ["- Otro elemento"],
        ):
            with self.subTest(block=block):
                lines = ["- Código `abierto"] + ["  " + line for line in block] + [
                    "  [^real]: Nota real.", "  cerrado`.",
                ]
                body, result = notes.extract_definitions(lines)
                self.assertEqual(set(result), {"real"})
                self.assertEqual(result["real"].source_line, len(block) + 2)
                self.assertEqual(body[0], lines[0])

    def test_open_backtick_in_a_heading_or_quote_cannot_hide_a_following_note(self):
        for opening in ("## Código `abierto", "> Código `abierto"):
            with self.subTest(opening=opening):
                lines = ["- " + opening, "  [^real]: Nota real.", "  cerrado`."]
                body, result = notes.extract_definitions(lines)
                self.assertEqual(set(result), {"real"})
                self.assertEqual(result["real"].source_line, 2)
                self.assertEqual(body[0], lines[0])

    def test_list_marker_inside_an_outer_code_fence_is_not_a_container(self):
        lines = ["````markdown", "- ```", "  [^literal]: Código.", "  ```", "````", "[^real]: Nota."]
        body, result = notes.extract_definitions(lines)
        self.assertEqual(set(result), {"real"})
        self.assertEqual(body[:5], lines[:5])

    def test_multiline_inline_code_protects_definition_syntax(self):
        lines = ["Código `abierto", "[^literal]: Código en línea.", "cerrado`.", "", "[^real]: Definición."]
        body, result = notes.extract_definitions(lines)
        self.assertEqual(set(result), {"real"})
        self.assertEqual(body[1], lines[1])

    def test_unclosed_inline_backtick_and_escaped_markers_do_not_hide_later_definitions(self):
        result = definitions("Texto `sin cerrar.\n\n\\[^escaped]: Texto.\n[^real]: Nota.")
        self.assertEqual(set(result), {"real"})

    def test_inline_code_cannot_span_a_blank_paragraph_boundary(self):
        result = definitions("Texto `sin cerrar.\n\n[^real]: Nota.\n\nCierre ` en otro párrafo.")
        self.assertEqual(set(result), {"real"})

    def test_quoted_definition_and_four_space_initial_definition_are_not_top_level_definitions(self):
        self.assertEqual(definitions("> [^quoted]: Texto.\n    [^indented]: Texto."), {})

    def test_duplicate_definition_diagnostic_reports_both_source_lines(self):
        with self.assertRaisesRegex(notes.FootnoteError, r"duplicada en línea 13.*línea 11"):
            notes.extract_definitions(["[^a]: Una.", "", "[^a]: Otra."], [11, 12, 13])

    def test_empty_definition_is_an_explicit_error(self):
        with self.assertRaisesRegex(notes.FootnoteError, r"vacía en línea 1"):
            definitions("[^a]:\n\nTexto.")

    def test_unicode_case_sensitive_labels_are_supported_without_spelling_changes(self):
        result = definitions("[^año]: Primera.\n[^Año]: Segunda.\n[^spec:v1.2]: Tercera.")
        self.assertEqual(list(result), ["año", "Año", "spec:v1.2"])

    def test_source_number_length_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "número de origen"):
            notes.extract_definitions(["Texto"], [])


class LinkedNoteTests(unittest.TestCase):
    def parse(self, document):
        parser = structure._DocumentParser()
        parser.feed(document)
        parser.close()
        return list(structure._walk(parser.root))

    def test_numbering_uses_first_reference_order_and_repeated_references_share_one_note(self):
        result = apply("<p>" + marker("b") + marker("a") + marker("b") + "</p>",
                       "[^a]: Nota A.\n[^b]: Nota B.")
        nodes = self.parse(result)
        refs = [node for node in nodes if node.get("role") == "doc-noteref"]
        items = [node for node in nodes if node.get("data-footnote-number")]
        self.assertEqual([structure._label(node) for node in refs], ["1", "2", "1"])
        self.assertEqual(refs[0].get("href"), refs[2].get("href"))
        self.assertEqual(len(items), 2)
        self.assertIn("Nota B.", structure._label(items[0]))
        self.assertIn("Nota A.", structure._label(items[1]))
        self.assertEqual(result.count("Nota B."), 1)
        self.assertEqual(result.count('role="doc-backlink"'), 3)

    def test_every_forward_and_back_link_resolves_to_a_unique_html_target(self):
        result = apply("<p>" + marker("año") + marker("año") + marker("B") + "</p>",
                       "[^año]: Nota año.\n[^B]: Nota B.")
        nodes = self.parse(result)
        ids = [node.get("id") for node in nodes if node.get("id")]
        self.assertEqual(len(ids), len(set(ids)))
        refs = [node for node in nodes if node.get("role") in {"doc-noteref", "doc-backlink"}]
        self.assertEqual(len(refs), 6)
        for node in refs:
            self.assertIn(node.get("href")[1:], ids)

    def test_existing_document_and_note_content_ids_do_not_collide_with_generated_ids(self):
        result = apply('<p id="document-notes">Cuerpo.</p><p id="document-note-1">' + marker("a") + "</p>",
                       "[^a]: # document-note-ref-1-1")
        nodes = self.parse(result)
        ids = [node.get("id") for node in nodes if node.get("id")]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("document-notes-1", ids)
        self.assertIn("document-note-1-1", ids)
        self.assertIn("document-note-ref-1-1-1", ids)

    def test_rich_definition_retains_source_locations_links_lists_and_code(self):
        result = apply("<p>" + marker("rich") + "</p>",
                       "[^rich]: **Detalle** y [enlace](https://example.com).\n\n    - Uno\n    - Dos\n\n    ```text\n    [^literal]\n    ```")
        self.assertIn("<strong>Detalle</strong>", result)
        self.assertIn('href="https://example.com"', result)
        self.assertIn('<ul data-source-line="3">', result)
        self.assertIn('<pre data-source-line="6">', result)
        self.assertIn("[^literal]", result)
        self.assertIn('data-source-line="1" data-footnote-number="1"', result)

    def test_notes_are_explicitly_document_end_content_after_the_original_body(self):
        result = apply("<h1>Título</h1><p>" + marker("a") + "</p><p>Último párrafo.</p>", "[^a]: Nota.")
        self.assertLess(result.index("Último párrafo."), result.index('role="doc-endnotes"'))
        self.assertIn('data-document-role="section">Notas</h2>', result)
        self.assertNotIn("float: footnote", result)

    def test_footnote_content_headings_are_marked_separately_from_document_sections(self):
        result = apply("<p>" + marker("a") + "</p>", "[^a]: ### Encabezado interno")
        self.assertIn('data-document-role="note-content">Encabezado interno</h3>', result)

    def test_missing_definition_fails_with_the_reference_source_line(self):
        with self.assertRaisesRegex(notes.FootnoteError, r"\[\^ausente\].*línea 17.*no tiene definición"):
            apply("<p>" + marker("ausente", 17) + "</p>", "")

    def test_unused_definition_is_an_explicit_error_instead_of_silently_dropping_content(self):
        with self.assertRaisesRegex(notes.FootnoteError, r"sin referencia.*\[\^unused\].*línea 3"):
            apply("<p>Texto.</p>", "\n\n[^unused]: Contenido.")

    def test_nested_references_in_definition_are_rejected(self):
        def render_nested(lines, *, line_numbers):
            return "<p>" + marker("nested", line_numbers[0]) + "</p>"

        with self.assertRaisesRegex(notes.FootnoteError, r"línea 1.*dentro de otra nota"):
            apply("<p>" + marker("a") + "</p>", "[^a]: Contenido.", render_nested)

    def test_unchanged_documents_and_second_application_are_identity_operations(self):
        document = wrap("<h1>Título</h1><p>Cuerpo.</p>")
        self.assertEqual(notes.apply_footnotes(document, {}, converter.render_blocks, structure), document)
        generated = apply("<p>" + marker("a") + "</p>", "[^a]: Nota.")
        self.assertEqual(notes.apply_footnotes(generated, definitions("[^a]: Nota."), converter.render_blocks, structure), generated)


class ConverterNoteTests(unittest.TestCase):
    def build(self, text):
        with tempfile.TemporaryDirectory(prefix="mdpdf-footnotes-source-") as directory:
            source = Path(directory) / "document.md"
            source.write_text(text, encoding="utf-8")
            result = converter.build_document(source, None, "A4", False, True)
            self.assertEqual(source.read_text(encoding="utf-8"), text)
            return result

    def test_real_markdown_converts_notes_after_metadata_without_touching_source(self):
        result, metadata, presentation = self.build(
            '---\ndocumento:\n  titulo: "Informe"\n---\n\n## Contenido\n\nTexto[^año].\n\n[^año]: Detalle.\n'
        )
        self.assertEqual(metadata["titulo"], "Informe")
        self.assertEqual(presentation["footnotes"], 1)
        self.assertIn('role="doc-noteref"', result)
        self.assertIn("Detalle.", result)
        self.assertNotIn("[^año]", result)
        self.assertIn('data-source-line="10" data-footnote-number="1"', result)

    def test_literal_code_escaped_syntax_and_link_labels_do_not_create_notes(self):
        result, _, presentation = self.build(
            '# Documento\n\nCódigo `[^literal]` y \\[^escapado].\n\n'
            '[Etiqueta [^enlace]](https://example.com).\n\n'
            '```markdown\n[^definición]: Ejemplo.\nTexto[^código].\n```\n'
        )
        self.assertEqual(presentation["footnotes"], 0)
        self.assertIn("[^literal]", result)
        self.assertIn("[^escapado]", result)
        self.assertIn("[^enlace]", result)
        self.assertIn("[^código]", result)
        self.assertNotIn('role="doc-noteref"', result)

    def test_note_references_inside_emphasis_are_active(self):
        result, _, presentation = self.build('# Documento\n\n**Texto[^a]** y *otro[^a]*.\n\n[^a]: Detalle.\n')
        self.assertEqual(presentation["footnotes"], 1)
        self.assertEqual(result.count('role="doc-noteref"'), 2)
        self.assertIn("<strong>Texto<sup", result)

    def test_definition_examples_in_list_code_remain_visible_without_creating_notes(self):
        for code in (
            '- ```markdown\n  [^literal]: Código conservado.\n  ```\n',
            '1. ~~~markdown\n   [^literal]: Código conservado.\n   ~~~\n',
            '- [x] ```markdown\n  [^literal]: Código conservado.\n  ```\n',
            '- Exterior\n  - ```markdown\n    [^literal]: Código conservado.\n    ```\n',
        ):
            with self.subTest(code=code):
                document, _, presentation = self.build('# Documento\n\n' + code)
                self.assertIn('<code class="language-markdown">[^literal]: Código conservado.</code>', document)
                self.assertEqual(presentation["footnotes"], 0)
                self.assertNotIn('role="doc-endnotes"', document)

    def test_a_literal_definition_in_list_code_cannot_satisfy_an_external_reference(self):
        with self.assertRaisesRegex(converter.ConversionError, r"\[\^literal\].*línea 3.*no tiene definición"):
            self.build('# Documento\n\nTexto[^literal].\n\n- ```markdown\n  [^literal]: Solo código.\n  ```\n')

    def test_literal_and_real_definitions_with_the_same_identifier_are_distinct(self):
        document, _, presentation = self.build(
            '# Documento\n\nTexto[^a].\n\n- ```markdown\n  [^a]: Solo código.\n  ```\n\n[^a]: Nota real.\n'
        )
        self.assertIn('<code class="language-markdown">[^a]: Solo código.</code>', document)
        self.assertEqual(presentation["footnotes"], 1)
        self.assertEqual(document.count('role="doc-noteref"'), 1)
        self.assertEqual(document.count("Nota real."), 1)

    def test_list_heading_boundaries_keep_real_notes_with_unmatched_backticks(self):
        for content in (
            '- Código `abierto\n  ## Sección\n  [^real]: Nota real.\n  cerrado`.\n',
            '- ## Código `abierto\n  [^real]: Nota real.\n  cerrado`.\n',
        ):
            with self.subTest(content=content):
                document, _, presentation = self.build('# Documento\n\nTexto[^real].\n\n' + content)
                self.assertEqual(presentation["footnotes"], 1)
                self.assertEqual(document.count('role="doc-noteref"'), 1)
                self.assertEqual(document.count("Nota real."), 1)
                self.assertIn("`abierto", document)
                self.assertIn("cerrado`.", document)

    def test_markdown_reference_to_another_note_inside_a_definition_fails_with_source_line(self):
        with self.assertRaisesRegex(converter.ConversionError, r"document\.md.*línea 5.*dentro de otra nota"):
            self.build('# Documento\n\nTexto[^a].\n\n[^a]: Detalle[^a].\n')

    def test_notes_and_inner_headings_do_not_replace_title_or_pollute_section_registry(self):
        document, _, _ = self.build('# Documento\n\n## Cuerpo\n\nTexto[^a].\n\n[^a]: ### Detalle interno\n')
        _, registry = structure.prepare_document(document)
        self.assertEqual([item["title"] for item in registry["entries"]], ["Cuerpo", "Notas"])
        self.assertNotIn("Detalle interno", [item["title"] for item in registry["headings"]])

    def test_note_content_keeps_table_cross_references_and_external_links(self):
        document, _, _ = self.build(
            '# Documento\n\n## Datos\n\nTabla: Estados {#tbl:estados}\n\n| Campo | Valor |\n| --- | --- |\n| A | B |\n\n'
            'Texto[^a].\n\n[^a]: Consulte [@tbl:estados] y [documentación](https://example.com).\n'
        )
        result, registry = structure.prepare_document(document)
        self.assertIn('href="#tbl:estados"', result)
        self.assertIn('href="https://example.com"', result)
        self.assertNotIn("[@tbl:estados]", result)
        self.assertEqual(len(registry["tables"]), 1)


if __name__ == "__main__":
    unittest.main()
