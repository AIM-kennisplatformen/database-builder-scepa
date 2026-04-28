# Main Modules

This page gives a quick tour of the main modules in `src/scepa_app`.

If you are reading the code for the first time, start with these entry points:

1. `src/scepa_app/main.py`
2. `src/scepa_app/document_parsing/extract_text_metadata.py`
3. `src/scepa_app/document_parsing/extract_text_metadata_zotero.py`
4. `src/scepa_app/graph/graph_from_metadata.py`
5. `src/scepa_app/util/partial_sync.py`

## 1. Application flow

Start in `src/scepa_app/main.py`.

Look at these functions first:

- `main()` - runs the full pipeline
- `load_config()` - reads required environment variables
- `parse_document()` - converts a PDF into a parsed document
- `extract_metadata()` - combines Zotero data and document heuristics
- `extract_chunks()` - creates chunks from parsed sections
- `embed_chunks()` - adds vectors to the chunks
- `store_vectors()` - stores chunks in Qdrant
- `store_graph()` - stores nodes in TypeDB
- `dump_nodes()` and `load_nodes()` - serialize and replay graph nodes
- `replay_nodes()` - loads dumped nodes and writes them to TypeDB

## 2. Metadata extraction

Look at `src/scepa_app/document_parsing/extract_text_metadata.py` next.

The main method is:

- `TextMetadataExtractor.extract()` - builds a `TextMetadata` object from a parsed document

Helpful methods to read alongside it:

- `_fill_from_pdf_metadata()` - uses embedded PDF metadata
- `_extract_llm()` - optional LLM-based extraction for authors and acknowledgements
- `_find_summary()` - finds the abstract or summary section
- `parse_author_line()` - parses simple author lines from headers
- `_first_lines()`, `_first_section_header()`, `_first_reasonable_line()` - title heuristics

## 3. Zotero metadata

Look at `src/scepa_app/document_parsing/extract_text_metadata_zotero.py`.

The main method is:

- `ZoteroMetadataExtractor.extract()` - converts a Zotero entry into `TextMetadata`

Helpful methods to read alongside it:

- `_extract_authors()` - filters Zotero creators down to personal authors
- `_extract_keywords()` - splits tags into keywords and structured tag groups
- `_is_institution_name()` - removes institutional authors

## 4. Metadata to graph

Look at `src/scepa_app/graph/graph_from_metadata.py`.

The main method is:

- `MetadataNodeExporter.export()` - turns `TextMetadata` objects into graph nodes

Helpful methods to read alongside it:

- `_hash()` - creates a stable document hash
- `_person_key()` - normalizes author names into a key
- `_person_node()` - builds person nodes
- `_institution_node()` - builds institution nodes
- `_is_noise()` - filters acknowledgements that should not become entities

## 5. Sync tracking

Look at `src/scepa_app/util/partial_sync.py`.

The main methods are:

- `PartialSync.start_sync()` - gets the last sync timestamp for a source
- `PartialSync.finish_sync()` - stores new artifacts and closes the sync cycle
- `PartialSync.close()` - closes the database connection

Helpful internal method:

- `_find_conflicts()` - finds items whose modification times differ across sources

## 6. Node formatting

Look at `src/scepa_app/util/node_util.py`.

The main methods are:

- `format_node()` - renders a node as readable text
- `print_nodes()` - prints a list of nodes

## 7. Data models

Look at `src/scepa_app/document_parsing/text_metadata.py`.

The core dataclasses are:

- `TextMetadata`
- `Acknowledgement`
- `Institution`

These are the objects passed between the metadata extraction and graph export steps.
