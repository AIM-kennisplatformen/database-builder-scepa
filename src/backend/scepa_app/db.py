from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .settings import Settings

if TYPE_CHECKING:
    from database_builder_libs.stores.qdrant.qdrant_store import QdrantDatastore
    from database_builder_libs.stores.typedb.typedb_store import TypeDbDatastore

logger = logging.getLogger(__name__)

# The TypeDB entity and key attribute under which ingested documents are stored.
TEXTDOCUMENT_ENTITY = "textdocument"
HASH_KEY_ATTR = "hashvalue"


def _short_error(exc: Exception) -> str:
    """First meaningful line of an exception, for concise (non-traceback) logging."""
    text = str(exc).strip()
    first_line = text.splitlines()[0].strip() if text else ""
    return first_line or exc.__class__.__name__


def connect_typedb(settings: Settings, apply_schema: bool = True) -> TypeDbDatastore:
    """Connect to TypeDB.

    When ``apply_schema`` is True (the default) the schema is applied on connect,
    which is needed before writing. Read-only callers can pass ``apply_schema=False``
    to keep the connection lightweight (applying the schema reopens the driver).
    """
    from database_builder_libs.stores.typedb.typedb_store import TypeDbDatastore

    config: dict[str, object] = {
        "uri": settings.typedb_uri,
        "username": settings.typedb_username,
        "password": settings.typedb_password,
        "database": settings.typedb_database,
    }
    if apply_schema:
        config["schema_path"] = settings.typedb_schema

    typedb = TypeDbDatastore()
    typedb.connect(config)
    return typedb


def connect_qdrant(settings: Settings) -> QdrantDatastore:
    """Connect to the Qdrant vector store."""
    from database_builder_libs.stores.qdrant.qdrant_store import QdrantDatastore

    qdrant = QdrantDatastore()
    qdrant.connect(
        {
            "url": settings.qdrant_url,
            "collection": settings.qdrant_collection,
            "vector_size": settings.qdrant_vector_size,
        }
    )
    return qdrant


def disconnect_typedb(typedb: TypeDbDatastore | None) -> None:
    """Close the TypeDB driver if one is open. Safe to call with None."""
    if typedb is None:
        return
    try:
        if typedb.typedb_driver is not None:
            typedb.typedb_driver.close()
    except Exception:
        logger.warning("Failed to close TypeDB connection.", exc_info=True)


def disconnect_qdrant(qdrant: QdrantDatastore | None) -> None:
    """Close the Qdrant client if one is open. Safe to call with None."""
    if qdrant is None:
        return
    try:
        if qdrant.client is not None:
            qdrant.client.close()
    except Exception:
        logger.warning("Failed to close Qdrant connection.", exc_info=True)


def document_in_typedb(typedb: TypeDbDatastore | None, file_hash: str) -> bool:
    """Return True if a document with this content hash already exists in TypeDB."""
    if typedb is None:
        logger.info("TypeDB duplicate check skipped for %s (no connection).", file_hash)
        return False
    try:
        nodes = typedb.get_nodes(f"entity={TEXTDOCUMENT_ENTITY}&{HASH_KEY_ATTR}={file_hash}")
        found = len(nodes) > 0
        logger.info("TypeDB duplicate check for %s: %s.", file_hash, "found" if found else "not found")
        return found
    except Exception as e:
        logger.warning("TypeDB duplicate check failed for %s: %s. Treating as not present.", file_hash, _short_error(e))
        return False


def document_in_qdrant(qdrant: QdrantDatastore | None, file_hash: str) -> bool:
    """Return True if vectors for this content hash already exist in Qdrant.

    Chunks are stored with ``document_id`` set to the file content hash, so a
    non-empty result means the document was already ingested.
    """
    if qdrant is None:
        logger.info("Qdrant duplicate check skipped for %s (no connection).", file_hash)
        return False
    try:
        found = len(qdrant.get_document_chunks(file_hash)) > 0
        logger.info("Qdrant duplicate check for %s: %s.", file_hash, "found" if found else "not found")
        return found
    except Exception as e:
        logger.warning("Qdrant duplicate check failed for %s: %s. Treating as not present.", file_hash, _short_error(e))
        return False
