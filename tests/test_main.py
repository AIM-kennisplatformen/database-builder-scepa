from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from database_builder_libs.models.node import EntityType, KeyAttribute, Node, NodeId


def _install_main_stubs() -> None:
    def _module(name: str) -> types.ModuleType:
        mod = types.ModuleType(name)
        sys.modules[name] = mod
        return mod

    typedb_store = _module("database_builder_libs.stores.typedb.typedb_store")
    qdrant_store = _module("database_builder_libs.stores.qdrant.qdrant_store")
    zotero_source = _module("database_builder_libs.sources.zotero_source")
    doc_parser = _module(
        "database_builder_libs.utility.extract.document_parser_docling"
    )
    chunk_strategy = _module(
        "database_builder_libs.utility.chunk.summary_and_sections"
    )
    embedder = _module(
        "database_builder_libs.utility.embed_chunk.openai_compatible"
    )

    class _TypeDbDatastore:
        def connect(self, *_args, **_kwargs):
            return None

        def store_node(self, *_args, **_kwargs):
            return None

        def get_nodes(self, *_args, **_kwargs):
            return []

    class _QdrantDatastore:
        def connect(self, *_args, **_kwargs):
            return None

        def store_chunks(self, *_args, **_kwargs):
            return None

    class _ZoteroSource:
        def connect(self, *_args, **_kwargs):
            return None

        def get_list_artefacts(self, *_args, **_kwargs):
            return []

        def get_all_documents_metadata(self, *_args, **_kwargs):
            return []

        def download_zotero_item(self, *_args, **_kwargs):
            return None

    class _DocumentParserDocling:
        def parse(self, *_args, **_kwargs):
            return SimpleNamespace(doc=SimpleNamespace(sections=[]))

    class _SummaryAndSectionsStrategy:
        def chunk(self, *_args, **_kwargs):
            return []

    class _OpenAICompatibleChunkEmbedder:
        def __init__(self, *_args, **_kwargs):
            pass

        def embed(self, chunks):
            return chunks

    setattr(typedb_store, "TypeDbDatastore", _TypeDbDatastore)
    setattr(qdrant_store, "QdrantDatastore", _QdrantDatastore)
    setattr(zotero_source, "ZoteroSource", _ZoteroSource)
    setattr(doc_parser, "DocumentParserDocling", _DocumentParserDocling)
    setattr(doc_parser, "ParsedDocument", SimpleNamespace)
    setattr(chunk_strategy, "SummaryAndSectionsStrategy", _SummaryAndSectionsStrategy)
    setattr(embedder, "OpenAICompatibleChunkEmbedder", _OpenAICompatibleChunkEmbedder)


def _load_main_module():
    _install_main_stubs()
    sys.modules.pop("scepa_app.main", None)
    return importlib.import_module("scepa_app.main")


def _settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        pdf_path=tmp_path,
        openai_host="http://openai.local",
        openai_key="secret",
        embedding_model="embed-model",
        llm_model="llm-model",
        qdrant_url="http://qdrant.local:6333",
        qdrant_collection="knowledge_base",
        qdrant_vector_size=4096,
        typedb_uri="typedb://localhost:1729",
        typedb_database="database",
        typedb_schema="/tmp/schema.tql",
        typedb_username="admin",
        typedb_password="password",
        zotero_library_id="123",
        zotero_api_key="zotero-secret",
        zotero_collection_id="collection",
        max_documents=1,
    )


def test_dump_and_load_nodes_roundtrip(tmp_path):
    main_module = _load_main_module()

    node = Node(
        id=NodeId("doc-1"),
        entity_type=EntityType("textdocument"),
        key_attribute=KeyAttribute("hashvalue"),
        payload_data={"namelike-title": "Title"},
        relations=(),
    )

    path = tmp_path / "nodes.json"

    main_module.dump_nodes([node], path)

    loaded = main_module.load_nodes(path)

    assert len(loaded) == 1
    assert loaded[0].id == node.id
    assert loaded[0].entity_type == node.entity_type
    assert loaded[0].payload_data == node.payload_data


def test_main_processes_only_configured_number_of_items(monkeypatch, tmp_path):
    main_module = _load_main_module()
    settings = _settings(tmp_path)

    zot = Mock()
    zot.get_list_artefacts.return_value = []
    zot.get_all_documents_metadata.return_value = [
        {"key": "item-1"},
        {"key": "item-2"},
    ]

    typedb = Mock()
    typedb.get_nodes.return_value = []

    qdrant = Mock()
    sync = Mock()
    sync.start_sync.return_value = None

    monkeypatch.setattr(main_module, "load_settings", lambda: settings)
    monkeypatch.setattr(main_module, "ZoteroSource", lambda: zot)
    monkeypatch.setattr(main_module, "PartialSync", lambda: sync)
    monkeypatch.setattr(main_module, "connect_qdrant", lambda _settings: qdrant)
    monkeypatch.setattr(main_module, "connect_typedb", lambda _settings: typedb)
    monkeypatch.setattr(main_module, "process_item", Mock())
    monkeypatch.setattr(main_module, "print_nodes", Mock())

    main_module.main()

    zot.connect.assert_called_once_with(
        {
            "library_id": settings.zotero_library_id,
            "library_type": "group",
            "api_key": settings.zotero_api_key,
        }
    )
    zot.get_all_documents_metadata.assert_called_once_with(
        collection_id=settings.zotero_collection_id
    )
    assert main_module.process_item.call_count == 1
    main_module.process_item.assert_called_once_with(
        {"key": "item-1"},
        settings,
        zot,
        qdrant,
        typedb,
    )
    typedb.get_nodes.assert_called_once_with("entity=textdocument&include=relations")
