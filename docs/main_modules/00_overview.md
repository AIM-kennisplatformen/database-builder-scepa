# Main Modules

This page gives a quick tour of the main modules in `src/scepa_app`.

If you are reading the code for the first time, start with these entry points:

1. `src/scepa_app/main.py`
2. `src/scepa_app/settings.py`
3. `src/scepa_app/util/metadata_util.py`
4. `src/scepa_app/graph/graph_from_metadata.py`
5. `src/scepa_app/util/partial_sync.py`

## 1. Application flow

Start in `src/scepa_app/main.py`.

Look at these functions first:

- `main()` - runs the full pipeline
- `load_settings()` - reads required environment variables
- `connect_qdrant()` - creates the vector store connection
- `connect_typedb()` - creates the graph store connection
 - `build_zotero_source()` - connects to Zotero
 - `build_qdrant()` - creates the vector store connection
 - `build_typedb()` - creates the graph store connection
 - `build_pdf_source()` - configures PDF parsing and extraction
 - `store_vectors()` - stores chunks in Qdrant
 - `store_graph()` - stores nodes in TypeDB
 - `process_item()` - runs the legacy per-document pipeline
 - `dump_nodes()` and `load_nodes()` - serialize and replay graph nodes

## 2. Metadata handling

Look at `src/scepa_app/util/metadata_util.py` next.

The main functions are:

- `extract_zotero_metadata()` - extracts the Zotero fields used by the app
- `merge_zotero_into_content()` - overlays Zotero metadata onto parsed content
- `sanitize_metadata()` - removes HTML and empty values before storage
- `normalize_metadata()` - escapes metadata values for TypeQL storage

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

The current pipeline passes plain metadata dictionaries and `Content` objects between the helper layers.
The graph exporter converts those into nodes for storage.
