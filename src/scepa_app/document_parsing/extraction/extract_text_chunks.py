from database_builder_libs.models.abstract_vector_store import Chunk
from typing import List


class TextChunkExtractor:

    def extract_chunks(
        self,
        sections,
        *,
        document_id: str,
    ) -> List[Chunk]:

        chunks: List[Chunk] = []

        for idx, (title, text, tables) in enumerate(sections):

            chunks.append(
                Chunk(
                    document_id=document_id,
                    chunk_index=idx,
                    text=text,
                    vector=[],
                    metadata={
                        "section_title": title,
                        "has_tables": bool(tables),
                    },
                )
            )

        return chunks