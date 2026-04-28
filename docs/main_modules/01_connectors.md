# Connectors

The project currently wires together its main data sources in `src/scepa_app/main.py`.

The most useful functions to inspect first are:

- `load_config()` - reads the connection settings from environment variables
- `main()` - connects to Zotero, downloads PDFs, and starts the processing pipeline
- `extract_metadata()` - combines Zotero metadata with document-level extraction

For source-specific metadata, also read:

- `ZoteroMetadataExtractor.extract()` in `src/scepa_app/document_parsing/extract_text_metadata_zotero.py`
- `TextMetadataExtractor.extract()` in `src/scepa_app/document_parsing/extract_text_metadata.py`

Example flow:

```python
config = load_config()

zot = ZoteroSource()
zot.connect({
    "library_id": config["zotero_library_id"],
    "library_type": "group",
    "api_key": config["zotero_api_key"],
})

metadata_items = zot.get_all_documents_metadata(
    collection_id=config["zotero_collection_id"]
)
```
