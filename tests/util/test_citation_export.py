import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, ".")
from scepa_app.util.citation_export import (
    _clean,
    _extract_year,
    _format_access_date,
    _format_authors,
    _make_key,
    _parse_people,
    _render_entry,
    zotero_to_bibtex,
)


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

def _journal_item(**overrides) -> dict:
    """Minimal valid journalArticle Zotero item."""
    data = {
        "key": "ABCD1234",
        "itemType": "journalArticle",
        "title": "Energy Poverty in Urban Areas",
        "creators": [
            {"creatorType": "author", "firstName": "Jane", "lastName": "Smith"},
            {"creatorType": "author", "firstName": "Bob", "lastName": "Jones"},
        ],
        "publicationTitle": "Energy Policy",
        "date": "2021-06-15",
        "volume": "12",
        "issue": "3",
        "pages": "100-115",
        "DOI": "",
        "url": "",
    }
    data.update(overrides)
    return {"data": data}


def _report_item(**overrides) -> dict:
    """Minimal valid report Zotero item."""
    data = {
        "key": "REPT1234",
        "itemType": "report",
        "title": "National Energy Outlook 2022",
        "creators": [
            {"creatorType": "author", "name": "Federal Energy Agency"},
        ],
        "institution": "Federal Energy Agency",
        "reportNumber": "TR-42",
        "place": "Washington, DC",
        "date": "2022",
        "DOI": "",
        "url": "",
    }
    data.update(overrides)
    return {"data": data}


def _thesis_item(**overrides) -> dict:
    """Minimal valid thesis Zotero item."""
    data = {
        "key": "THES1234",
        "itemType": "thesis",
        "title": "Deep Learning for Energy Forecasting",
        "creators": [
            {"creatorType": "author", "firstName": "Jane", "lastName": "Smith"},
        ],
        "university": "MIT",
        "place": "Cambridge, MA",
        "date": "2021",
        "DOI": "",
        "url": "",
    }
    data.update(overrides)
    return {"data": data}


def _book_item(**overrides) -> dict:
    data = {
        "key": "BOOK5678",
        "itemType": "book",
        "title": "Renewable Energy Systems",
        "creators": [
            {"creatorType": "author", "firstName": "Alice", "lastName": "Brown"},
        ],
        "publisher": "MIT Press",
        "place": "Cambridge, MA",
        "date": "2019",
        "ISBN": "978-0262035613",
        "DOI": "",
        "url": "",
    }
    data.update(overrides)
    return {"data": data}


def _conference_item(**overrides) -> dict:
    data = {
        "key": "CONF9012",
        "itemType": "conferencePaper",
        "title": "Smart Grid Optimisation",
        "creators": [
            {"creatorType": "author", "firstName": "Chris", "lastName": "Lee"},
        ],
        "proceedingsTitle": "Proc. IEEE Power & Energy Society General Meeting",
        "date": "2022",
        "pages": "1-8",
        "publisher": "IEEE",
        "place": "Denver, CO",
        "DOI": "",
        "url": "",
    }
    data.update(overrides)
    return {"data": data}


def _webpage_item(**overrides) -> dict:
    data = {
        "key": "WEB3456",
        "itemType": "webpage",
        "title": "UK Energy Strategy 2030",
        "creators": [],
        "date": "2023",
        "url": "https://gov.uk/energy-strategy",
        "accessDate": "2024-01-15T00:00:00Z",
        "publisher": "UK Government",
        "DOI": "",
    }
    data.update(overrides)
    return {"data": data}


# ─────────────────────────────────────────────────────────────────────
# Helper function tests
# ─────────────────────────────────────────────────────────────────────

class TestClean(unittest.TestCase):
    """Tests for _clean()"""

    def test_strips_leading_trailing_whitespace(self):
        self.assertEqual(_clean("  hello  "), "hello")

    def test_collapses_internal_whitespace(self):
        self.assertEqual(_clean("hello   world"), "hello world")

    def test_handles_newlines_and_tabs(self):
        self.assertEqual(_clean("hello\n\tworld"), "hello world")

    def test_empty_string(self):
        self.assertEqual(_clean(""), "")

    def test_non_string_coerced(self):
        self.assertEqual(_clean(42), "42")


