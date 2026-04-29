from pathlib import Path

from scepa_app.settings import load_settings


def test_load_settings_reads_required_env(monkeypatch):
    monkeypatch.setattr("scepa_app.settings.load_dotenv", lambda *args, **kwargs: None)

    values = {
        "PDF_PATH": "/tmp/pdfs",
        "OPENAI_HOST": "http://openai.local",
        "OPENAI_API_KEY": "secret",
        "OPENAI_LLM_MODEL": "llm-model",
        "OPENAI_EMBEDDING_MODEL": "embed-model",
        "TYPEDB_URI": "typedb://localhost:1729",
        "TYPEDB_DATABASE": "database",
        "TYPEDB_SCHEMA_PATH": "/tmp/schema.tql",
        "ZOTERO_LIBRARY_ID": "123",
        "ZOTERO_API_KEY": "zotero-secret",
        "ZOTERO_COLLECTION_ID": "abc",
        "QDRANT_URI": "http://qdrant.local:6333",
        "QDRANT_COLLECTION": "knowledge_base",
        "EMBEDDING_VECTOR_SIZE": "4096",
        "TYPEDB_USER": "admin",
        "TYPEDB_PASSWORD": "password",
        "MAX_DOCUMENTS": "12",
    }

    for key, value in values.items():
        monkeypatch.setenv(key, value)

    settings = load_settings()

    assert settings.pdf_path == Path("/tmp/pdfs")
    assert settings.openai_host == "http://openai.local"
    assert settings.embedding_model == "embed-model"
    assert settings.llm_model == "llm-model"
    assert settings.qdrant_vector_size == 4096
    assert settings.max_documents == 12
