from datetime import datetime

from scepa_app.util.partial_sync import PartialSync


def test_partial_sync_uses_custom_db_path(tmp_path):
    db_path = tmp_path / "sync.db"

    sync = PartialSync(db_path=db_path)

    try:
        last_sync = sync.start_sync("Zotero")

        assert last_sync is None

        conflicts = sync.finish_sync(
            "Zotero",
            [("item-1", datetime.fromtimestamp(1))],
        )

        assert conflicts == []
    finally:
        sync.close()
