# Storage Layer

The storage flow is split between vector storage, graph storage, and node export.

Read these functions first:

- `store_vectors()` in `src/scepa_app/main.py` - writes embedded chunks to Qdrant
- `store_graph()` in `src/scepa_app/main.py` - writes nodes to TypeDB
- `MetadataNodeExporter.export()` in `src/scepa_app/graph/graph_from_metadata.py` - builds the nodes that are stored

Helpful support functions:

- `dump_nodes()` and `load_nodes()` in `src/scepa_app/main.py`
- `format_node()` and `print_nodes()` in `src/scepa_app/util/node_util.py`

## Example flow

```python
nodes = MetadataNodeExporter().export([content])
dump_nodes(nodes, settings.pdf_path / f"{item_key}_nodes.json")
store_graph(nodes, typedb)
```

## Vector store examples (Qdrant)

### Connecting to Qdrant

```python
from database_builder_scepa.stores.qdrant.qdrant_store import QdrantDatastore
from database_builder_scepa.models.chunk import Chunk

qdrant_store = QdrantDatastore()
qdrant_store.connect({
    "url": "http://localhost:6333",
    "collection": "documents",
    "vector_size": 768,
})
```

### Storing document chunks

```python
chunks = [
    Chunk(
        document_id="doc1",
        chunk_index=0,
        text="This is the first chunk of document 1.",
        vector=[0.1, 0.2, ...],
        metadata={"page": 1, "section": "introduction"},
    ),
]

qdrant_store.store_chunks(chunks)
```

### Similarity search

```python
query_vector = [0.1, 0.2, ...]
results = qdrant_store.similarity_search(vector=query_vector, limit=5)

for chunk in results:
    print(f"Document: {chunk.document_id}")
    print(f"Chunk: {chunk.chunk_index}")
    print(f"Text: {chunk.text}")
```

## Graph store examples (TypeDB)

### Connecting to TypeDB

```python
from database_builder_scepa.stores.typedb_v2.typedb_v2_store import TypeDbDatastore
from database_builder_scepa.models.node import Node, NodeId, EntityType, KeyAttribute

typedb_store = TypeDbDatastore()
typedb_store.connect({
    "uri": "localhost:1729",
    "database": "knowledge_base",
    "schema_path": "schema.tql",
})
```

### Creating and storing nodes

```python
person_node = Node(
    id=NodeId("person:john_doe"),
    entity_type=EntityType("person"),
    key_attribute=KeyAttribute("email"),
    payload_data={
        "email": "john.doe@example.com",
        "name": "John Doe",
        "age": 30,
    },
    relations=[
        {"type": "works_for", "target": NodeId("organization:acme_corp")},
        {"type": "authored", "target": NodeId("document:report_2023")},
    ],
)

typedb_store.store_node(person_node)
```
