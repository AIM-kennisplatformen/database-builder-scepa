import pytest
from unittest.mock import Mock

from scepa_app.document_parsing.embedding.embed_chunks import ChunkEmbedder
from database_builder_libs.models.abstract_vector_store import Chunk


def make_chunk(i: int) -> Chunk:
    return Chunk(
        document_id="doc1",
        chunk_index=i,
        text=f"text-{i}",
        vector=None,
        metadata={"k": i},
    )


def test_embed_returns_new_chunks_with_vectors():
    # Arrange
    chunks = [make_chunk(0), make_chunk(1)]
    mock_model = Mock()
    mock_model.embed_batch.return_value = [
        [0.1, 0.2],
        [0.3, 0.4],
    ]

    embedder = ChunkEmbedder(mock_model)

    # Act
    result = embedder.embed(chunks)

    # Assert
    mock_model.embed_batch.assert_called_once_with(["text-0", "text-1"])

    assert len(result) == 2

    for i, chunk in enumerate(result):
        assert chunk.document_id == chunks[i].document_id
        assert chunk.chunk_index == chunks[i].chunk_index
        assert chunk.text == chunks[i].text
        assert chunk.metadata == chunks[i].metadata
        assert chunk.vector == mock_model.embed_batch.return_value[i]

        # ensure new object returned
        assert chunk is not chunks[i]


def test_embed_raises_if_vector_count_mismatch():
    # Arrange
    chunks = [make_chunk(0), make_chunk(1)]
    mock_model = Mock()
    mock_model.embed_batch.return_value = [[0.1, 0.2]]  # only 1 vector

    embedder = ChunkEmbedder(mock_model)

    # Act / Assert
    with pytest.raises(RuntimeError, match="Embedding batch size mismatch"):
        embedder.embed(chunks)