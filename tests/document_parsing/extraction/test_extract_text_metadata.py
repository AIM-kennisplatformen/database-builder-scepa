import json
from unittest.mock import Mock, patch

import pytest

from scepa_app.document_parsing.extraction.extract_text_metadata import (
    TextMetadataExtractor,
    TextMetadata,
    Acknowledgement,
)


class FakeDoc:
    def __init__(self, items):
        self.items = items

    def iterate_items(self):
        for item in self.items:
            yield item, None


class FakeHeader:
    def __init__(self, text):
        self.text = text


class FakeText:
    def __init__(self, text):
        self.text = text


PATCH_PATH = "scepa_app.document_parsing.extraction.extract_text_metadata"


def patch_docling():
    return patch(f"{PATCH_PATH}.SectionHeaderItem", FakeHeader), patch(
        f"{PATCH_PATH}.TextItem", FakeText
    )


# -------------------------------------------------
# Summary extraction
# -------------------------------------------------

def test_find_summary():

    with patch_docling()[0], patch_docling()[1]:

        doc = FakeDoc(
            [
                FakeHeader("Abstract"),
                FakeText("Line one."),
                FakeText("Line two."),
                FakeHeader("Introduction"),
            ]
        )

        extractor = TextMetadataExtractor()

        summary = extractor._find_summary(doc)

        assert summary == "Line one.\nLine two."


def test_first_section_header_used_as_title():

    with patch_docling()[0], patch_docling()[1]:

        doc = FakeDoc(
            [
                FakeHeader("A Very Interesting Paper"),
                FakeText("Some text"),
            ]
        )

        extractor = TextMetadataExtractor()

        assert extractor._first_section_header(doc) == "A Very Interesting Paper"


def test_title_heuristic_from_first_lines():

    with patch_docling()[0], patch_docling()[1]:

        doc = FakeDoc(
            [
                FakeText("A Very Interesting Paper Title"),
                FakeText("Author Name"),
            ]
        )

        extractor = TextMetadataExtractor()

        lines = extractor._first_lines(doc, limit=10)

        assert extractor._first_reasonable_line(lines) == "A Very Interesting Paper Title"


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

    authors, acknowledgements = extractor._extract_llm(["line"])

    assert authors == ["Alice Smith"]

    assert acknowledgements == [
        Acknowledgement(name="Bob", type="person", relation="review")
    ]


def test_extract_llm_handles_invalid_json():

    llm = Mock()

    response = Mock()
    response.choices = [Mock(message=Mock(content="not json"))]

    llm.chat.completions.create.return_value = response

    extractor = TextMetadataExtractor(llm_client=llm)

    authors, acknowledgements = extractor._extract_llm(["line"])

    assert authors is None
    assert acknowledgements == []


@patch(f"{PATCH_PATH}.PdfReader")
def test_fill_from_pdf_metadata(mock_reader):

    reader = Mock()
    reader.metadata = {"/Title": "PDF Title", "/Author": "Alice; Bob"}

    mock_reader.return_value = reader

    extractor = TextMetadataExtractor()

    meta = TextMetadata(source={})

    extractor._fill_from_pdf_metadata(meta, "file.pdf")

    assert meta.title == "PDF Title"
    assert meta.authors == ["Alice", "Bob"]
    assert meta.source["title"] == "pdf_metadata"
    assert meta.source["authors"] == "pdf_metadata"