class TestFormatAuthors(unittest.TestCase):
    """Tests for _format_authors()"""

    def test_single_author_string(self):
        self.assertEqual(_format_authors("Smith, John"), "Smith, John")

    def test_list_of_authors_joined_with_and(self):
        result = _format_authors(["Smith, John", "Doe, Alice"])
        self.assertEqual(result, "Smith, John and Doe, Alice")

    def test_empty_list(self):
        self.assertEqual(_format_authors([]), "")

    def test_list_filters_empty_strings(self):
        result = _format_authors(["Smith, John", "", "Doe, Alice"])
        self.assertEqual(result, "Smith, John and Doe, Alice")

    def test_single_item_list(self):
        self.assertEqual(_format_authors(["Smith, John"]), "Smith, John")


class TestMakeKey(unittest.TestCase):
    """Tests for _make_key()"""

    def test_extracts_first_word_and_year(self):
        self.assertEqual(_make_key("Energy Poverty Study", "2021"), "Energy2021")

    def test_strips_non_alpha_from_first_word(self):
        self.assertEqual(_make_key("123Energy Study", "2020"), "Energy2020")

    def test_empty_title_uses_unknown(self):
        self.assertEqual(_make_key("", "2021"), "Unknown2021")

    def test_int_year(self):
        self.assertEqual(_make_key("Climate Change", 2023), "Climate2023")


class TestRenderEntry(unittest.TestCase):
    """Tests for _render_entry()"""

    def test_produces_valid_bibtex_structure(self):
        result = _render_entry("article", "Smith2021", {"author": "Smith, J.", "year": "2021"})
        self.assertTrue(result.startswith("@article{Smith2021,"))
        self.assertTrue(result.endswith("}"))

    def test_skips_empty_fields(self):
        result = _render_entry("article", "Key", {"author": "Smith", "url": ""})
        self.assertNotIn("url", result)

    def test_last_field_has_no_trailing_comma(self):
        result = _render_entry("article", "Key", {"author": "Smith", "year": "2021"})
        lines = result.strip().split("\n")
        # Line before closing brace should not end with comma
        self.assertFalse(lines[-2].rstrip().endswith(","))

    def test_fields_are_padded_for_alignment(self):
        result = _render_entry("article", "Key", {"author": "Smith", "journal": "Nature", "year": "2021"})
        lines = result.split("\n")
        field_lines = [l for l in lines if " = {" in l]
        # All = signs should be at the same column
        eq_positions = [l.index("=") for l in field_lines]
        self.assertEqual(len(set(eq_positions)), 1)

    def test_all_empty_fields_produces_valid_bibtex(self):
        result = _render_entry("misc", "Key", {"author": "", "title": ""})
        self.assertTrue(result.startswith("@misc{Key,"))
        self.assertTrue(result.endswith("}"))
        # No field lines emitted — entry collapses to just opening line and closing brace.
        lines = result.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[1], "}")


class TestExtractYear(unittest.TestCase):
    """Tests for _extract_year()"""

    def test_extracts_year_from_iso_date(self):
        self.assertEqual(_extract_year("2021-06-15"), "2021")

    def test_extracts_year_from_partial_date(self):
        self.assertEqual(_extract_year("01/2011"), "2011")

    def test_extracts_year_from_year_only(self):
        self.assertEqual(_extract_year("2019"), "2019")

    def test_returns_empty_on_no_year(self):
        self.assertEqual(_extract_year(""), "")

    def test_returns_empty_on_none_like(self):
        self.assertEqual(_extract_year("no date here"), "")


class TestFormatAccessDate(unittest.TestCase):
    """Tests for _format_access_date()"""

    def test_formats_iso_datetime(self):
        self.assertEqual(_format_access_date("2024-01-15T00:00:00Z"), "Jan. 15, 2024")

    def test_returns_original_on_invalid(self):
        self.assertEqual(_format_access_date("not-a-date"), "not-a-date")

    def test_handles_timezone_offset(self):
        result = _format_access_date("2024-03-20T12:00:00+00:00")
        self.assertEqual(result, "Mar. 20, 2024")


