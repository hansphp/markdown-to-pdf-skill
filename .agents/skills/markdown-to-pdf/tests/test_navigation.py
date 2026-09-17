"""Pruebas de paginación real, destinos y convergencia sin iniciar navegadores."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pdf_navigation.py"
SPEC = importlib.util.spec_from_file_location("mdpdf_navigation_tests", SCRIPT)
navigation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(navigation)
HAS_PYPDF = importlib.util.find_spec("pypdf") is not None


class ConvergenceTests(unittest.TestCase):
    def setUp(self):
        self.entries = [{"id": "capítulo", "title": "Capítulo", "level": 1}]

    def test_uses_pages_from_latest_pdf_until_the_printed_map_matches(self):
        render = Mock(return_value=Path("output.pdf"))
        with patch.object(navigation, "resolve_toc_pages", side_effect=[{"capítulo": 3}, {"capítulo": 4}, {"capítulo": 4}]):
            path, pages, passes = navigation.stabilize_toc(render, self.entries)
        self.assertEqual(path, Path("output.pdf"))
        self.assertEqual(pages, {"capítulo": 4})
        self.assertEqual(passes, 3)
        self.assertEqual([call.args[0] for call in render.call_args_list], [{}, {"capítulo": 3}, {"capítulo": 4}])

    def test_never_publishes_an_unstable_index_after_four_passes(self):
        render = Mock(return_value=Path("output.pdf"))
        maps = [{"capítulo": page} for page in (3, 4, 3, 4)]
        with patch.object(navigation, "resolve_toc_pages", side_effect=maps):
            with self.assertRaisesRegex(navigation.NavigationError, "4 pasadas"):
                navigation.stabilize_toc(render, self.entries)
        self.assertEqual(render.call_count, 4)

    def test_pass_limit_cannot_exceed_four(self):
        render = Mock()
        with self.assertRaises(navigation.NavigationError):
            navigation.stabilize_toc(render, self.entries, max_passes=5)
        render.assert_not_called()

    def test_duplicate_ids_are_rejected_before_rendering(self):
        render = Mock()
        with self.assertRaisesRegex(navigation.NavigationError, "duplicado"):
            navigation.stabilize_toc(render, self.entries + self.entries)
        render.assert_not_called()

    def test_missing_entry_id_is_rejected(self):
        with self.assertRaisesRegex(navigation.NavigationError, "identificador"):
            navigation.resolve_toc_pages(Path("unused.pdf"), [{"title": "Capítulo"}])

    def test_empty_index_needs_only_one_render_without_pdf_dependency(self):
        render = Mock(return_value=Path("output.pdf"))
        path, pages, passes = navigation.stabilize_toc(render, [])
        self.assertEqual((path, pages, passes), (Path("output.pdf"), {}, 1))

    def test_validation_detects_wrong_or_missing_printed_page_numbers(self):
        with patch.object(navigation, "resolve_toc_pages", return_value={"capítulo": 4}):
            with self.assertRaisesRegex(navigation.NavigationError, "capítulo"):
                navigation.validate_navigation(Path("output.pdf"), self.entries, {"capítulo": 3})
            with self.assertRaises(navigation.NavigationError):
                navigation.validate_navigation(Path("output.pdf"), self.entries, {})
            self.assertEqual(navigation.validate_navigation(Path("output.pdf"), self.entries, {"capítulo": 4}), {"capítulo": 4})


@unittest.skipUnless(HAS_PYPDF, "pypdf solo está disponible en el entorno local completo")
class PDFDestinationTests(unittest.TestCase):
    def setUp(self):
        from pypdf import PdfWriter
        self.PdfWriter = PdfWriter
        temporary = tempfile.TemporaryDirectory(prefix="mdpdf-navigation-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.pdf = self.root / "navigation.pdf"
        self.entries = [
            {"id": "capítulo", "title": "Título repetido", "level": 1},
            {"id": "capítulo-1", "title": "Título repetido", "level": 1},
            {"id": "final", "title": "Última sección", "level": 2},
        ]

    def writer_with_pages(self, count=4):
        writer = self.PdfWriter()
        for _ in range(count):
            writer.add_blank_page(width=595, height=842)
        return writer

    def test_unicode_ids_and_duplicate_titles_resolve_after_multipage_index(self):
        writer = self.writer_with_pages()
        writer.add_named_destination("/cap%C3%ADtulo", 2)
        writer.add_named_destination("/cap%C3%ADtulo-1", 3)
        writer.add_named_destination("/final", 3)
        writer.write(self.pdf)
        pages = navigation.resolve_toc_pages(self.pdf, self.entries)
        self.assertEqual(pages, {"capítulo": 3, "capítulo-1": 4, "final": 4})
        details = navigation.resolve_toc_destinations(self.pdf, self.entries)
        self.assertEqual(details["capítulo"]["named_destination"], "/cap%C3%ADtulo")
        self.assertEqual(details["capítulo"]["page_index"], 2)
        self.assertEqual(details["capítulo"]["source"], "named")

    def test_named_destinations_take_priority_over_same_title_outline(self):
        writer = self.writer_with_pages()
        writer.add_named_destination("/cap%C3%ADtulo", 2)
        writer.add_outline_item("Título repetido", 0)
        writer.write(self.pdf)
        self.assertEqual(navigation.resolve_toc_pages(self.pdf, self.entries[:1]), {"capítulo": 3})

    def test_missing_destination_is_reported(self):
        writer = self.writer_with_pages()
        writer.write(self.pdf)
        with self.assertRaisesRegex(navigation.NavigationError, "capítulo"):
            navigation.resolve_toc_pages(self.pdf, self.entries)

    def test_outline_fallback_requires_a_unique_title(self):
        writer = self.writer_with_pages()
        writer.add_outline_item("Última sección", 3)
        writer.write(self.pdf)
        details = navigation.resolve_toc_destinations(self.pdf, self.entries[-1:])
        self.assertEqual(details["final"]["page"], 4)
        self.assertEqual(details["final"]["source"], "outline")

    def test_ambiguous_duplicate_titles_cannot_replace_missing_ids(self):
        writer = self.writer_with_pages()
        writer.add_outline_item("Título repetido", 2)
        writer.add_outline_item("Título repetido", 3)
        writer.write(self.pdf)
        with self.assertRaises(navigation.NavigationError):
            navigation.resolve_toc_pages(self.pdf, self.entries[:2])

    def test_two_entries_cannot_share_a_single_outline_fallback(self):
        writer = self.writer_with_pages()
        writer.add_outline_item("Título repetido", 2)
        writer.write(self.pdf)
        with self.assertRaises(navigation.NavigationError):
            navigation.resolve_toc_pages(self.pdf, self.entries[:2])

    def test_bookmarks_preserve_repeated_titles_and_nesting(self):
        writer = self.writer_with_pages()
        writer.add_outline_item("Título repetido", 2)
        second = writer.add_outline_item("Título repetido", 3)
        writer.add_outline_item("Última sección", 3, parent=second)
        writer.write(self.pdf)
        bookmarks = navigation.read_bookmarks(self.pdf)
        self.assertEqual([(b["title"], b["level"], b["page"]) for b in bookmarks], [
            ("Título repetido", 1, 3), ("Título repetido", 1, 4), ("Última sección", 2, 4),
        ])

    def test_real_pdf_passes_converge_after_index_changes_page_count(self):
        calls = []

        def render(page_numbers):
            calls.append(page_numbers)
            writer = self.writer_with_pages(5)
            # Primera maquetación: el destino está en p3; al rellenar el índice,
            # este ocupa otra página. Cada PDF contiene su destino definitivo.
            writer.add_named_destination("/final", 2 if not page_numbers else 3)
            writer.write(self.pdf)
            return self.pdf

        pdf, pages, passes = navigation.stabilize_toc(render, self.entries[-1:])
        self.assertEqual((pages, passes), ({"final": 4}, 3))
        self.assertEqual(calls, [{}, {"final": 3}, {"final": 4}])
        navigation.validate_navigation(pdf, self.entries[-1:], pages)

    def test_updated_labels_keep_repeated_bookmark_destinations_and_hierarchy(self):
        from pypdf import PdfReader
        writer = self.writer_with_pages()
        writer.add_metadata({"/Title": "Documento"})
        writer.add_named_destination("/formula", 2)
        parent = writer.add_outline_item("Razón", 2)
        writer.add_outline_item("Razón", 3, parent=parent)
        writer.add_outline_item("Notas1", 3)
        writer.write(self.pdf)
        before = navigation.read_bookmarks(self.pdf)
        navigation.update_bookmark_labels(self.pdf, [
            {"native_title": "Razón", "title": "Razón (a)/(b)", "needs_update": True},
            {"native_title": "Razón", "title": "Razón (c)/(d)", "needs_update": True},
            {"native_title": "Notas1", "title": "Notas[1]", "needs_update": True},
        ])
        after = navigation.read_bookmarks(self.pdf)
        self.assertEqual([item["title"] for item in after],
                         ["Razón (a)/(b)", "Razón (c)/(d)", "Notas[1]"])
        self.assertEqual([{k: v for k, v in item.items() if k != "title"} for item in before],
                         [{k: v for k, v in item.items() if k != "title"} for item in after])
        self.assertEqual(navigation.resolve_toc_pages(self.pdf, [{"id": "formula"}]), {"formula": 3})
        with PdfReader(self.pdf) as reader:
            self.assertEqual(reader.metadata.title, "Documento")

    def test_label_mismatch_never_rewrites_the_pdf(self):
        writer = self.writer_with_pages()
        writer.add_outline_item("Real", 0)
        writer.write(self.pdf)
        original = self.pdf.read_bytes()
        with self.assertRaisesRegex(navigation.NavigationError, "no coinciden"):
            navigation.update_bookmark_labels(self.pdf, [
                {"native_title": "Otro", "title": "Otro (a)/(b)", "needs_update": True},
            ])
        self.assertEqual(self.pdf.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
