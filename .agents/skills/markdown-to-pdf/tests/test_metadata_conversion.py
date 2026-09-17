"""Metadata through the public converter, including CLI and local runtime."""

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "convert_markdown_to_pdf.py"
SPEC = importlib.util.spec_from_file_location("mdpdf_metadata_conversion", SCRIPT)
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)


def inherited_headings_markdown(with_cover):
    return ('---\ndocumento: {}\npdf:\n  portada: ' + str(with_cover).lower() + '\n---\n' + r'''
| Dato | Valor |
| --- | --- |
| Título | **Informe** $\frac{a}{b}$[^titulo] |
| Subtítulo | *Sistema* $x^2$[^subtitulo] |
| Estado | Borrador |

## 1. Cuerpo

Texto del cuerpo.

[^titulo]: Nota del título.
[^subtitulo]: Nota del subtítulo.
''')


class MetadataConversionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mdpdf-metadata-convert-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "document.md"

    def build(self, source, *options):
        self.source.write_text(source, encoding="utf-8")
        args = converter.parse_args([str(self.source), *options])
        result = converter.build_document(
            self.source, None, args.paper, args.landscape, args.footer,
            args.metadata_overrides, auto_margins=True,
            logo=args.logo, logo_explicit=args.logo_explicit, no_branding=args.no_branding,
        )
        self.assertEqual(self.source.read_text(encoding="utf-8"), source)
        return result[:2]

    def test_explicit_cli_metadata_overrides_yaml_and_empty_is_not_defaulted(self):
        source = '---\ndocumento:\n  titulo: "Título YAML"\n  version: "0.10"\n  clasificacion: "INTERNO"\n---\n## 1. Contenido\n\nTexto.\n'
        result, metadata = self.build(source, "--title=Título CLI", "--document-version", "0.20", "--classification", "")
        self.assertEqual(metadata["titulo"], "Título CLI")
        self.assertEqual(metadata["version"], "0.20")
        self.assertEqual(metadata["clasificacion"], "")
        self.assertEqual(metadata["subtitulo"], "")
        self.assertIn("Título CLI", result)
        self.assertNotIn("Título YAML", result)
        self.assertNotIn("0.10", result)
        self.assertNotIn("INTERNO", result)
        structure = converter.load_support_module("document_structure")
        _, registry = structure.prepare_document(result)
        self.assertEqual([item["title"] for item in registry["entries"]], ["1. Contenido"])

    def test_classification_alone_keeps_legacy_document_layout(self):
        source = "# Título existente\n\n## Primera sección\n\nTexto.\n"
        original, default = self.build(source)
        overridden, metadata = self.build(source, "--classification", "INTERNO")
        self.assertEqual(original, overridden)
        self.assertEqual(metadata["subtitulo"], "Primera sección")
        self.assertEqual(metadata["titulo"], default["titulo"])
        self.assertEqual(metadata["clasificacion"], "INTERNO")
        self.assertNotIn("<table", overridden)

    def test_new_cli_field_enables_metadata_without_yaml(self):
        result, metadata = self.build("# Documento\n\n## 1. Alcance\n\nTexto.", "--document-code", "DOC-001")
        self.assertEqual(metadata["codigo"], "DOC-001")
        self.assertEqual(metadata["subtitulo"], "")
        self.assertIn("DOC-001", result)
        self.assertEqual(result.count("<table"), 1)

    def test_body_rule_and_colon_paragraph_after_yaml_are_preserved(self):
        result, _ = self.build('---\ndocumento:\n  titulo: "Documento"\n---\n---\nNota: Texto que debe conservarse.\n---\n## 1. Contenido\n')
        self.assertIn("Nota: Texto que debe conservarse.", result)
        parser = converter.load_support_module("document_structure")._DocumentParser()
        parser.feed(result)
        self.assertEqual(sum(node.tag == "hr" for node in converter.load_support_module("document_structure")._walk(parser.root)), 2)

    def test_table_headings_keep_formulas_and_notes_with_and_without_cover(self):
        structure = converter.load_support_module("document_structure")
        technical = converter.load_support_module("technical_rendering")
        for with_cover in (False, True):
            with self.subTest(cover=with_cover):
                result, _ = self.build(inherited_headings_markdown(with_cover))
                parser = structure._DocumentParser()
                parser.feed(result)
                nodes = list(structure._walk(parser.root))
                for role, emphasis in (("title", "strong"), ("subtitle", "em")):
                    heading = next(node for node in nodes if node.get("data-document-role") == role)
                    children = list(structure._walk(heading))
                    self.assertTrue(any(node.tag == emphasis for node in children))
                    self.assertEqual(sum(node.get("data-document-math") == "inline" for node in children), 1)
                    self.assertEqual(sum(node.get("role") == "doc-noteref" for node in children), 1)
                    self.assertEqual(heading.parent.get("class") == "document-cover-content", with_cover)
                self.assertTrue(technical.technical_requirements(result)["math"])
                self.assertEqual(sum(node.get("data-footnote-number") is not None for node in nodes), 2)
                self.assertEqual(sum(node.get("role") == "doc-backlink" for node in nodes), 2)
                self.assertNotIn("<td>Título</td>", result)
                self.assertNotIn("<td>Subtítulo</td>", result)

    def test_invalid_yaml_reports_source_and_does_not_start_renderer(self):
        self.source.write_text('---\ndocumento:\n  version: 0.10\n---\nTexto.', encoding="utf-8")
        with patch.object(converter, "render_with_playwright") as render:
            with self.assertRaisesRegex(converter.ConversionError, r"document.md:.*línea 3.*comillas"):
                converter.convert(converter.parse_args([str(self.source)]))
        render.assert_not_called()
        self.assertFalse(self.source.with_suffix(".pdf").exists())

    def test_generated_metadata_reads_resolved_references_and_numbered_notes(self):
        document, metadata = self.build('''# Informe [@tbl:datos][^titulo]

## Consulta [@tbl:datos]

Tabla: Datos {#tbl:datos}

| Campo | Valor |
| --- | --- |
| A | B |

[^titulo]: Fuente del título.
''')
        structure = converter.load_support_module("document_structure")
        document, _ = structure.prepare_document(document)
        result, targets = converter.load_support_module("document_metadata").refresh_generated_metadata(
            document, metadata, False, structure)
        self.assertEqual(metadata["titulo"], "Informe Tabla 1[1]")
        self.assertEqual(metadata["subtitulo"], "Consulta Tabla 1")
        self.assertIn('<title>Informe Tabla 1[1]</title>', result)
        self.assertEqual(set(targets), {"titulo", "subtitulo"})
        self.assertNotIn("document-toc", targets.values())

    def test_generated_metadata_keeps_explicit_omissions_and_literal_values(self):
        document, metadata = self.build('''---
documento:
  titulo: "Manual [@tbl:literal] <texto>"
  subtitulo: ""
---
## Sección que no es subtítulo

Texto.
''')
        structure = converter.load_support_module("document_structure")
        document, _ = structure.prepare_document(document)
        result, targets = converter.load_support_module("document_metadata").refresh_generated_metadata(
            document, metadata, True, structure)
        self.assertEqual(metadata["titulo"], "Manual [@tbl:literal] <texto>")
        self.assertEqual(metadata["subtitulo"], "")
        self.assertEqual(set(targets), {"titulo"})
        self.assertIn('<title>Manual [@tbl:literal] &lt;texto&gt;</title>', result)

    def test_generated_metadata_keeps_filename_fallback_without_a_title(self):
        document, metadata = self.build('## 1. Alcance\n\nTexto.')
        structure = converter.load_support_module("document_structure")
        document, _ = structure.prepare_document(document)
        _, targets = converter.load_support_module("document_metadata").refresh_generated_metadata(
            document, metadata, False, structure)
        self.assertEqual(metadata["titulo"], "document")
        self.assertEqual(metadata["subtitulo"], "1. Alcance")
        self.assertNotIn("titulo", targets)

    def test_no_branding_preserves_body_classification_and_disables_page_furniture(self):
        source = '---\ndocumento:\n  titulo: "Documento"\n  clasificacion: "INTERNO"\n---\n## 1. Alcance\n\nTexto.'
        self.source.write_text(source, encoding="utf-8")
        args = converter.parse_args([str(self.source), "--no-branding", "--no-toc", "--no-bookmarks"])
        captured = {}

        def render(html_path, pdf_path, footer, title, subtitle, **kwargs):
            captured.update(html=html_path.read_text(encoding="utf-8"), footer=footer, **kwargs)
            pdf_path.write_bytes(b"%PDF-1.4\n" + b"x" * 120 + b"\n%%EOF\n")
            return "playwright/fake"

        validation = converter.load_support_module("document_validation")
        with patch.object(validation, "inspect_pdf", return_value=[]), \
             patch.object(converter, "playwright_available", return_value=True), \
             patch.object(converter, "render_with_playwright", side_effect=render):
            converter.convert(args)
        self.assertIn("INTERNO", captured["html"])
        self.assertIn("margin: 18mm 16mm", captured["html"])
        self.assertEqual(captured["classification"], "")
        self.assertIsNone(captured["logo_path"])
        self.assertFalse(captured["footer"])
        self.assertEqual(self.source.read_text(encoding="utf-8"), source)

    def test_yaml_only_browser_reuses_local_environment_when_yaml_is_missing(self):
        self.source.write_text('---\ndocumento:\n  titulo: "Documento"\n---\nTexto.', encoding="utf-8")
        local_python = self.root / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        local_python.parent.mkdir(parents=True)
        local_python.write_text("placeholder", encoding="utf-8")
        args = converter.parse_args([str(self.source), "--engine", "browser", "--no-branding", "--no-toc", "--no-bookmarks"])
        # Load before replacing SKILL_DIR with the isolated environment fixture.
        converter.load_support_module("document_metadata")
        with patch.object(converter, "SKILL_DIR", self.root), \
             patch.object(converter, "yaml_available", return_value=False), \
             patch.dict(os.environ, {}, clear=True), patch.object(converter.os, "execve") as execute:
            converter.use_local_environment(args, [str(self.source)])
        self.assertEqual(execute.call_args.args[0], str(local_python))


if __name__ == "__main__":
    unittest.main()
