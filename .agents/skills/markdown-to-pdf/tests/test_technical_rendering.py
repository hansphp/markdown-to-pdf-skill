"""Offline asset and placeholder contract checks for technical rendering."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock


SKILL = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("mdpdf_technical_rendering", SKILL / "scripts" / "technical_rendering.py")
technical = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(technical)


class TechnicalAssetsTests(unittest.TestCase):
    def test_only_real_placeholders_require_engines(self):
        self.assertFalse(technical.has_technical_content('<pre>&lt;img data-document-mermaid="flowchart TD"&gt;</pre>'))
        self.assertFalse(technical.has_technical_content('<p>data-document-math="inline"</p>'))
        self.assertEqual(technical.technical_requirements('<img data-document-mermaid="flowchart TD"/>'), {"mermaid": True, "math": False})
        self.assertEqual(technical.technical_requirements('<span data-document-math="inline">x</span><div data-document-math="display">y</div>'), {"mermaid": False, "math": True})

    def test_all_vendored_files_match_pinned_integrity(self):
        assets = technical._verified_assets(SKILL, ["mermaid", "katex"])
        self.assertIn("mermaid.min.js", assets["mermaid"])
        self.assertIn("katex.min.js", assets["katex"])
        self.assertIn("LICENSE", assets["mermaid"])
        self.assertIn("LICENSE", assets["katex"])
        manifest = json.loads((SKILL / "assets" / "vendor" / "manifest.json").read_text())
        self.assertEqual(manifest["packages"]["mermaid"]["version"], "12.0.0")
        self.assertEqual(manifest["packages"]["katex"]["version"], "0.18.7")

    def test_math_css_embeds_every_font_with_no_external_paths(self):
        assets = technical._verified_assets(SKILL, ["katex"])
        css = technical._embedded_math_css(assets["katex"])
        self.assertIn('url("data:font/woff2;base64,', css)
        self.assertNotIn("url(fonts/", css)
        self.assertNotIn('url("fonts/', css)
        self.assertNotIn("https://", css)

    def test_missing_and_modified_assets_have_actionable_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(technical.TechnicalRenderingError, "Restaure assets/vendor"):
                technical._verified_assets(root, ["mermaid"])
            vendor = root / "assets" / "vendor"
            (vendor / "mermaid").mkdir(parents=True)
            manifest = {"packages": {"mermaid": {"files": {"mermaid.min.js": "wrong-hash"}}}}
            (vendor / "manifest.json").write_text(json.dumps(manifest))
            (vendor / "mermaid" / "mermaid.min.js").write_text("corrupt")
            with self.assertRaisesRegex(technical.TechnicalRenderingError, "integridad SHA-256 incorrecta"):
                technical._verified_assets(root, ["mermaid"])

    def test_plain_document_works_without_vendor_directory(self):
        page = Mock()
        page.evaluate.return_value = {"mermaid": False, "math": False}
        self.assertEqual(technical.render_technical(page, Path("/missing-skill")), {"mermaid": 0, "math": 0})
        page.add_script_tag.assert_not_called()
        page.add_style_tag.assert_not_called()

    def test_empty_label_mapping_does_not_touch_the_browser(self):
        page = Mock()
        self.assertEqual(technical.read_text_labels(page, {}), {})
        page.evaluate.assert_not_called()

    def test_label_read_failures_have_document_context(self):
        page = Mock()
        page.evaluate.side_effect = RuntimeError('El navegador se cerró.')
        with self.assertRaisesRegex(technical.TechnicalRenderingError, 'etiquetas textuales.*navegador'):
            technical.read_text_labels(page, {'titulo': 'document-title'})
        with self.assertRaisesRegex(technical.TechnicalRenderingError, 'títulos de los marcadores.*navegador'):
            technical.read_heading_labels(page)


if __name__ == "__main__":
    unittest.main()
