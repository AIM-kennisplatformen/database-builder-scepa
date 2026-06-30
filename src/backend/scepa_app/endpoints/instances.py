"""Instances endpoint — read existing TypeDB instances so the upload form can offer them for reuse."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING

from fastapi import APIRouter

from ..db import connect_typedb, disconnect_typedb
from ..settings import load_settings
from .models import ExistingInstances

if TYPE_CHECKING:
    from database_builder_libs.stores.typedb.typedb_store import TypeDbDatastore

router = APIRouter(prefix="/instances", tags=["instances"])
logger = logging.getLogger(__name__)

# TypeDB entities and attributes whose existing values the form offers for reuse.
# These mirror the nodes written by MetadataNodeExporter at ingestion time.
PERSON_ENTITY = "person"
PUBLISHING_INSTITUTION_ENTITY = "publishinginstitution"
INSTITUTION_NAME_ATTR = "namelike-name"
PERSON_FIRST_ATTR = "namelike-first"
PERSON_LAST_ATTR = "namelike-last"


def _person_display_name(payload: dict[str, object]) -> str:
    """Join a person's first and last name into a single display string."""
    parts = [payload.get(PERSON_FIRST_ATTR), payload.get(PERSON_LAST_ATTR)]
    return " ".join(str(part) for part in parts if part).strip()


def _distinct_sorted(values: Iterable[object]) -> list[str]:
    """Trim, drop blanks, deduplicate case-insensitively and sort alphabetically."""
    seen: dict[str, str] = {}
    for value in values:
        if isinstance(value, str) and value.strip():
            seen.setdefault(value.strip().casefold(), value.strip())
    return sorted(seen.values(), key=str.casefold)


@router.get(
    "",
    response_model=ExistingInstances,
    summary="List existing instances for reuse",
)
async def list_existing_instances() -> ExistingInstances:
    """Return distinct organization and author names already stored in TypeDB.

    Best-effort: if TypeDB is unavailable or the read fails, the lists come back
    empty so the form still works with plain free-text entry.
    """
    typedb: TypeDbDatastore | None = None
    try:
        typedb = connect_typedb(load_settings(), apply_schema=False)
    except Exception:
        logger.warning(
            "Could not connect to TypeDB; returning no existing instances.",
            exc_info=True,
        )
        return ExistingInstances()

    try:
        organizations = [
            node.payload_data.get(INSTITUTION_NAME_ATTR)
            for node in typedb.get_nodes(f"entity={PUBLISHING_INSTITUTION_ENTITY}")
        ]
        authors = [
            _person_display_name(dict(node.payload_data))
            for node in typedb.get_nodes(f"entity={PERSON_ENTITY}")
        ]
    except Exception:
        logger.warning("Failed to read existing instances from TypeDB.", exc_info=True)
        return ExistingInstances()
    finally:
        disconnect_typedb(typedb)

    return ExistingInstances(
        organizations=_distinct_sorted(organizations),
        authors=_distinct_sorted(authors),
    )
