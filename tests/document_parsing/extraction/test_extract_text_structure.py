import pytest
from unittest.mock import Mock, patch
from pandas import DataFrame

from scepa_app.document_parsing.extraction.extract_text_structure import (
    TextStructureExtractor,
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


class FakeTable:
    def __init__(self, df):
        self.df = df

    def export_to_dataframe(self, *args, **kwargs):
        return self.df

@patch("scepa_app.document_parsing.extraction.extract_text_structure.VectorizeDocument")
def test_convert_success(mock_vectorize, tmp_path):

    fake_doc = Mock()
    mock_vectorize.return_value.vectorize.return_value = fake_doc

    extractor = TextStructureExtractor()

    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"pdf")

    with patch(
        "scepa_app.document_parsing.extraction.extract_text_structure.DoclingDocument",
        type(fake_doc),
    ):
        result = extractor.convert(str(pdf))

    assert result == fake_doc


@patch("scepa_app.document_parsing.extraction.extract_text_structure.VectorizeDocument")
def test_convert_raises_if_wrong_type(mock_vectorize, tmp_path):

    mock_vectorize.return_value.vectorize.return_value = "not_doc"

    extractor = TextStructureExtractor()

    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"pdf")

    with pytest.raises(RuntimeError):
        extractor.convert(str(pdf))


# -------------------------------------------------
# extract_sections()
# -------------------------------------------------

def test_extract_sections_basic():

    df = DataFrame({"a": [1]})

    with patch(
        "scepa_app.document_parsing.extraction.extract_text_structure.SectionHeaderItem",
        FakeHeader,
    ), patch(
        "scepa_app.document_parsing.extraction.extract_text_structure.TextItem",
        FakeText,
    ), patch(
        "scepa_app.document_parsing.extraction.extract_text_structure.TableItem",
        FakeTable,
    ):

        doc = FakeDoc(
            [
                FakeHeader("Intro"),
                FakeText("Line one"),
                FakeText("Line two"),
                FakeTable(df),
                FakeHeader("Methods"),
                FakeText("Method text"),
            ]
        )

        extractor = TextStructureExtractor()

        sections = extractor.extract_sections(doc)

        assert len(sections) == 2

        title1, text1, tables1 = sections[0]
        assert title1 == "Intro"
        assert text1 == "Line one\nLine two"
        assert len(tables1) == 1

        title2, text2, tables2 = sections[1]
        assert title2 == "Methods"
        assert text2 == "Method text"
        assert tables2 == []


def test_extract_sections_text_without_header():

    with patch(
        "scepa_app.document_parsing.extraction.extract_text_structure.TextItem",
        FakeText,
    ):

        doc = FakeDoc(
            [
                FakeText("First line"),
                FakeText("Second line"),
            ]
        )

        extractor = TextStructureExtractor()

        sections = extractor.extract_sections(doc)

        assert len(sections) == 1

        title, text, tables = sections[0]

        assert title == ""
        assert text == "First line\nSecond line"
        assert tables == []


def test_extract_sections_empty_doc():

    doc = FakeDoc([])

    extractor = TextStructureExtractor()

    sections = extractor.extract_sections(doc)

    assert sections == []