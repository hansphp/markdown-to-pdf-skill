"""Real PDFs keep generated labels, rich indices and native destinations aligned."""

import importlib.util
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SKILL = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "mdpdf_generated_labels_integration", SKILL / "scripts/convert_markdown_to_pdf.py"
)
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)


def normalized(value):
    return re.sub(r"\s+", " ", value or "").strip()


def label_key(value):
    # A superscript or inline span can contribute whitespace at its boundary.
    return re.sub(r"\s+", "", value or "")


@unittest.skipUnless(os.environ.get("MDPDF_BROWSER_TESTS") == "1", "Requiere MDPDF_BROWSER_TESTS=1")
class GeneratedLabelsIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mdpdf-generated-labels-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "document.md"
        shutil.copyfile(SKILL / "assets/ejemplo/recursos/flujo.svg", self.root / "flujo.svg")
        self.structure = converter.load_support_module("document_structure")
        self.navigation = converter.load_support_module("pdf_navigation")

    def render(self, markdown, *flags):
        from pypdf import PdfReader

        self.source.write_text(markdown, encoding="utf-8")
        args = converter.parse_args([str(self.source), "--strict", "--no-logo", *flags])
        captured = {}
        original = converter.render_with_playwright

        def capture_document(html_path, *positional, **keywords):
            captured["html"] = html_path.read_text(encoding="utf-8")
            return original(html_path, *positional, **keywords)

        with patch.object(converter, "render_with_playwright", side_effect=capture_document):
            output, engine = converter.convert(args)
        self.assertTrue(engine.startswith("playwright/"))
        self.assertEqual(args.validation_diagnostics, [])
        self.assertEqual(self.source.read_text(encoding="utf-8"), markdown)
        parser = self.structure._DocumentParser()
        parser.feed(captured["html"])
        parser.close()
        nodes = list(self.structure._walk(parser.root))
        with PdfReader(output) as reader:
            texts = [normalized(page.extract_text()) for page in reader.pages]
            pdf_title = reader.metadata.title
        return output, args, nodes, texts, pdf_title

    def assert_readable_title(self, args, texts, pdf_title, expected):
        self.assertEqual(label_key(args.resolved_metadata["titulo"]), label_key(expected))
        self.assertEqual(label_key(pdf_title), label_key(expected))
        # The footer is printed as plain text, including bracketed note numbers.
        self.assertIn(label_key(expected), label_key(texts[-1]))
        for token in ("[@", "[^", r"\frac", r"\(", r"\left", r"\right"):
            self.assertNotIn(token, " ".join(texts))
            self.assertNotIn(token, pdf_title)

    def test_forward_references_reach_inferred_captions_footer_and_repeated_bookmarks(self):
        markdown = '''# Informe de [@tbl:otra][^titulo]

## Detalle de [@tbl:otra]

| A | B |
| --- | --- |
| Uno | Dos |

Tabla: Otra {#tbl:otra}

| A | B |
| --- | --- |
| Tres | Cuatro |

<!-- pagebreak -->

## Detalle de [@tbl:otra]

Contenido de la sección repetida.

[^titulo]: Fuente del título.
'''
        output, args, nodes, texts, pdf_title = self.render(markdown, "--table-index")
        self.assertEqual(args.table_index_count, 2)
        self.assertEqual(args.footnote_count, 1)
        self.assert_readable_title(args, texts, pdf_title, "Informe de Tabla 2[1]")
        all_text = " ".join(texts)
        self.assertGreaterEqual(all_text.count("Tabla 1. Detalle de Tabla 2"), 2)
        self.assertIn("Tabla 2. Otra", all_text)
        bookmarks = self.navigation.read_bookmarks(output)
        repeated = [item for item in bookmarks if item["title"] == "Detalle de Tabla 2"]
        self.assertEqual(len(repeated), 2)
        self.assertLess(repeated[0]["page"], repeated[1]["page"])
        entries = [{"id": node.get("id")} for node in nodes
                   if node.tag == "h2" and self.structure._label(node) == "Detalle de Tabla 2"]
        self.assertEqual(len(entries), 2)
        pages = self.navigation.resolve_toc_pages(output, entries + [{"id": "table-1"}, {"id": "tbl:otra"}])
        self.assertEqual([pages[entry["id"]] for entry in entries], [item["page"] for item in repeated])
        index_text = " ".join(text for text in texts if "Índice de tablas" in text)
        self.assertRegex(index_text, r"Tabla 1\. Detalle de Tabla 2\s+" + str(pages["table-1"]) + r"\b")
        self.assertRegex(index_text, r"Tabla 2\. Otra\s+" + str(pages["tbl:otra"]) + r"\b")

    def test_cover_inherited_metadata_and_rich_indices_keep_math_notes_and_references(self):
        markdown = r'''---
documento: {}
pdf:
  portada: true
  indice_tablas: true
  indice_figuras: true
---
| Dato | Valor |
| --- | --- |
| Título | Informe $\frac{a}{b}$[^titulo] de [@tbl:base] |
| Subtítulo | Análisis $x^2$[^subtitulo] |
| Versión | 1.0 |

## Razón $\frac{a}{b}$[^seccion]

Tabla: Coeficiente $\frac{a}{b}$[^tabla] para [@fig:flujo] {#tbl:base}

| A | B |
| --- | --- |
| Uno | Dos |

Figura: Potencia $x^2$[^figura] según [@tbl:base] {#fig:flujo}

![Flujo](flujo.svg)

[^titulo]: Fuente del título.
[^subtitulo]: Fuente del subtítulo.
[^seccion]: Fuente de la sección.
[^tabla]: Fuente de la tabla.
[^figura]: Fuente de la figura.
'''
        output, args, nodes, texts, pdf_title = self.render(markdown)
        self.assertTrue(args.cover)
        self.assertEqual(args.table_index_count, 2)
        self.assertEqual(args.figure_index_count, 1)
        self.assertEqual(args.footnote_count, 5)
        self.assert_readable_title(args, texts, pdf_title, "Informe (a)/(b)[1] de Tabla 2")
        self.assertEqual(label_key(args.resolved_metadata["subtitulo"]), label_key("Análisis x^(2)[2]"))
        self.assertNotIn("Página 1 de", texts[0])
        navs = [node for node in nodes if node.tag == "nav"]
        self.assertEqual(len(navs), 3)
        for nav in navs:
            descendants = list(self.structure._walk(nav))
            self.assertTrue(any(node.get("data-document-math") == "inline" for node in descendants))
            self.assertFalse(any(node.get("role") == "doc-noteref" for node in descendants))
            for link in (node for node in descendants if node.tag == "a"):
                self.assertFalse(any(child.tag == "a" for child in self.structure._walk(link) if child is not link))
        self.assertEqual(sum(node.get("role") == "doc-noteref" for node in nodes), 5)
        self.assertEqual(sum(node.get("role") == "doc-backlink" for node in nodes), 5)
        targets = ["tbl:base", "fig:flujo", "document-note-1", "document-note-5",
                   "document-note-ref-1-1", "document-note-ref-2-1", "document-note-ref-5-1"]
        pages = self.navigation.resolve_toc_pages(output, [{"id": target} for target in targets])
        self.assertEqual(pages["document-note-ref-1-1"], 1)
        self.assertEqual(pages["document-note-ref-2-1"], 1)
        self.assertGreater(pages["tbl:base"], 1)
        self.assertEqual(pages["document-note-ref-5-1"], pages["fig:flujo"])
        bookmarks = self.navigation.read_bookmarks(output)
        heading = next(item for item in bookmarks if label_key(item["title"]) == label_key("Razón (a)/(b)[3]"))
        self.assertEqual(heading["page"], pages["tbl:base"])
        for item in bookmarks:
            self.assertNotIn(r"\frac", item["title"])
            self.assertNotIn("[@", item["title"])

    def test_without_indices_or_captions_plain_labels_and_original_notes_stay_complete(self):
        markdown = r'''---
documento: {}
---
| Dato | Valor |
| --- | --- |
| Título | Informe $x^2$[^titulo] de [@tbl:base] |
| Subtítulo | Análisis $\frac{a}{b}$ |
| Versión | 1.0 |

## Cálculo $\frac{a}{b}$[^seccion]

Tabla: Dato $x^2$[^tabla] {#tbl:base}

| A | B |
| --- | --- |
| Uno | Dos |

Consulte [@tbl:base] y [@fig:flujo].

Figura: Flujo de $x^2$ {#fig:flujo}

![Flujo](flujo.svg)

[^titulo]: Fuente del título.
[^seccion]: Fuente de la sección.
[^tabla]: Fuente de la tabla.
'''
        output, args, nodes, texts, pdf_title = self.render(
            markdown, "--no-cover", "--no-toc", "--no-table-index", "--no-figure-index", "--no-captions"
        )
        self.assertFalse(args.cover)
        self.assertEqual((args.toc_entries_count, args.table_index_count, args.figure_index_count), (0, 0, 0))
        self.assertFalse(any(node.tag == "nav" for node in nodes))
        self.assertFalse(any(node.get("data-document-caption") for node in nodes))
        self.assertEqual(args.footnote_count, 3)
        self.assertEqual(sum(node.get("role") == "doc-noteref" for node in nodes), 3)
        self.assert_readable_title(args, texts, pdf_title, "Informe x^(2)[1] de Tabla 2")
        self.assertEqual(label_key(args.resolved_metadata["subtitulo"]), label_key("Análisis (a)/(b)"))
        self.assertIn("Consulte Tabla 2 y Figura 1.", " ".join(texts))
        bookmarks = self.navigation.read_bookmarks(output)
        self.assertTrue(any(label_key(item["title"]) == label_key("Cálculo (a)/(b)[2]") for item in bookmarks))
        targets = ["tbl:base", "fig:flujo", "document-note-1", "document-note-3",
                   "document-note-ref-1-1", "document-note-ref-3-1"]
        self.assertEqual(len(self.navigation.resolve_toc_pages(output, [{"id": target} for target in targets])), 6)

    def test_formula_only_headings_keep_native_bookmarks_without_an_index(self):
        markdown = r'''# $x^2$

Texto inicial.

## $\frac{a}{b}$

Primer cálculo.

<!-- pagebreak -->

## $\frac{c}{d}$

Segundo cálculo.
'''
        output, args, _, texts, pdf_title = self.render(markdown, '--no-toc')
        self.assert_readable_title(args, texts, pdf_title, 'x^(2)')
        bookmarks = self.navigation.read_bookmarks(output)
        self.assertEqual([item['title'] for item in bookmarks], ['x^(2)', '(a)/(b)', '(c)/(d)'])
        self.assertEqual([item['page'] for item in bookmarks], [1, 1, 2])
        self.assertEqual([item['level'] for item in bookmarks], [1, 2, 2])


if __name__ == "__main__":
    unittest.main()
