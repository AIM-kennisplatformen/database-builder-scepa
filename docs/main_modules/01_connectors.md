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

## Example flow

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

## PDF Source examples

### Minimal setup

```python
from database_builder_scepa.sources.pdf_source import PDFSource

src = PDFSource()
src.connect({"folder_path": "/data/papers"})
```

### Listing changed files

```python
from datetime import datetime, timezone

last_sync = datetime(2024, 1, 1, tzinfo=timezone.utc)
artefacts = src.get_list_artefacts(last_sync)

for relative_path, modified_at in artefacts:
    print(f"{relative_path}  —  last modified {modified_at}")
```

### Extracting content

```python
contents = src.get_content(artefacts)

for content in contents:
    meta = content.content["metadata"]
    print(f"File:    {content.content['file_name']}")
    print(f"Title:   {meta['title']}")
    print(f"Authors: {meta['authors']}")
    print(f"Source:  {meta['source']}")
    print(f"Chunks:  {len(content.content['chunks'])}")
    print("---")
```

### Enabling LLM extraction

```python
src = PDFSource()
src.connect({
    "folder_path":  "/data/papers",
    "llm_base_url": "http://localhost:11434/v1",
    "llm_api_key":  "ollama",
    "llm_model":    "gemma2:9b",
})
```

### Configuring extraction strategies per field

```python
from database_builder_scepa.sources.pdf_source import (
    PDFSource,
    FieldExtractionConfig,
    OrderedStrategyConfig,
    ExtractionStrategy,
)

src = PDFSource()
src.connect({
    "folder_path":  "/data/papers",
    "llm_base_url": "http://localhost:11434/v1",
    "llm_api_key":  "ollama",

    "title": FieldExtractionConfig(
        strategies=OrderedStrategyConfig(
            order=[ExtractionStrategy.LLM, ExtractionStrategy.DOCLING],
        )
    ),

    "authors": FieldExtractionConfig(
        strategies=OrderedStrategyConfig(
            order=[ExtractionStrategy.FILE_METADATA, ExtractionStrategy.LLM],
            stop_on_success=False,
        )
    ),

    "acknowledgements": FieldExtractionConfig(enabled=False),
})
```

### Skipping fields already known from an external source

```python
src = PDFSource()
src.connect({
    "folder_path": "/data/papers",
    "title":       FieldExtractionConfig(enabled=False),
    "authors":     FieldExtractionConfig(enabled=False),
})
```

```python
content = src.get_content(artefacts)[0]
meta    = content.content["metadata"]
source  = meta.get("source", {})

meta["title"]   = "Title from Zotero"
meta["authors"] = ["Author A", "Author B"]
source["title"]   = "zotero"
source["authors"] = "zotero"
meta["source"]  = source
```

### Adding chunking and embedding

```python
from database_builder_scepa.sources.pdf_source import SectionsConfig
from database_builder_scepa.utility.chunk.summary_and_sections import SummaryAndSectionsStrategy
from database_builder_scepa.utility.embed_chunk.openai_compatible import OpenAICompatibleChunkEmbedder

src = PDFSource()
src.connect({
    "folder_path": "/data/papers",
    "sections": SectionsConfig(
        chunking_strategy=SummaryAndSectionsStrategy(),
        embedder=OpenAICompatibleChunkEmbedder(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            model="nomic-embed-text",
        ),
    ),
})

contents = src.get_content(artefacts)
for content in contents:
    for chunk in content.content["chunks"]:
        print(chunk["chunk_index"], chunk["text"][:80])
```

```python
src.connect({
    "folder_path": "/data/papers",
    "sections": SectionsConfig(enabled=False),
})
```

### Quick inventory without parsing

```python
inventory = src.get_all_documents_metadata()

for item in inventory:
    print(f"{item['id']}  {item['size']} bytes  modified {item['modified']}")
    print(f"  pdf_meta: {item['pdf_meta']}")
```

```python
first_ten = src.get_all_documents_metadata(limit=10)
```
