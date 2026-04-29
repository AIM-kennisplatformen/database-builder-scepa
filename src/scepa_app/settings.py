from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel


class Settings(BaseModel):
    pdf_path: Path
    openai_host: str
    openai_key: str
    embedding_model: str
    typedb_uri: str
    typedb_database: str
    typedb_schema: str
    zotero_library_id: str
    zotero_api_key: str
    zotero_collection_id: str
    llm_model: str
    qdrant_url: str
    qdrant_collection: str
    qdrant_vector_size: int
    typedb_username: str
    typedb_password: str
    max_documents: int | None = None


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_settings() -> Settings:
    load_dotenv()

    max_documents = os.getenv("MAX_DOCUMENTS")

    return Settings.model_validate(
        {
            "pdf_path": Path(_required_env("PDF_PATH")),
            "openai_host": _required_env("OPENAI_HOST"),
            "openai_key": _required_env("OPENAI_API_KEY"),
            "embedding_model": _required_env("OPENAI_EMBEDDING_MODEL"),
            "typedb_uri": _required_env("TYPEDB_URI"),
            "typedb_database": _required_env("TYPEDB_DATABASE"),
            "typedb_schema": _required_env("TYPEDB_SCHEMA_PATH"),
            "zotero_library_id": _required_env("ZOTERO_LIBRARY_ID"),
            "zotero_api_key": _required_env("ZOTERO_API_KEY"),
            "zotero_collection_id": _required_env("ZOTERO_COLLECTION_ID"),
            "llm_model": _required_env("LLM_MODEL"),
            "qdrant_url": _required_env("QDRANT_URL"),
            "qdrant_collection": _required_env("QDRANT_COLLECTION"),
            "qdrant_vector_size": int(_required_env("QDRANT_VECTOR_SIZE")),
            "typedb_username": _required_env("TYPEDB_USERNAME"),
            "typedb_password": _required_env("TYPEDB_PASSWORD"),
            "max_documents": int(max_documents) if max_documents else None,
        }
    )
