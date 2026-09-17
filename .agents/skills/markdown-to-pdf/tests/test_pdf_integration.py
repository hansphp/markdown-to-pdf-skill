"""Integración opcional: MDPDF_BROWSER_TESTS=1 habilita el navegador real."""

import hashlib
import importlib.util
import os
import re
import tempfile
import unicodedata
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "convert_markdown_to_pdf.py"
SPEC = importlib.util.spec_from_file_location("mdpdf_browser_integration", SCRIPT)
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)


def normalized(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text).replace("\u00ad", "")).strip()


def painted_images(page, reader):
    """Identifica imágenes realmente dibujadas, incluidas las de formularios PDF.

    Se leen flujos PDF; no se rasteriza ni se necesita Pillow. La intersección
    entre páginas permite comprobar la imagen repetida del encabezado.
    """
    from pypdf.generic import ContentStream

    images = set()
    visited = set()

    def inspect(content, resources):
        if content is None or resources is None:
            return
        resources = resources.get_object()
        objects = resources.get("/XObject", {}).get_object() if "/XObject" in resources else {}
        for operands, operator in ContentStream(content, reader).operations:
            if operator != b"Do" or not operands or operands[0] not in objects:
                continue
            obj = objects[operands[0]].get_object()
            identity = id(obj)
            if identity in visited:
                continue
            visited.add(identity)
            if obj.get("/Subtype") == "/Image":
                images.add((int(obj["/Width"]), int(obj["/Height"]), hashlib.sha256(obj.get_data()).digest()))
            elif obj.get("/Subtype") == "/Form":
                inspect(obj, obj.get("/Resources", resources))

    inspect(page.get_contents(), page.get("/Resources"))
    return images


