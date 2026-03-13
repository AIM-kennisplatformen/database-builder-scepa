from __future__ import annotations

from typing import List

from database_builder_libs.models.abstract_vector_store import Chunk
from .openai_embedding_model import OpenAICompatibleEmbeddingModel


class ChunkEmbedder:
    """Embed a list of Chunk objects in batches."""

    def __init__(self, embedding_model: OpenAICompatibleEmbeddingModel) -> None:
        self._embedding_model = embedding_model

    def embed(self, chunks: List[Chunk]) -> List[Chunk]:
        """Return new Chunk objects with vectors populated."""

        texts = [c.text for c in chunks]
        vectors = self._embedding_model.embed_batch(texts)

        if len(vectors) != len(chunks):
            raise RuntimeError(
                f"Embedding batch size mismatch: got {len(vectors)} vectors for {len(chunks)} chunks."
            )

        embedded: List[Chunk] = []

        for c, v in zip(chunks, vectors):
            embedded.append(
                Chunk(
                    document_id=c.document_id,
                    chunk_index=c.chunk_index,
                    text=c.text,
                    vector=v,
                    metadata=c.metadata,
                )
            )

        return embedded