class TestParsePeople(unittest.TestCase):
    """Tests for _parse_people()"""

    def test_parses_authors_last_first(self):
        creators = [{"creatorType": "author", "firstName": "Jane", "lastName": "Smith"}]
        self.assertEqual(_parse_people(creators, "author"), "Smith, Jane")

    def test_ignores_other_roles(self):
        creators = [
            {"creatorType": "author", "firstName": "Jane", "lastName": "Smith"},
            {"creatorType": "editor", "firstName": "Bob", "lastName": "Jones"},
        ]
        self.assertEqual(_parse_people(creators, "author"), "Smith, Jane")

    def test_multiple_authors_joined_with_and(self):
        creators = [
            {"creatorType": "author", "firstName": "Jane", "lastName": "Smith"},
            {"creatorType": "author", "firstName": "Bob", "lastName": "Jones"},
        ]
        result = _parse_people(creators, "author")
        self.assertEqual(result, "Smith, Jane and Jones, Bob")

    def test_organisation_name_field(self):
        creators = [{"creatorType": "author", "name": "The National Energy Action Research"}]
        result = _parse_people(creators, "author")
        self.assertEqual(result, "The National Energy Action Research")

    def test_last_name_only(self):
        creators = [{"creatorType": "author", "firstName": "", "lastName": "Smith"}]
        self.assertEqual(_parse_people(creators, "author"), "Smith")

    def test_empty_creators(self):
        self.assertEqual(_parse_people([], "author"), "")

    def test_parses_editors(self):
        creators = [{"creatorType": "editor", "firstName": "Ed", "lastName": "Itor"}]
        self.assertEqual(_parse_people(creators, "editor"), "Itor, Ed")


# ─────────────────────────────────────────────────────────────────────
# zotero_to_bibtex — item type dispatch
# ─────────────────────────────────────────────────────────────────────

class TestZoteroToBibtexArticle(unittest.TestCase):
    """Tests for journalArticle dispatch"""

    def test_produces_article_entry(self):
        result = zotero_to_bibtex(_journal_item())
        self.assertTrue(result.startswith("@article{"))

    def test_uses_zotero_key_as_citation_key(self):
        result = zotero_to_bibtex(_journal_item())
        self.assertIn("@article{ABCD1234,", result)

    def test_includes_author(self):
        result = zotero_to_bibtex(_journal_item())
        self.assertIn("Smith, Jane", result)
        self.assertIn("Jones, Bob", result)

    def test_multiple_authors_joined_with_and(self):
        result = zotero_to_bibtex(_journal_item())
        self.assertIn("Smith, Jane and Jones, Bob", result)

    def test_includes_title(self):
        result = zotero_to_bibtex(_journal_item())
        self.assertIn("Energy Poverty in Urban Areas", result)

    def test_includes_journal(self):
        result = zotero_to_bibtex(_journal_item())
        self.assertIn("Energy Policy", result)

    def test_includes_year(self):
        result = zotero_to_bibtex(_journal_item())
        self.assertIn("2021", result)

    def test_includes_volume_and_number(self):
        result = zotero_to_bibtex(_journal_item())
        self.assertIn("12", result)
        self.assertIn("3", result)

    def test_includes_pages(self):
        result = zotero_to_bibtex(_journal_item())
        self.assertIn("100-115", result)

    def test_preprint_dispatches_to_article(self):
        item = _journal_item(itemType="preprint")
        self.assertTrue(zotero_to_bibtex(item).startswith("@article{"))

    def test_omits_empty_url_field(self):
        result = zotero_to_bibtex(_journal_item(url=""))
        self.assertNotIn("url     =", result)


