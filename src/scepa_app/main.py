from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from database_builder_libs.sources.zotero_source import ZoteroSource
from dotenv import load_dotenv
load_dotenv()

LAST_SYNC_FILE = Path(".last_sync")
DOWNLOAD_DIR = Path("./downloads")



DEFAULT_SYNC_TIME = datetime(2025, 11, 21, 9, 4, 50, tzinfo=timezone.utc)

def load_last_sync() -> datetime:
    """Load last synchronization timestamp from disk."""
    if not LAST_SYNC_FILE.exists():
        return DEFAULT_SYNC_TIME

    return datetime.fromisoformat(LAST_SYNC_FILE.read_text().strip()).astimezone(
        timezone.utc
    )
def save_last_sync(ts: datetime) -> None:
    """Persist latest synchronization timestamp."""
    LAST_SYNC_FILE.write_text(ts.isoformat())


def build_config() -> dict:
    """Read Zotero credentials from environment variables."""
    return {
        "library_id": os.environ["ZOTERO_LIBRARY_ID"],
        "library_type": os.environ.get("ZOTERO_LIBRARY_TYPE", "group"),
        "api_key": os.environ["ZOTERO_API_KEY"],
        "collection": os.environ.get("ZOTERO_COLLECTION_ID"),
    }


def main() -> None:
    # Prepare directories
    DOWNLOAD_DIR.mkdir(exist_ok=True)

    # Load cursor
    last_synced = load_last_sync()
    print(f"Last sync: {last_synced}")

    # Connect source
    source = ZoteroSource()
    source.connect(build_config())

    # Discover changed items
    artefacts = source.get_list_artefacts(last_synced)
    print(f"Found {len(artefacts)} changed items")

    if not artefacts:
        print("Nothing to do.")
        return

    # Fetch metadata
    contents = source.get_content(artefacts)

    for content in contents:
        print("=" * 60)
        print(f"Item:      {content.id_}")
        print(f"Modified:  {content.date}")
        print(f"Title:     {content.content.get('title')}")
        print(f"Type:      {content.content.get('itemType')}")

    # Download attachments (example: first 5 items)
    print("\nDownloading attachments...")
    for item_key, _ in artefacts[:5]:
        source.download_zotero_item(
            item_id=item_key,
            download_path=str(DOWNLOAD_DIR),
        )

    # Update cursor
    newest = max(ts for _, ts in artefacts)
    save_last_sync(newest)

    print(f"\nSync complete. New cursor: {newest}")


if __name__ == "__main__":
    main()