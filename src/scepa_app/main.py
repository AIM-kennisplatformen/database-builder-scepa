from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from .document_parsing.extraction.extract_text_chunks import TextChunkExtractor
from .document_parsing.extraction.extract_text_structure import TextStructureExtractor

from .document_parsing.embedding.embed_chunks import ChunkEmbedder
from .document_parsing.embedding.openai_embedding_model import OpenAICompatibleEmbeddingModel
from .document_parsing.extraction.extract_text_metadata import TextMetadataExtractor

load_dotenv()

LAST_SYNC_FILE = Path(".last_sync")
DOWNLOAD_DIR = Path("./downloads")

DEFAULT_SYNC_TIME = datetime(2025, 11, 21, 9, 4, 50, tzinfo=timezone.utc)


def load_last_sync() -> datetime:
    if not LAST_SYNC_FILE.exists():
        return DEFAULT_SYNC_TIME
    return datetime.fromisoformat(LAST_SYNC_FILE.read_text().strip()).astimezone(timezone.utc)


def save_last_sync(ts: datetime) -> None:
    LAST_SYNC_FILE.write_text(ts.isoformat())

def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

def main() -> None:
    pdf_path = Path(os.getenv("PDF_PATH", "PDF_INPUT/document.pdf"))
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path.resolve()}")

    structure_extractor = TextStructureExtractor()
    docling_doc = TextStructureExtractor._convert(self=structure_extractor, pdf_path=str(pdf_path))

    sections = structure_extractor._extract_sections(docling_doc)

    metadata_extractor = TextMetadataExtractor()
    metadata = metadata_extractor.extract(pdf_path=str(pdf_path), doc=docling_doc)

    chunk_extractor = TextChunkExtractor()
    chunks = chunk_extractor.extract_chunks(
        sections,
        document_id=os.getenv("DOCUMENT_ID", pdf_path.stem),
    )

    embedder = ChunkEmbedder(
        OpenAICompatibleEmbeddingModel(
            base_url=require_env("OPENAI_HOST"),
            api_key=require_env("OPENAI_API_KEY"),
            model=require_env("OPENAI_EMBEDDING_MODEL"),
        )
    )
    embedder.embed(chunks)
    print(len(chunks), "embedded chunks")

    # Print a concise summary
    print(f"Document metadata: {metadata}")
    print(f"Sections extracted: {len(sections)}")
    print(f"Chunks created:     {len(chunks)}")
    for c in chunks[:17]:
        print("-" * 60)
        print(f"chunk_index={c.chunk_index} section={c.metadata.get('section_title') if c.metadata else None}")
        print(c.text[:300].replace("\n", " ") + ("..." if len(c.text) > 300 else ""))


if __name__ == "__main__":
    main()