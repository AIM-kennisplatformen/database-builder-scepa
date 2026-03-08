import json
from unittest.mock import Mock, patch

import pytest
from docling_core.types.doc import SectionHeaderItem, TextItem

from scepa_app.document_parsing.extraction.extract_text_metadata import (
    TextMetadataExtractor,
    Institution,
    Acknowledgement,
)


# -------------------------------------------------
# Helpers
# -------------------------------------------------

class FakeNode:
    def __init__(self, text):
        self.text = text


class FakeDoc:
    def __init__(self, items):
        self.items = items

    def iterate_items(self):
        for i in self.items:
            yield i, None

class FakeSectionHeader(SectionHeaderItem):
    def __init__(self, text):
        self.text = text


class FakeText(TextItem):
    def __init__(self, text):
        self.text = text

# -------------------------------------------------
# Summary extraction
# -------------------------------------------------
def test_find_summary():

    class FakeHeader:
        def __init__(self, text):
            self.text = text

    class FakeText:
        def __init__(self, text):
            self.text = text

    class FakeDoc:
        def __init__(self, items):
            self.items = items

        def iterate_items(self):
            for i in self.items:
                yield i, None

    with patch(
        "scepa_app.document_parsing.extraction.extract_text_metadata.SectionHeaderItem",
        FakeHeader,
    ), patch(
        "scepa_app.document_parsing.extraction.extract_text_metadata.TextItem",
        FakeText,
    ):

        doc = FakeDoc([
            FakeHeader("Abstract"),
            FakeText("Line one."),
            FakeText("Line two."),
            FakeHeader("Introduction"),
        ])

        extractor = TextMetadataExtractor()

        summary = extractor._find_summary(doc)

        assert summary == "Line one.\nLine two."
# -------------------------------------------------
# Title heuristics
# -------------------------------------------------

def test_first_section_header_used_as_title():

    class FakeHeader:
        def __init__(self, text):
            self.text = text

    class FakeText:
        def __init__(self, text):
            self.text = text

    class FakeDoc:
        def __init__(self, items):
            self.items = items

        def iterate_items(self):
            for i in self.items:
                yield i, None

    with patch(
        "scepa_app.document_parsing.extraction.extract_text_metadata.SectionHeaderItem",
        FakeHeader,
    ), patch(
        "scepa_app.document_parsing.extraction.extract_text_metadata.TextItem",
        FakeText,
    ):

        doc = FakeDoc([
            FakeHeader("A Very Interesting Paper"),
            FakeText("Some text"),
        ])

        extractor = TextMetadataExtractor()

        title = extractor._first_section_header(doc)

        assert title == "A Very Interesting Paper"

def test_title_heuristic_from_first_lines():

    class FakeHeader:
        def __init__(self, text):
            self.text = text

    class FakeText:
        def __init__(self, text):
            self.text = text

    class FakeDoc:
        def __init__(self, items):
            self.items = items

        def iterate_items(self):
            for i in self.items:
                yield i, None

    with patch(
        "scepa_app.document_parsing.extraction.extract_text_metadata.SectionHeaderItem",
        FakeHeader,
    ), patch(
        "scepa_app.document_parsing.extraction.extract_text_metadata.TextItem",
        FakeText,
    ):

        doc = FakeDoc([
            FakeText("A Very Interesting Paper Title"),
            FakeText("Author Name"),
        ])

        extractor = TextMetadataExtractor()

        lines = extractor._first_lines(doc, limit=10)

        title = extractor._first_reasonable_line(lines)

        assert title == "A Very Interesting Paper Title"

# -------------------------------------------------
# Author splitting
# -------------------------------------------------

@pytest.mark.parametrize(
    "value,expected",
    [
        ("Alice; Bob", ["Alice", "Bob"]),
        ("Alice and Bob", ["Alice", "Bob"]),
        ("Alice", ["Alice"]),
    ],
)
def test_split_authors(value, expected):

    extractor = TextMetadataExtractor()

    assert extractor._split_authors(value) == expected


# -------------------------------------------------
# LLM extraction
# -------------------------------------------------

def test_extract_llm_parses_json():

    llm = Mock()

    response = Mock()
    response.choices = [
        Mock(
            message=Mock(
                content=json.dumps(
                    {
                        "authors": ["Alice Smith"],
                        "institutions": [
                            {"name": "MIT", "parent": None}
                        ],
                        "acknowledgements": [
                            {
                                "name": "Bob",
                                "type": "person",
                                "relation": "review",
                            }
                        ],
                    }
                )
            )
        )
    ]

    llm.chat.completions.create.return_value = response

    extractor = TextMetadataExtractor(llm_client=llm)

    authors, institutions, acknowledgements = extractor._extract_llm(["line"])

    assert authors == ["Alice Smith"]

    assert institutions == [
        Institution(name="MIT", parent=None)
    ]

    assert acknowledgements == [
        Acknowledgement(name="Bob", type="person", relation="review")
    ]


def test_extract_llm_handles_invalid_json():

    llm = Mock()

    response = Mock()
    response.choices = [Mock(message=Mock(content="not json"))]

    llm.chat.completions.create.return_value = response

    extractor = TextMetadataExtractor(llm_client=llm)

    authors, institutions, acknowledgements = extractor._extract_llm(["line"])

    assert authors is None
    assert institutions is None
    assert acknowledgements == []


# -------------------------------------------------
# PDF metadata extraction
# -------------------------------------------------

@patch("scepa_app.document_parsing.extraction.extract_text_metadata.PdfReader")
def test_fill_from_pdf_metadata(mock_reader):

    reader = Mock()
    reader.metadata = {"/Title": "PDF Title", "/Author": "Alice; Bob"}

    mock_reader.return_value = reader

    extractor = TextMetadataExtractor()

    from scepa_app.document_parsing.extraction.extract_text_metadata import TextMetadata

    meta = TextMetadata()

    extractor._fill_from_pdf_metadata(meta, "file.pdf")

    assert meta.title == "PDF Title"
    assert meta.authors == ["Alice", "Bob"]
    assert meta.source["title"] == "pdf_metadata"
    assert meta.source["authors"] == "pdf_metadata"