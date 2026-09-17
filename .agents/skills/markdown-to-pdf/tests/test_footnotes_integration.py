"""Optional real-PDF checks for note numbering, content and both link directions."""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "convert_markdown_to_pdf.py"
SPEC = importlib.util.spec_from_file_location("mdpdf_footnotes_pdf_tests", SCRIPT)
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)


@unittest.skipUnless(os.environ.get("MDPDF_BROWSER_TESTS") == "1", "Requiere MDPDF_BROWSER_TESTS=1")
class FootnotePDFTests(unittest.TestCase):
    def test_list_code_is_printed_literally_beside_a_real_note_with_the_same_label(self):
        from pypdf import PdfReader

        markdown = '''# Notas y ejemplos

Texto con una nota real[^literal].

- ```markdown
  [^literal]: Ejemplo de sintaxis conservado.
  ```

1. Lista exterior.
   - [x] ~~~markdown
     [^otro]: Ejemplo anidado conservado.
     ~~~

[^literal]: Explicación de la nota real.
'''
        with tempfile.TemporaryDirectory(prefix="mdpdf-notes-list-code-") as directory:
            source = Path(directory) / "document.md"
            source.write_text(markdown, encoding="utf-8")
            args = converter.parse_args([str(source), "--no-logo", "--strict"])
            output, engine = converter.convert(args)
            self.assertTrue(engine.startswith("playwright/"))
            self.assertEqual(args.footnote_count, 1)
            self.assertEqual(source.read_text(encoding="utf-8"), markdown)
            with PdfReader(str(output)) as reader:
                text = " ".join(page.extract_text() or "" for page in reader.pages)
                for expected in (
                    "[^literal]: Ejemplo de sintaxis conservado.",
                    "[^otro]: Ejemplo anidado conservado.",
                    "Explicación de la nota real.",
                ):
                    self.assertEqual(text.count(expected), 1)
            navigation = converter.load_support_module("pdf_navigation")
            self.assertEqual(len(navigation.resolve_toc_pages(output, [
                {"id": "document-note-1"}, {"id": "document-note-ref-1-1"},
            ])), 2)

    def test_printed_notes_have_stable_numbering_and_destinations_in_both_directions(self):
        from pypdf import PdfReader

        markdown = '''# Informe de notas

## Referencias

Primera aparición[^segunda] y otra fuente[^primera].

Tabla: Estados {#tbl:estados}

| Estado | Valor |
| --- | --- |
| Activo | 1 |

<!-- pagebreak -->

## Continuación

Segunda aparición de la misma nota[^segunda].

[^primera]: Fuente uno; consulte [@tbl:estados].

    ### Encabezado dentro de la nota

    - Primer elemento.
    - Segundo elemento y [enlace](https://example.com).

[^segunda]: Fuente dos con **texto destacado**.

    Otro párrafo que debe conservarse.

    ```text
    [^literal] sigue siendo código.
    ```
'''
        with tempfile.TemporaryDirectory(prefix="mdpdf-notes-pdf-") as directory:
            source = Path(directory) / "document.md"
            source.write_text(markdown, encoding="utf-8")
            args = converter.parse_args([str(source), "--no-logo", "--strict"])
            output, engine = converter.convert(args)
            self.assertTrue(engine.startswith("playwright/"))
            self.assertEqual(source.read_text(encoding="utf-8"), markdown)
            self.assertEqual(args.footnote_count, 2)
            with PdfReader(str(output)) as reader:
                texts = [page.extract_text() or "" for page in reader.pages]
                all_text = " ".join(texts)
                for expected in ("Fuente uno", "Fuente dos", "Otro párrafo", "Primer elemento", "[^literal]"):
                    self.assertIn(expected, all_text)
                self.assertNotIn("[^primera]", all_text)
                self.assertNotIn("[^segunda]", all_text)
                self.assertNotIn("[@tbl:estados]", all_text)
                self.assertLess(all_text.index("Fuente dos"), all_text.index("Fuente uno"))
                self.assertEqual(all_text.count("Fuente dos"), 1)
                self.assertEqual(all_text.count("Fuente uno"), 1)
                link_count = sum(1 for page in reader.pages for annotation in page.get("/Annots", [])
                                 if annotation.get_object().get("/Subtype") == "/Link")
                self.assertGreaterEqual(link_count, 10)
            navigation = converter.load_support_module("pdf_navigation")
            targets = ["document-note-1", "document-note-2", "document-note-ref-1-1",
                       "document-note-ref-1-2", "document-note-ref-2-1", "document-notes", "tbl:estados"]
            pages = navigation.resolve_toc_pages(output, [{"id": target} for target in targets])
            self.assertEqual(len(pages), 7)
            self.assertGreater(pages["document-note-ref-1-2"], pages["document-note-ref-1-1"])
            self.assertGreaterEqual(pages["document-note-1"], pages["document-note-ref-1-2"])
            bookmarks = navigation.read_bookmarks(output)
            self.assertIn("Notas", [item["title"] for item in bookmarks])
            # Native browser bookmarks retain semantic subheadings in notes;
            # the printed section index deliberately lists only "Notas".
            inner = next(item for item in bookmarks if item["title"] == "Encabezado dentro de la nota")
            self.assertGreaterEqual(inner["page"], pages["document-note-2"])
            document, _, _ = converter.build_document(source, None, "A4", False, True)
            _, registry = converter.load_support_module("document_structure").prepare_document(document)
            self.assertNotIn("Encabezado dentro de la nota", [item["title"] for item in registry["entries"]])

    def test_basic_browser_engine_renders_notes_without_navigation_dependencies(self):
        from pypdf import PdfReader

        with tempfile.TemporaryDirectory(prefix="mdpdf-notes-basic-") as directory:
            source = Path(directory) / "document.md"
            source.write_text('# Documento\n\nTexto[^a].\n\n[^a]: Nota básica con retorno.\n', encoding="utf-8")
            args = converter.parse_args([str(source), "--no-branding", "--no-toc", "--no-bookmarks", "--engine", "browser"])
            output, engine = converter.convert(args)
            self.assertTrue(engine.startswith("browser/"))
            with PdfReader(str(output)) as reader:
                text = " ".join(page.extract_text() or "" for page in reader.pages)
                self.assertIn("Nota básica con retorno.", text)
                self.assertNotIn("[^a]", text)
            navigation = converter.load_support_module("pdf_navigation")
            self.assertEqual(len(navigation.resolve_toc_pages(output, [
                {"id": "document-note-1"}, {"id": "document-note-ref-1-1"},
            ])), 2)

    def test_invalid_notes_fail_before_replacing_an_existing_pdf(self):
        with tempfile.TemporaryDirectory(prefix="mdpdf-notes-errors-") as directory:
            source = Path(directory) / "document.md"
            output = source.with_suffix(".pdf")
            output.write_bytes(b"existing-result")
            for source_text in (
                '# Documento\n\nTexto[^ausente].\n',
                '# Documento\n\n[^unused]: Definición sin llamada.\n',
                '# Documento\n\nTexto[^a].\n\n[^a]: Una.\n[^a]: Otra.\n',
            ):
                with self.subTest(source=source_text):
                    source.write_text(source_text, encoding="utf-8")
                    args = converter.parse_args([str(source), "--force"])
                    with self.assertRaises(converter.ConversionError):
                        converter.convert(args)
                    self.assertEqual(output.read_bytes(), b"existing-result")
                    self.assertEqual(source.read_text(encoding="utf-8"), source_text)


if __name__ == "__main__":
    unittest.main()
