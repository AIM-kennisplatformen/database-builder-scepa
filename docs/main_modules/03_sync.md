# Sync System

The sync helper lives in `src/scepa_app/util/partial_sync.py`.

Start with these methods:

- `PartialSync.start_sync()` - reads the last recorded sync time
- `PartialSync.finish_sync()` - stores changed artifacts and updates the source timestamp
- `PartialSync.close()` - closes the SQLite connection

Internal logic worth knowing:

- `_init_db()` - creates the sync tables on first run
- `_find_conflicts()` - detects items that changed differently across sources

Example usage:

```python
from datetime import datetime

sync = PartialSync()
last_sync = sync.start_sync("Zotero")
last_sync_dt = datetime.fromtimestamp(last_sync) if last_sync is not None else None

artifacts = zot.get_list_artefacts(last_synced=last_sync_dt)
sync.finish_sync("Zotero", artifacts)
```
