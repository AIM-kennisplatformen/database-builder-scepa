# Connectors

The project currently wires together its main data sources in `src/scepa_app/main.py`.

The most useful functions to inspect first are:

- `load_settings()` - reads the connection settings from environment variables
- `main()` - connects to Zotero, downloads PDFs, and starts the processing pipeline
- `build_zotero_source()` - connects to Zotero
- `build_qdrant()` / `build_typedb()` - connect the storage backends
- `build_pdf_source()` - configures PDF extraction and chunking

For metadata handling, also read:

- `extract_zotero_metadata()` in `src/scepa_app/util/metadata_util.py`
- `merge_zotero_into_content()` in `src/scepa_app/util/metadata_util.py`
- `sanitize_metadata()` / `normalize_metadata()` in `src/scepa_app/util/metadata_util.py`

Example flow:

```python
settings = load_settings()

zot = ZoteroSource()
zot.connect({
    "library_id": settings.zotero_library_id,
    "library_type": "group",
    "api_key": settings.zotero_api_key,
})

metadata_items = zot.get_all_documents_metadata(
    collection_id=settings.zotero_collection_id
)
```