@unittest.skipUnless(os.environ.get("MDPDF_BROWSER_TESTS") == "1", "Requiere MDPDF_BROWSER_TESTS=1 para iniciar un navegador real")
class PDFIntegrationTests(unittest.TestCase):
    def test_footer_keeps_pagination_with_long_or_omitted_labels(self):
        from pypdf import PdfReader

        long_title = 'TÍTULO <literal> & ' + 'Evaluación de documentos y requisitos ' * 30
        long_subtitle = 'SUBTÍTULO ' + 'MUYLARGOSINESPACIOS' * 35
        cases = [
            ('A4', False, long_title, long_subtitle),
            ('A4', True, '', long_subtitle),
            ('Letter', False, long_title, ''),
            ('Letter', True, long_title, long_subtitle),
            ('Legal', False, long_title, long_subtitle),
            ('Legal', True, long_title, long_subtitle),
            ('A4', False, 'Título breve', 'Subtítulo breve'),
            ('A4', False, '', ''),
        ]
        with tempfile.TemporaryDirectory(prefix='mdpdf-footer-pdf-') as directory:
            root = Path(directory)
            source = root / 'document.html'
            for case, (paper, landscape, title, subtitle) in enumerate(cases):
                with self.subTest(paper=paper, landscape=landscape, title=bool(title), subtitle=bool(subtitle)):
                    orientation = 'landscape' if landscape else 'portrait'
                    source.write_text(
                        '<!doctype html><html><head><meta charset="utf-8"><style>'
                        f'@page {{ size: {paper} {orientation}; margin: 20mm 16mm 18mm; }}'
                        'section { break-before: page; } section:first-child { break-before: auto; }'
                        '</style></head><body>'
                        + ''.join(f'<section>CONTENIDO {number}</section>' for number in range(1, 13))
                        + '</body></html>', encoding='utf-8')
                    output = root / f'footer-{case}.pdf'
                    converter.render_with_playwright(
                        source, output, True, title, subtitle, classification='', bookmarks=False,
                    )
                    with PdfReader(output) as reader:
                        self.assertEqual(len(reader.pages), 12)
                        for number, page in enumerate(reader.pages, 1):
                            text = normalized(page.extract_text())
                            self.assertIn(f'CONTENIDO {number}', text)
                            self.assertIn(f'Página {number} de 12', text)
                            self.assertEqual(text.count('…'), int(title == long_title) + int(subtitle == long_subtitle))
                            if title == long_title:
                                self.assertIn('TÍTULO <literal> &', text)
                                self.assertNotIn(long_title.strip(), text)
                            elif title:
                                self.assertIn(title, text)
                            if subtitle == long_subtitle:
                                self.assertIn('SUBTÍTULO MUYLARGOSINESPACIOS', text)
                                self.assertNotIn(long_subtitle, text)
                            elif subtitle:
                                self.assertIn(subtitle, text)

    def test_central_metadata_reaches_body_footer_title_and_navigation(self):
        from pypdf import PdfReader

        template = '''---
documento:
  titulo: "Informe centralizado"
  subtitulo: "Revisión de metadatos"
  codigo: "DOC-001"
  version: "0.10"
  fecha: "2026-09-13"
  estado: "En revisión"
  clasificacion: "USO INTERNO"
---
# Título anterior

## Subtítulo anterior

Introducción que se conserva.

| Dato | Valor |
| --- | --- |
| Versión | 0.01 |
| Estado | Antiguo |

## 1. Contenido

[Título](#título-anterior) y [tabla documental](#table-1).

La versión histórica 0.01 se mantiene en el cuerpo.

## 2. Control de cambios

| Versión histórica | Estado histórico |
| --- | --- |
| 0.01 | Antiguo |
'''
        with tempfile.TemporaryDirectory(prefix="mdpdf-metadata-pdf-") as directory:
            source = Path(directory) / "document.md"
            navigation = converter.load_support_module("pdf_navigation")
            structure_module = converter.load_support_module("document_structure")
            for iteration, (title, version, options) in enumerate([
                ("Informe centralizado", "0.20", ["--document-version", "0.20", "--classification", "EJEMPLO"]),
                ("Informe actualizado", "0.30", []),
            ]):
                markdown = template if iteration == 0 else template.replace("Informe centralizado", title).replace('"0.10"', '"0.30"')
                source.write_text(markdown, encoding="utf-8")
                args = converter.parse_args([str(source), "--output", str(Path(directory) / f"result-{iteration}.pdf"), *options])
                output, engine = converter.convert(args)
                self.assertTrue(engine.startswith("playwright/"))
                self.assertEqual(source.read_text(encoding="utf-8"), markdown)
                self.assertEqual(args.resolved_metadata["titulo"], title)
                self.assertEqual(args.resolved_metadata["version"], version)
                self.assertEqual(args.table_count, 2)
                html, _, _ = converter.build_document(source, None, "A4", False, True, args.metadata_overrides)
                _, structure = structure_module.prepare_document(html)
                self.assertEqual([entry["title"] for entry in structure["entries"]], ["1. Contenido", "2. Control de cambios"])
                destinations = navigation.resolve_toc_pages(output, structure["entries"])
                self.assertEqual(len(destinations), 2)
                with PdfReader(str(output)) as reader:
                    self.assertEqual(reader.metadata.title, title)
                    texts = [normalized(page.extract_text() or "") for page in reader.pages]
                    first = texts[0]
                    self.assertIn(f"Versión {version}", first)
                    self.assertIn("Estado En revisión", first)
                    self.assertIn("Código DOC-001", first)
                    self.assertIn("Fecha 2026-09-13", first)
                    self.assertNotIn("0.01", first)
                    self.assertNotIn("Título anterior", first)
                    self.assertIn("La versión histórica 0.01 se mantiene", " ".join(texts))
                    for number, text in enumerate(texts, 1):
                        self.assertIn(title, text)
                        self.assertIn("Revisión de metadatos", text)
                        self.assertIn("EJEMPLO" if iteration == 0 else "USO INTERNO", text)
                        self.assertIn(f"Página {number} de {len(texts)}", text)

    def test_complete_document_has_stable_multipage_index_and_repeated_page_furniture(self):
        from pypdf import PdfReader

        self.assertTrue(converter.playwright_available(), "Ejecute esta prueba con el Python del entorno local del skill")
        navigation = converter.load_support_module("pdf_navigation")
        structure_module = converter.load_support_module("document_structure")
        title = "Prueba de navegación PDF"
        subtitle = "Ámbito 01"

        with tempfile.TemporaryDirectory(prefix="mdpdf-browser-test-") as directory:
            root = Path(directory)
            source = root / "document.md"
            (root / "diagram.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="80" viewBox="0 0 240 80">'
                '<rect x="2" y="2" width="236" height="76" rx="8" fill="#e5e7eb" stroke="#374151"/>'
                '<path d="M30 40h180m-20-12 20 12-20 12" fill="none" stroke="#2563eb" stroke-width="4"/>'
                '</svg>', encoding="utf-8",
            )
            parts = [f"# {title}", "", "Documento de ensayo para verificar navegación y contenido completo.", ""]
            expected_titles = []
            for number in range(1, 46):
                section = f"Ámbito {number:02d}"
                repeated = "Comprobación repetida"
                expected_titles.extend([section, repeated])
                parts.extend([f"## {section}", "", f"Requisito verificable del ámbito {number:02d}.", ""])
                if number == 1:
                    parts.extend([
                        "Tabla: Valores de aceptación", "",
                        "| Campo | Valor |", "| --- | --- |", "| Estado | Aprobado |", "",
                    ])
                parts.extend([f"### {repeated}", "", f"Evidencia específica de la comprobación {number:02d}.", ""])
                if number == 45:
                    parts.extend([
                        "Figura: Flujo de comprobación", "", "![Texto alternativo](diagram.svg)", "",
                        "Última evidencia conservada.", "",
                    ])
            markdown = "\n".join(parts)
            source.write_text(markdown, encoding="utf-8")

            args = converter.parse_args([str(source)])
            output, engine = converter.convert(args)
            self.assertTrue(engine.startswith("playwright/"))
            self.assertEqual(source.read_text(encoding="utf-8"), markdown)
            self.assertEqual(args.toc_entries_count, 90)
            self.assertEqual((args.table_count, args.figure_count), (1, 1))

            html, _, _ = converter.build_html(source, None, args.paper, args.landscape, True)
            _, structure = structure_module.prepare_document(html)
            entries = structure["entries"]
            self.assertEqual([entry["title"] for entry in entries], expected_titles)
            destinations = navigation.resolve_toc_pages(output, entries)
            self.assertEqual(len(destinations), 90)
            bookmarks = navigation.read_bookmarks(output)
            index_bookmarks = [item for item in bookmarks if item["title"] == "Índice"]
            self.assertEqual(len(index_bookmarks), 1)
            self.assertGreater(index_bookmarks[0]["page"], 1)
            self.assertFalse(any(item["title"] in {"Í", "ndice"} for item in bookmarks))
            self.assertEqual([item["title"] for item in bookmarks if item["title"] not in {title, "Índice"}], expected_titles)

            with PdfReader(str(output)) as reader:
                texts = [normalized(page.extract_text() or "") for page in reader.pages]
                index_start = index_bookmarks[0]["page"] - 1
                first_section = destinations[entries[0]["id"]] - 1
                self.assertGreaterEqual(first_section - index_start, 2, "El índice de 90 entradas debe ocupar varias páginas")
                index_text = normalized(" ".join(texts[index_start:first_section]))
                printed_rows = [(label, int(number)) for label, number in re.findall(
                    r"(Ámbito \d{2}|Comprobación repetida)\s+(\d+)\b", index_text,
                )]
                expected_rows = [(entry["title"], destinations[entry["id"]]) for entry in entries]
                self.assertEqual(printed_rows, expected_rows, "Cada fila debe imprimir la página real de su destino")
                for entry in entries:
                    self.assertIn(entry["title"], texts[destinations[entry["id"]] - 1])

                all_text = normalized(" ".join(texts))
                self.assertIn("Tabla 1. Valores de aceptación", all_text)
                self.assertIn("Figura 1. Flujo de comprobación", all_text)
                self.assertIn("Estado Aprobado", all_text)
                self.assertIn("Última evidencia conservada.", all_text)
                common_images = None
                for number, (page, text) in enumerate(zip(reader.pages, texts), 1):
                    with self.subTest(page=number):
                        self.assertIn("CONFIDENCIAL", text)
                        self.assertIn(title, text)
                        self.assertIn(subtitle, text)
                        pagination = f"Página {number} de {len(reader.pages)}"
                        self.assertIn(pagination, text)
                        body = text.replace("CONFIDENCIAL", "").replace(title, "").replace(subtitle, "").replace(pagination, "")
                        self.assertGreater(len(body.split()), 1, "No debe existir una página vacía o con un glifo aislado")
                        images = painted_images(page, reader)
                        self.assertTrue(images, "Falta la imagen del encabezado")
                        common_images = images if common_images is None else common_images & images
                self.assertTrue(common_images, "El mismo logotipo debe dibujarse en todas las páginas")


if __name__ == "__main__":
    unittest.main()
