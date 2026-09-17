"""Cover composition preserves body content and document navigation."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load_module(name):
    spec = importlib.util.spec_from_file_location(f"cover_tests_{name}", SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


structure = load_module("document_structure")
cover_module = load_module("document_cover")
apply_cover = cover_module.apply_cover

TITLE = '<h1 id="documento" data-document-role="title">Documento <em>ejemplo</em></h1>'
SUBTITLE = '<h2 id="subtitulo" data-document-role="subtitle">Sistema local</h2>'
METADATA = ('<table id="datos" data-document-role="metadata"><thead><tr><th>Dato</th>'
            '<th>Valor</th></tr></thead><tbody><tr><td>Versión</td><td>0.1</td></tr>'
            '<tr><td>Estado</td><td>Borrador</td></tr></tbody></table>')
BODY_TABLE = '<table id="cambios"><tr><th>Fecha</th><th>Cambio</th></tr><tr><td>Hoy</td><td>Revisión</td></tr></table>'


def wrap(body):
    return '<!doctype html><html lang="es"><head><title>Documento</title></head><body><main>' + body + '</main></body></html>'


def covered(body, metadata=None, logo=None):
    return apply_cover(wrap(body), metadata or {}, logo, structure)


def main_children(document):
    parser = structure._DocumentParser()
    parser.feed(document)
    parser.close()
    main = next(node for node in structure._walk(parser.root) if node.tag == "main")
    return [node for node in main.children if not node.tag.startswith("#")]


class CoverCompositionTests(unittest.TestCase):
    def test_presentation_moves_once_without_modifying_input_or_body(self):
        intro = '<p id="intro">Texto introductorio &amp; <a href="#datos">datos</a>.</p>'
        body = '<h2 id="contenido" data-document-role="section">1. Contenido</h2>' + BODY_TABLE
        original = wrap(TITLE + intro + SUBTITLE + METADATA + body)
        before = str(original)
        result = apply_cover(original, {}, None, structure)
        self.assertEqual(original, before)
        children = main_children(result)
        self.assertEqual([node.tag for node in children], ["section", "p", "h2", "table"])
        self.assertEqual(children[0].get("data-document-role"), "cover")
        self.assertIn(TITLE, structure._serialize(children[0]))
        self.assertIn(SUBTITLE, structure._serialize(children[0]))
        self.assertIn(METADATA, structure._serialize(children[0]))
        self.assertIn(intro + body, result)
        for identifier in ("documento", "subtitulo", "datos", "intro", "contenido", "cambios"):
            self.assertEqual(result.count(f'id="{identifier}"'), 1)

    def test_nested_presentation_and_control_changes_remain_in_body(self):
        nested = '<blockquote>' + METADATA.replace('id="datos"', 'id="anidados"') + '</blockquote>'
        changes = '<h2 data-document-role="section">Control de cambios</h2>' + BODY_TABLE
        result = covered(TITLE + nested + changes)
        cover, quote, heading, table = main_children(result)
        self.assertNotIn("anidados", structure._serialize(cover))
        self.assertEqual(structure._serialize(quote), nested)
        self.assertEqual(structure._serialize(heading) + structure._serialize(table), changes)

    def test_classification_is_escaped_and_not_repeated_from_metadata_table(self):
        table = METADATA.replace('</tbody>', '<tr><td>Clasificación:</td><td>INTERNO</td></tr></tbody>')
        result = covered(TITLE + table, {"clasificacion": "INTERNO"})
        self.assertEqual(result.count("INTERNO"), 1)
        self.assertNotIn('data-document-role="cover-classification"', result)
        result = covered(TITLE, {"clasificacion": "INTERNO <A> & B"})
        self.assertIn('data-document-role="cover-classification">INTERNO &lt;A&gt; &amp; B</p>', result)

    def test_absent_fields_do_not_create_placeholder_elements(self):
        result = covered(TITLE, {"subtitulo": "", "clasificacion": ""})
        self.assertNotIn('data-document-role="subtitle"', result)
        self.assertNotIn('<table', result)
        self.assertNotIn('document-cover-top', result)
        self.assertNotIn('<img', result)
        self.assertEqual(len(main_children(result)), 1)

    def test_visible_metadata_without_title_is_supported(self):
        result = covered(METADATA)
        self.assertNotIn('<h1', result)
        self.assertNotIn('<h2', result)
        self.assertIn(METADATA, result)

    def test_logo_only_cover_does_not_invent_document_fields(self):
        result = covered('<p>Contenido sin título.</p>', logo='data:image/png;base64,ZmFrZQ==')
        cover = main_children(result)[0]
        serialized = structure._serialize(cover)
        self.assertIn('data-document-role="cover-logo"', serialized)
        self.assertNotIn('document-cover-content', serialized)
        self.assertNotIn('<h1', serialized)
        self.assertIn('<p>Contenido sin título.</p>', result)

    def test_classification_only_cover_is_visible(self):
        result = covered('<p>Contenido.</p>', {"clasificacion": "BORRADOR"})
        self.assertIn('data-document-role="cover-classification">BORRADOR</p>', result)

    def test_empty_cover_fails_instead_of_adding_a_blank_page(self):
        with self.assertRaisesRegex(ValueError, "portada no tiene contenido visible"):
            covered('<p>Contenido sin metadatos.</p>', {"titulo": "", "clasificacion": ""})

    def test_no_main_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, "contenido principal main"):
            apply_cover('<html><body>Texto.</body></html>', {}, None, structure)

    def test_repeated_cover_composition_is_idempotent(self):
        first = covered(TITLE + METADATA)
        self.assertEqual(apply_cover(first, {}, None, structure), first)


class CoverNavigationTests(unittest.TestCase):
    def test_index_is_between_cover_and_intro_and_excludes_cover_headings(self):
        source = covered(TITLE + SUBTITLE + METADATA + '<p id="intro">Introducción.</p>'
                         '<h2 id="alcance" data-document-role="section">1. Alcance</h2>'
                         '<h3 id="detalle" data-document-role="section">1.1 Detalle</h3>')
        result, registry = structure.prepare_document(source)
        children = main_children(result)
        self.assertEqual([node.tag for node in children], ["section", "nav", "p", "h2", "h3"])
        self.assertEqual([row["id"] for row in registry["entries"]], ["alcance", "detalle"])
        self.assertEqual([row["role"] for row in registry["headings"]],
                         ["title", "subtitle", "section", "section"])
        self.assertIn('href="#alcance"', result)
        self.assertNotIn('href="#documento"', result)

    def test_titleless_body_h1_remains_a_section(self):
        source = covered(METADATA + '<h1 id="contenido" data-document-role="section">Contenido</h1>')
        _, registry = structure.prepare_document(source)
        self.assertEqual([entry["id"] for entry in registry["entries"]], ["contenido"])

    def test_metadata_table_keeps_number_and_target_after_moving(self):
        source = covered(TITLE + METADATA + '<h2 data-document-role="section">Control de cambios</h2>'
                         '<p><a href="#datos">Datos documentales</a></p>' + BODY_TABLE)
        result, registry = structure.prepare_document(source)
        self.assertEqual([(row["id"], row["number"]) for row in registry["tables"]],
                         [("datos", 1), ("cambios", 2)])
        self.assertEqual(registry["tables"][0]["caption"], "Tabla 1. Datos del documento")
        self.assertEqual(result.count('id="datos"'), 1)
        self.assertIn('<a href="#datos">Datos documentales</a>', result)
        self.assertIn('>Tabla 1. Datos del documento</caption>', result)

    def test_cover_preserves_existing_caption_and_does_not_register_logo(self):
        table = METADATA.replace('<thead>', '<caption>Ficha <em>principal</em></caption><thead>')
        source = covered(TITLE + table + '<h2 data-document-role="section">Diseño</h2>'
                         '<p><img src="flujo.png" alt="Flujo"></p>', logo='data:image/png;base64,ZmFrZQ==')
        result, registry = structure.prepare_document(source)
        self.assertEqual(registry["tables"][0]["title"], "Ficha principal")
        self.assertIn('>Tabla 1. Ficha <em>principal</em></caption>', result)
        self.assertEqual([row["src"] for row in registry["figures"]], ["flujo.png"])
        self.assertEqual(registry["figures"][0]["number"], 1)

    def test_disabling_index_and_captions_keeps_cover_and_targets(self):
        source = covered(TITLE + METADATA + '<h2 id="alcance" data-document-role="section">Alcance</h2>')
        result, registry = structure.prepare_document(source, with_toc=False, with_captions=False)
        self.assertNotIn('<nav', result)
        self.assertNotIn('<caption', result)
        self.assertIn('data-document-role="cover"', result)
        self.assertEqual(registry["tables"][0]["id"], "datos")
        self.assertEqual(registry["entries"][0]["id"], "alcance")

    def test_repeated_preparation_keeps_single_index_after_cover(self):
        source = covered(TITLE + METADATA + '<p>Introducción.</p>'
                         '<h2 id="alcance" data-document-role="section">Alcance</h2>')
        first, first_registry = structure.prepare_document(source)
        second, second_registry = structure.prepare_document(first)
        self.assertEqual(first_registry, second_registry)
        self.assertEqual([node.tag for node in main_children(second)], ["section", "nav", "p", "h2"])
        self.assertEqual(second.count('<caption '), 1)


@unittest.skipUnless(importlib.util.find_spec("pypdf"), "La integración de portada requiere pypdf local")
class CoverPageReplacementTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.full = self.root / "full.pdf"
        self.clean = self.root / "clean.pdf"

    def create_pdf(self, path, *, complete=False, width=200, height=300, rotate=0, mcid=0):
        from pypdf import PdfWriter
        from pypdf.annotations import Link
        from pypdf.generic import (ArrayObject, BooleanObject, DecodedStreamObject,
                                  DictionaryObject, NameObject, NumberObject)

        with PdfWriter() as writer:
            first = writer.add_blank_page(width=width, height=height)
            if rotate:
                first.rotate(rotate)
            font_name = "/OriginalFont" if complete else "/CleanFont"
            font = writer._add_object(DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }))
            first[NameObject("/Resources")] = DictionaryObject({
                NameObject("/Font"): DictionaryObject({NameObject(font_name): font}),
            })
            drawing = f"/P <</MCID {mcid}>> BDC BT {font_name} 12 Tf 10 250 Td (Cover body) Tj ET EMC\n"
            if complete:
                drawing += f"/Artifact BMC BT {font_name} 8 Tf 10 15 Td (Original footer) Tj ET EMC\n"
            content = DecodedStreamObject()
            content.set_data(drawing.encode("ascii"))
            first[NameObject("/Contents")] = writer._add_object(content)

            # A real structure tree points back to the original Page object.
            first[NameObject("/StructParents")] = NumberObject(0)
            tree = DictionaryObject({NameObject("/Type"): NameObject("/StructTreeRoot")})
            tree_ref = writer._add_object(tree)
            element = writer._add_object(DictionaryObject({
                NameObject("/Type"): NameObject("/StructElem"), NameObject("/S"): NameObject("/P"),
                NameObject("/P"): tree_ref, NameObject("/Pg"): first.indirect_reference,
                NameObject("/K"): NumberObject(0),
            }))
            parent = writer._add_object(DictionaryObject({
                NameObject("/Nums"): ArrayObject([NumberObject(0), ArrayObject([element])]),
            }))
            tree.update({NameObject("/K"): ArrayObject([element]), NameObject("/ParentTree"): parent,
                         NameObject("/ParentTreeNextKey"): NumberObject(1)})
            writer._root_object[NameObject("/StructTreeRoot")] = tree_ref
            writer._root_object[NameObject("/MarkInfo")] = DictionaryObject({NameObject("/Marked"): BooleanObject(True)})

            if complete:
                second = writer.add_blank_page(width=width, height=height)
                second[NameObject("/Resources")] = first["/Resources"]
                body = DecodedStreamObject()
                body.set_data(b"BT /OriginalFont 12 Tf 10 250 Td (Body page) Tj ET")
                second[NameObject("/Contents")] = writer._add_object(body)
                writer.add_outline_item("Portada", 0)
                writer.add_outline_item("Contenido", 1)
                writer.add_named_destination("cover", 0)
                writer.add_named_destination("body", 1)
                for source_page, target_page in ((0, 1), (1, 0)):
                    annotation = writer.add_annotation(
                        source_page, Link(rect=(10, 20, 50, 30), target_page_index=target_page))
                    annotation["/Dest"][0] = writer.pages[target_page].indirect_reference
            writer.write(path)

    def test_replacement_removes_footer_and_preserves_navigation_resources_and_tags(self):
        from pypdf import PdfReader

        self.create_pdf(self.full, complete=True)
        self.create_pdf(self.clean)
        clean_bytes = self.clean.read_bytes()
        cover_module.replace_cover_page(self.full, self.clean)
        self.assertEqual(self.clean.read_bytes(), clean_bytes)
        with PdfReader(self.full) as result:
            self.assertEqual(len(result.pages), 2)
            self.assertEqual(result.pages[0].extract_text().strip(), "Cover body")
            self.assertEqual(result.pages[1].extract_text().strip(), "Body page")
            self.assertEqual(set(result.pages[0]["/Resources"]["/Font"]), {"/CleanFont"})
            self.assertEqual(set(result.pages[1]["/Resources"]["/Font"]), {"/OriginalFont"})
            self.assertEqual([result.get_destination_page_number(item) for item in result.outline], [0, 1])
            self.assertEqual({name: result.get_destination_page_number(dest)
                              for name, dest in result.named_destinations.items()}, {"cover": 0, "body": 1})
            for source_page, target_page in ((0, 1), (1, 0)):
                link = result.pages[source_page]["/Annots"][0].get_object()
                self.assertEqual(result.get_page_number(link["/Dest"][0].get_object()), target_page)
            tree = result.trailer["/Root"]["/StructTreeRoot"]
            element = tree["/K"][0].get_object()
            self.assertEqual(result.get_page_number(element["/Pg"]), 0)
            self.assertEqual(element["/K"], 0)
            self.assertEqual(result.pages[0]["/StructParents"], 0)
            self.assertEqual(tree["/ParentTree"]["/Nums"][1][0], tree["/K"][0])

    def test_different_geometry_is_rejected_without_overwriting_either_pdf(self):
        self.create_pdf(self.full, complete=True)
        self.create_pdf(self.clean, width=250)
        original, clean = self.full.read_bytes(), self.clean.read_bytes()
        with self.assertRaisesRegex(ValueError, "geometría"):
            cover_module.replace_cover_page(self.full, self.clean)
        self.assertEqual(self.full.read_bytes(), original)
        self.assertEqual(self.clean.read_bytes(), clean)
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ["clean.pdf", "full.pdf"])

    def test_different_rotation_is_rejected_without_overwriting(self):
        self.create_pdf(self.full, complete=True)
        self.create_pdf(self.clean, rotate=90)
        original = self.full.read_bytes()
        with self.assertRaisesRegex(ValueError, "orientación"):
            cover_module.replace_cover_page(self.full, self.clean)
        self.assertEqual(self.full.read_bytes(), original)

    def test_changed_tag_mapping_is_rejected_without_overwriting(self):
        self.create_pdf(self.full, complete=True)
        self.create_pdf(self.clean, mcid=1)
        original = self.full.read_bytes()
        with self.assertRaisesRegex(ValueError, "estructura etiquetada"):
            cover_module.replace_cover_page(self.full, self.clean)
        self.assertEqual(self.full.read_bytes(), original)

    def test_failed_write_cleans_temporary_and_preserves_original(self):
        self.create_pdf(self.full, complete=True)
        self.create_pdf(self.clean)
        original = self.full.read_bytes()
        with patch("pypdf.PdfWriter.write", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(ValueError, "integrar la portada"):
                cover_module.replace_cover_page(self.full, self.clean)
        self.assertEqual(self.full.read_bytes(), original)
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ["clean.pdf", "full.pdf"])

    def test_empty_input_fails_without_overwriting(self):
        from pypdf import PdfWriter

        self.create_pdf(self.full, complete=True)
        with PdfWriter() as writer:
            writer.write(self.clean)
        original = self.full.read_bytes()
        with self.assertRaisesRegex(ValueError, "al menos una página"):
            cover_module.replace_cover_page(self.full, self.clean)
        self.assertEqual(self.full.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