class TestZoteroToBibtexTechReport(unittest.TestCase):
    """Tests for report dispatch"""

    def test_produces_techreport_entry(self):
        result = zotero_to_bibtex(_report_item())
        self.assertTrue(result.startswith("@techreport{"))

    def test_includes_institution(self):
        result = zotero_to_bibtex(_report_item())
        self.assertIn("Federal Energy Agency", result)

    def test_includes_report_number(self):
        result = zotero_to_bibtex(_report_item())
        self.assertIn("TR-42", result)

    def test_includes_address(self):
        result = zotero_to_bibtex(_report_item())
        self.assertIn("Washington, DC", result)

    def test_does_not_include_journal_field(self):
        result = zotero_to_bibtex(_report_item())
        self.assertNotIn("journal", result)


class TestZoteroToBibtexPhdThesis(unittest.TestCase):
    """Tests for thesis dispatch"""

    def test_produces_phdthesis_entry(self):
        result = zotero_to_bibtex(_thesis_item())
        self.assertTrue(result.startswith("@phdthesis{"))

    def test_includes_school(self):
        result = zotero_to_bibtex(_thesis_item())
        self.assertIn("MIT", result)

    def test_includes_address(self):
        result = zotero_to_bibtex(_thesis_item())
        self.assertIn("Cambridge, MA", result)

    def test_does_not_include_journal_field(self):
        result = zotero_to_bibtex(_thesis_item())
        self.assertNotIn("journal", result)


class TestZoteroToBibtexBook(unittest.TestCase):
    """Tests for book dispatch"""

    def test_produces_book_entry(self):
        result = zotero_to_bibtex(_book_item())
        self.assertTrue(result.startswith("@book{"))

    def test_includes_publisher(self):
        result = zotero_to_bibtex(_book_item())
        self.assertIn("MIT Press", result)

    def test_includes_address(self):
        result = zotero_to_bibtex(_book_item())
        self.assertIn("Cambridge, MA", result)

    def test_includes_isbn(self):
        result = zotero_to_bibtex(_book_item())
        self.assertIn("978-0262035613", result)

    def test_book_section_dispatches_to_book(self):
        item = _book_item(itemType="bookSection")
        self.assertTrue(zotero_to_bibtex(item).startswith("@book{"))

    def test_editors_included(self):
        item = _book_item()
        item["data"]["creators"].append(
            {"creatorType": "editor", "firstName": "Ed", "lastName": "Itor"}
        )
        result = zotero_to_bibtex(item)
        self.assertIn("Itor, Ed", result)


class TestZoteroToBibtexInproceedings(unittest.TestCase):
    """Tests for conferencePaper dispatch"""

    def test_produces_inproceedings_entry(self):
        result = zotero_to_bibtex(_conference_item())
        self.assertTrue(result.startswith("@inproceedings{"))

    def test_includes_booktitle(self):
        result = zotero_to_bibtex(_conference_item())
        self.assertIn("Proc. IEEE Power & Energy Society General Meeting", result)

    def test_includes_pages(self):
        result = zotero_to_bibtex(_conference_item())
        self.assertIn("1-8", result)

    def test_includes_organization(self):
        result = zotero_to_bibtex(_conference_item())
        self.assertIn("IEEE", result)

    def test_falls_back_to_publication_title_if_no_proceedings_title(self):
        item = _conference_item()
        del item["data"]["proceedingsTitle"]
        item["data"]["publicationTitle"] = "IEEE Transactions"
        result = zotero_to_bibtex(item)
        self.assertIn("IEEE Transactions", result)


class TestZoteroToBibtexWebpage(unittest.TestCase):
    """Tests for webpage dispatch"""

    def test_produces_misc_entry(self):
        result = zotero_to_bibtex(_webpage_item())
        self.assertTrue(result.startswith("@misc{"))

    def test_includes_url_in_note(self):
        result = zotero_to_bibtex(_webpage_item())
        self.assertIn("[Online]. Available: https://gov.uk/energy-strategy", result)

    def test_includes_formatted_access_date(self):
        result = zotero_to_bibtex(_webpage_item())
        self.assertIn("Accessed: Jan. 15, 2024", result)

    def test_includes_organization(self):
        result = zotero_to_bibtex(_webpage_item())
        self.assertIn("UK Government", result)

    def test_blogpost_dispatches_to_misc(self):
        item = _webpage_item(itemType="blogPost")
        self.assertTrue(zotero_to_bibtex(item).startswith("@misc{"))

    def test_document_dispatches_to_misc(self):
        item = _webpage_item(itemType="document")
        self.assertTrue(zotero_to_bibtex(item).startswith("@misc{"))

    def test_missing_access_date_omits_accessed_line(self):
        item = _webpage_item(accessDate="")
        result = zotero_to_bibtex(item)
        self.assertNotIn("Accessed:", result)


