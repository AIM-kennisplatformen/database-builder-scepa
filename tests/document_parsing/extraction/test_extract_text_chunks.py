import pytest

from scepa_app.document_parsing.extraction.extract_text_chunks import TextChunkExtractor
from database_builder_libs.models.abstract_vector_store import Chunk


def test_extract_chunks_basic():
    extractor = TextChunkExtractor()

    sections = [
        ("Intro", "intro text", []),
        ("Methods", "methods text", ["table1"]),
    ]

    result = extractor.extract_chunks(
        sections,
        document_id="doc-123",
    )

    assert len(result) == 2

    # first chunk
    c0 = result[0]
    assert isinstance(c0, Chunk)
    assert c0.document_id == "doc-123"
    assert c0.chunk_index == 0
    assert c0.text == "intro text"
    assert c0.vector == []
    assert c0.metadata == {
        "section_title": "Intro",
        "has_tables": False,
    }

    # second chunk
    c1 = result[1]
    assert c1.document_id == "doc-123"
    assert c1.chunk_index == 1
    assert c1.text == "methods text"
    assert c1.metadata == {
        "section_title": "Methods",
        "has_tables": True,
    }


def test_extract_chunks_empty_sections():
    extractor = TextChunkExtractor()

    result = extractor.extract_chunks([], document_id="doc-123")

    assert result == []


def test_extract_chunks_preserves_order():
    extractor = TextChunkExtractor()

    sections = [
        ("A", "text A", []),
        ("B", "text B", []),
        ("C", "text C", []),
    ]

    result = extractor.extract_chunks(sections, document_id="doc")

    assert [c.chunk_index for c in result] == [0, 1, 2]
    assert [c.text for c in result] == ["text A", "text B", "text C"]