"""Cover options through the public converter and local runtime."""

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "convert_markdown_to_pdf.py"
SPEC = importlib.util.spec_from_file_location("mdpdf_cover_conversion", SCRIPT)
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)


class CoverConversionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mdpdf-cover-options-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "document.md"
        self.logo = self.root / "local.svg"
        self.logo.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10"/></svg>')

    def build(self, markdown, *options):
        self.source.write_text(markdown, encoding="utf-8")
        args = converter.parse_args([str(self.source), *options])
        result = converter.build_document(
            self.source, None, args.paper, args.landscape, args.footer,
            args.metadata_overrides, cover=args.cover, logo=args.logo,
            logo_explicit=args.logo_explicit, no_branding=args.no_branding,
        )
        self.assertEqual(self.source.read_text(encoding="utf-8"), markdown)
        return result

    def test_cli_cover_switch_has_priority_over_yaml_in_both_directions(self):
        base = '---\ndocumento:\n  titulo: "Documento"\npdf:\n  portada: true\n---\n## 1. Alcance\n'
        with_cover, _, enabled = self.build(base)
        without_cover, _, disabled = self.build(base, "--no-cover")
        self.assertTrue(enabled["cover"])
        self.assertFalse(disabled["cover"])
        self.assertIn('class="document-cover"', with_cover)
        self.assertNotIn('class="document-cover"', without_cover)
        self.assertIn("Documento</h1>", without_cover)
        forced, _, options = self.build(base.replace("true", "false"), "--cover")
        self.assertTrue(options["cover"])
        self.assertIn('class="document-cover"', forced)

    def test_yaml_logo_is_relative_to_markdown_and_cli_has_priority(self):
        source = '---\ndocumento:\n  titulo: "Documento"\npdf:\n  portada: true\n  logo: "local.svg"\n---\nTexto.'
        document, _, options = self.build(source)
        self.assertEqual(options["logo"], self.logo.resolve())
        self.assertIn("data:image/svg+xml;base64,", document)
        _, _, overridden = self.build(source, "--logo", str(converter.DEFAULT_LOGO))
        self.assertEqual(overridden["logo"], converter.DEFAULT_LOGO.resolve())
        _, _, omitted = self.build(source, "--no-logo")
        self.assertIsNone(omitted["logo"])

    def test_yaml_null_omits_default_logo_even_without_cover(self):
        _, _, options = self.build('---\npdf:\n  logo: null\n---\n# Documento\n')
        self.assertIsNone(options["logo"])
        self.assertFalse(options["cover"])

    def test_no_branding_preserves_cover_and_metadata_but_omits_logo(self):
        source = '---\ndocumento:\n  titulo: "Documento"\n  clasificacion: "INTERNO"\npdf:\n  portada: true\n  logo: "ausente.png"\n---\nTexto.'
        document, metadata, options = self.build(source, "--no-branding")
        self.assertTrue(options["cover"])
        self.assertIsNone(options["logo"])
        self.assertEqual(metadata["clasificacion"], "INTERNO")
        self.assertIn("INTERNO", document)
        self.assertNotIn("data:image", document)

    def test_cover_can_use_existing_metadata_and_keeps_title_link(self):
        source = '# Documento existente\n\n| Dato | Valor |\n| --- | --- |\n| Versión | 0.1 |\n| Estado | Borrador |\n\n## 1. Alcance\n\n[Inicio](#documento-existente).'
        document, metadata, options = self.build(source, "--cover")
        self.assertTrue(options["cover"])
        self.assertEqual(metadata["version"], "0.1")
        self.assertEqual(document.count('<table'), 1)
        self.assertIn('id="documento-existente"', document)
        self.assertIn('href="#documento-existente"', document)

    def test_browser_engine_rejects_cover_with_plain_flags(self):
        self.source.write_text('# Documento\n', encoding="utf-8")
        args = converter.parse_args([str(self.source), "--cover", "--engine", "browser", "--no-branding", "--no-toc", "--no-bookmarks"])
        with self.assertRaisesRegex(converter.ConversionError, "--no-cover"):
            converter.convert(args)

    def test_yaml_cover_reuses_local_playwright_when_other_features_are_off(self):
        self.source.write_text('---\npdf:\n  portada: true\n---\n# Documento\n', encoding="utf-8")
        local_python = self.root / '.venv' / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
        local_python.parent.mkdir(parents=True)
        local_python.write_text('placeholder')
        converter.load_support_module('document_metadata')
        args = converter.parse_args([str(self.source), '--no-branding', '--no-toc', '--no-bookmarks'])
        with patch.object(converter, 'SKILL_DIR', self.root), \
             patch.object(converter, 'yaml_available', return_value=True), \
             patch.object(converter, 'playwright_available', return_value=False), \
             patch.dict(os.environ, {}, clear=True), patch.object(converter.os, 'execve') as execute:
            converter.use_local_environment(args, [str(self.source)])
        self.assertEqual(execute.call_args.args[0], str(local_python))


if __name__ == '__main__':
    unittest.main()