class TestZoteroToBibtexFallback(unittest.TestCase):
    """Tests for unknown item type fallback"""

    def test_unknown_type_produces_misc(self):
        item = _journal_item(itemType="patent")
        self.assertTrue(zotero_to_bibtex(item).startswith("@misc{"))

    def test_missing_item_type_produces_misc(self):
        item = {"data": {"key": "X", "title": "Something", "creators": []}}
        self.assertTrue(zotero_to_bibtex(item).startswith("@misc{"))


# ─────────────────────────────────────────────────────────────────────
# zotero_to_bibtex — DOI fetch behaviour
# ─────────────────────────────────────────────────────────────────────

class TestZoteroToBibtexDoiFetch(unittest.TestCase):
    """Tests for DOI fetch behaviour"""

    @patch("scepa_app.util.citation_export._from_doi")
    def test_doi_fetch_used_when_present(self, mock_fetch):
        mock_fetch.return_value = "@article{Fetched2021, title={From DOI}}"
        item = _journal_item(DOI="10.1234/test")
        result = zotero_to_bibtex(item)
        mock_fetch.assert_called_once_with("10.1234/test")
        self.assertIn("From DOI", result)

    @patch("scepa_app.util.citation_export._from_doi")
    def test_falls_back_to_metadata_when_doi_fetch_fails(self, mock_fetch):
        mock_fetch.return_value = None
        item = _journal_item(DOI="10.1234/test")
        result = zotero_to_bibtex(item)
        self.assertTrue(result.startswith("@article{"))
        self.assertIn("Energy Poverty in Urban Areas", result)

    @patch("scepa_app.util.citation_export._from_doi")
    def test_doi_not_fetched_when_absent(self, mock_fetch):
        item = _journal_item(DOI="")
        zotero_to_bibtex(item)
        mock_fetch.assert_not_called()


# ─────────────────────────────────────────────────────────────────────
# zotero_to_bibtex — input format handling
# ─────────────────────────────────────────────────────────────────────

class TestZoteroToBibtexInputFormats(unittest.TestCase):
    """Tests for input dict format handling"""

    def test_accepts_full_zotero_api_response_with_data_key(self):
        item = _journal_item()
        self.assertIn("data", item)
        result = zotero_to_bibtex(item)
        self.assertTrue(result.startswith("@article{"))

    def test_accepts_unwrapped_data_dict(self):
        item = _journal_item()["data"]
        result = zotero_to_bibtex(item)
        self.assertTrue(result.startswith("@article{"))

    def test_uses_citation_key_field_if_no_key(self):
        item = _journal_item()
        del item["data"]["key"]
        item["data"]["citationKey"] = "MyCustomKey"
        result = zotero_to_bibtex(item)
        self.assertIn("@article{MyCustomKey,", result)

    def test_auto_generates_key_if_none_provided(self):
        item = _journal_item()
        del item["data"]["key"]
        result = zotero_to_bibtex(item)
        # Should fall back to first-word-of-title + year
        self.assertIn("@article{Energy2021,", result)

    def test_handles_missing_creators_gracefully(self):
        item = _journal_item()
        del item["data"]["creators"]
        result = zotero_to_bibtex(item)
        self.assertTrue(result.startswith("@article{"))

    def test_handles_organisation_author(self):
        """Organisations stored as a single 'name' field — as in the Heyman item."""
        item = _journal_item()
        item["data"]["creators"].append(
            {"creatorType": "author", "name": "The National Energy Action Research"}
        )
        result = zotero_to_bibtex(item)
        self.assertIn("The National Energy Action Research", result)


if __name__ == "__main__":
    unittest.main()