# Storage Layer

The storage flow is split between vector storage, graph storage, and node export.

Read these functions first:

- `store_vectors()` in `src/scepa_app/main.py` - writes embedded chunks to Qdrant
- `store_graph()` in `src/scepa_app/main.py` - writes nodes to TypeDB
- `MetadataNodeExporter.export()` in `src/scepa_app/graph/graph_from_metadata.py` - builds the nodes that are stored

Helpful support functions:

- `dump_nodes()` and `load_nodes()` in `src/scepa_app/main.py`
- `format_node()` and `print_nodes()` in `src/scepa_app/util/node_util.py`

Example flow:

```python
nodes = MetadataNodeExporter().export([metadata])
dump_nodes(nodes, settings.pdf_path / f"{item_key}_nodes.json")
store_graph(nodes, typedb)
```
