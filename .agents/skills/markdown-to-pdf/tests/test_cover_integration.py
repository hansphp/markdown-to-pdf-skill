"""Real-browser cover pagination, layout limits and navigation."""

import importlib.util
import os
import re
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "convert_markdown_to_pdf.py"
SPEC = importlib.util.spec_from_file_location("mdpdf_cover_integration", SCRIPT)
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)


def normalized(text):
    return re.sub(r"\s+", " ", text or "").strip()


@unittest.skipUnless(os.environ.get("MDPDF_BROWSER_TESTS") == "1", "Requiere MDPDF_BROWSER_TESTS=1")
class CoverIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mdpdf-cover-pdf-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "document.md"

    def test_cover_toggle_preserves_destinations_metadata_and_physical_page_numbers(self):
        from pypdf import PdfReader
        markdown = '''---
documento:
  titulo: "Informe con portada"
  subtitulo: "Prueba de navegación"
  codigo: "DOC-01"
  version: "0.1"
  estado: "Borrador"
  clasificacion: "INTERNO"
pdf:
  portada: true
---
Introducción conservada fuera de la portada.

## 1. Alcance

[Datos iniciales](#table-1) y [última sección](#2-revisión).

## 2. Revisión

Texto de revisión.
'''
        self.source.write_text(markdown, encoding="utf-8")
        navigation = converter.load_support_module("pdf_navigation")
        structure_module = converter.load_support_module("document_structure")
        for cover in (True, False):
            with self.subTest(cover=cover):
                output = self.root / f"cover-{cover}.pdf"
                args = converter.parse_args([str(self.source), "--output", str(output), *([] if cover else ["--no-cover"])])
                converter.convert(args)
                self.assertEqual(self.source.read_text(encoding="utf-8"), markdown)
                html, _, _ = converter.build_document(self.source, None, "A4", False, True, cover=cover)
                _, structure = structure_module.prepare_document(html)
                pages = navigation.resolve_toc_pages(output, structure["entries"])
                self.assertEqual(len(pages), 2)
                self.assertEqual(args.table_count, 1)
                self.assertEqual(args.figure_count, 0)
                bookmarks = navigation.read_bookmarks(output)
                self.assertEqual(next(item["page"] for item in bookmarks if item["title"] == "Índice"), 2)
                self.assertEqual(next(item["page"] for item in bookmarks if item["title"] == "Informe con portada"), 1)
                with PdfReader(str(output)) as reader:
                    texts = [normalized(page.extract_text()) for page in reader.pages]
                    self.assertEqual(len(texts), 3)
                    self.assertIn("Código DOC-01", texts[0])
                    self.assertIn("Versión 0.1", texts[0])
                    self.assertIn("Tabla 1. Datos del documento", texts[0])
                    self.assertIn("Índice", texts[1])
                    self.assertIn("Introducción conservada", texts[2] if cover else texts[0])
                    if cover:
                        self.assertNotIn("Introducción conservada", texts[0])
                        self.assertNotIn("Página 1 de", texts[0])
                        self.assertEqual(texts[0].count("Informe con portada"), 1)
                    for number, text in enumerate(texts[1:], 2):
                        self.assertIn(f"Página {number} de {len(texts)}", text)
                    destinations = navigation.resolve_toc_pages(output, [
                        {"id": "table-1", "title": "Datos iniciales"},
                        {"id": "2-revisión", "title": "2. Revisión"},
                    ])
                    self.assertEqual(destinations["table-1"], 1)
                    self.assertEqual(destinations["2-revisión"], pages["2-revisión"])

    def test_long_title_fits_landscape_papers_without_spilling_or_clipping(self):
        from pypdf import PdfReader
        title = "Evaluación de documentos y requisitos de la operación " * 9
        markdown = f'---\ndocumento:\n  titulo: "{title.strip()}"\n  subtitulo: "Subtítulo extenso para comprobar el formato horizontal"\n  codigo: "DOC-LARGO"\n  version: "1.0"\npdf:\n  portada: true\n---\n## 1. Contenido\n\nTexto final conservado.\n'
        self.source.write_text(markdown, encoding="utf-8")
        for paper, width, height in (("Letter", 792, 612), ("A4", 841.89, 595.28), ("Legal", 1008, 612)):
            for branding in (True, False):
                with self.subTest(paper=paper, branding=branding):
                    output = self.root / f"long-title-{paper}-{branding}.pdf"
                    args = converter.parse_args([
                        str(self.source), "--output", str(output), "--paper", paper,
                        "--landscape", "--no-toc", "--strict", *([] if branding else ["--no-branding"]),
                    ])
                    converter.convert(args)
                    self.assertEqual(args.validation_diagnostics, [])
                    self.assertEqual(self.source.read_text(encoding="utf-8"), markdown)
                    with PdfReader(str(output)) as reader:
                        self.assertEqual(len(reader.pages), 2)
                        first = normalized(reader.pages[0].extract_text())
                        self.assertIn(normalized(title), first)
                        self.assertIn("Subtítulo extenso para comprobar el formato horizontal", first)
                        self.assertIn("DOC-LARGO", first)
                        self.assertNotIn("Página 1 de", first)
                        self.assertNotIn("Texto final conservado", first)
                        second = normalized(reader.pages[1].extract_text())
                        self.assertIn("Texto final conservado", second)
                        if branding:
                            self.assertIn("Página 2 de 2", second)
                        else:
                            self.assertNotIn("Página 2 de 2", second)
                        for page in reader.pages:
                            self.assertAlmostEqual(float(page.mediabox.width), width, delta=1)
                            self.assertAlmostEqual(float(page.mediabox.height), height, delta=1)

    def test_cover_with_multipage_index_keeps_all_final_destinations(self):
        from pypdf import PdfReader
        parts = ['---', 'documento:', '  titulo: "Informe extenso"', 'pdf:', '  portada: true', '---',
                 'Introducción después del índice.', '']
        for number in range(1, 46):
            parts.extend([f'## Sección {number:02d}', '', 'Contenido de la sección.', '',
                          '### Verificación', '', 'Evidencia de la sección.', ''])
        self.source.write_text('\n'.join(parts), encoding='utf-8')
        args = converter.parse_args([str(self.source)])
        output, _ = converter.convert(args)
        html, _, _ = converter.build_document(self.source, None, 'A4', False, True)
        _, structure = converter.load_support_module('document_structure').prepare_document(html)
        navigation = converter.load_support_module('pdf_navigation')
        pages = navigation.resolve_toc_pages(output, structure['entries'])
        self.assertEqual(len(pages), 90)
        self.assertGreaterEqual(pages[structure['entries'][0]['id']], 4)
        with PdfReader(str(output)) as reader:
            texts = [normalized(page.extract_text()) for page in reader.pages]
            first_section = pages[structure['entries'][0]['id']] - 1
            index_text = ' '.join(texts[1:first_section])
            rows = [(title, int(page)) for title, page in re.findall(r'(Sección \d{2}|Verificación)\s+(\d+)\b', index_text)]
            expected = [(entry['title'], pages[entry['id']]) for entry in structure['entries']]
            self.assertEqual(rows, expected)
            self.assertNotIn('Página 1 de', texts[0])
            self.assertIn('Introducción después del índice', texts[first_section])
            self.assertEqual(len(navigation.read_bookmarks(output)), 92)

    def test_cover_only_document_has_no_trailing_blank_page(self):
        from pypdf import PdfReader
        self.source.write_text('---\ndocumento:\n  titulo: "Solo título"\n  clasificacion: ""\npdf:\n  portada: true\n  logo: null\n---\n', encoding="utf-8")
        output, _ = converter.convert(converter.parse_args([str(self.source)]))
        with PdfReader(str(output)) as reader:
            self.assertEqual(len(reader.pages), 1)
            self.assertEqual(normalized(reader.pages[0].extract_text()), "Solo título")

    def test_unfittable_cover_fails_without_replacing_existing_output(self):
        self.source.write_text('---\ndocumento:\n  titulo: "Título"\npdf:\n  portada: true\n---\n## 1. Contenido\n', encoding="utf-8")
        css = self.root / "oversize.css"
        css.write_text('.document-cover [data-document-role="title"] { min-height: 2000mm; }')
        output = self.source.with_suffix('.pdf')
        output.write_bytes(b"Previous output must survive")
        args = converter.parse_args([str(self.source), "--css", str(css), "--force"])
        with self.assertRaisesRegex(converter.ConversionError, "portada no cabe"):
            converter.convert(args)
        self.assertEqual(output.read_bytes(), b"Previous output must survive")


if __name__ == '__main__':
    unittest.main()
