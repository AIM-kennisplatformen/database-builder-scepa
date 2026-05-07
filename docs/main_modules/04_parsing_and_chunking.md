# Parsing and Chunking

This module covers the Docling-based document parsing flow and the chunking strategies used to turn sections into `Chunk` objects.

## Document parsing examples

```python
from database_builder_scepa.utility.extract.document_parser_docling import (
    DocumentConversionError,
    DocumentParserDocling,
)

parser = DocumentParserDocling()

try:
    result = parser.parse("path/to/document.pdf")
except FileNotFoundError:
    print("File not found")
except ValueError as exc:
    print(f"Unsupported format: {exc}")
except DocumentConversionError as exc:
    for fault in exc.faults:
        print(f"Conversion failed: {fault.path_file_document} — {fault.faults}")
```

```python
from io import BytesIO
from database_builder_scepa.utility.extract.document_parser_docling import (
    DocumentConversionError,
    DocumentParserDocling,
)

parser = DocumentParserDocling()

with open("path/to/document.pdf", "rb") as f:
    stream = BytesIO(f.read())

try:
    result = parser.parse_stream(name="document.pdf", stream=stream)
except ValueError as exc:
    print(f"Unsupported format: {exc}")
except DocumentConversionError as exc:
    for fault in exc.faults:
        print(f"Conversion failed: {fault.path_file_document} — {fault.faults}")
```

### Working with the result

```python
for title, text, tables in result.sections:
    print(f"Section: '{title}'")
    print(f"  {len(text)} characters, {len(tables)} table(s)")

for table in result.tables:
    print(f"Table caption: '{table.caption}'")
    print(table.dataframe)

for figure in result.figures:
    print(f"Figure caption: '{figure.caption}'")

for block in result.code_blocks:
    print(f"[{block.section_title}] {block.text}")

for block in result.list_blocks:
    print(f"[{block.section_title}]")
    for item in block.items:
        print(f"  - {item}")

for footnote in result.footnotes:
    print(f"Footnote: {footnote.text}")

for entry in result.furniture:
    print(f"{entry.kind}: {entry.text}")

print(type(result.doc))  # <class 'docling_core.types.doc.DoclingDocument'>
```

### Supported formats

```python
supported_formats = [".csv", ".docx", ".html", ".md", ".pdf", ".pptx", ".xlsx"]
```

### Loading ML model artefacts from a local directory

```python
parser = DocumentParserDocling(path_dir_artifacts="/opt/docling/models")
result = parser.parse("path/to/document.pdf")
```

## Chunking strategies

Chunking strategies accept a list of `RawSection` tuples and return `Chunk` objects.

```python
sections = result.sections  # from DocumentParserDocling.parse / parse_stream
```

### Section chunking

```python
from database_builder_scepa.utility.chunk.n_points_section import SectionChunkingStrategy

strategy = SectionChunkingStrategy(
    min_chars=20,
    include_title_in_text=False,
)

chunks = strategy.chunk(sections, document_id="doc-001")
```

### Fixed-size chunking

```python
from database_builder_scepa.utility.chunk.n_points_fixed_size import FixedSizeChunkingStrategy

strategy = FixedSizeChunkingStrategy(
    chunk_size=500,
    min_chars=20,
)

chunks = strategy.chunk(sections, document_id="doc-001")
```

### Sliding-window chunking

```python
from database_builder_scepa.utility.chunk.n_points_sliding_window import SlidingWindowChunkingStrategy

strategy = SlidingWindowChunkingStrategy(
    chunk_size=500,
    overlap=100,
    min_chars=20,
)

chunks = strategy.chunk(sections, document_id="doc-001")
```

### Summary + sections chunking

```python
from database_builder_scepa.utility.chunk.summary_and_sections import SummaryAndSectionsStrategy

strategy = SummaryAndSectionsStrategy(min_chars=20)
chunks = strategy.chunk(sections, document_id="doc-001")
```

```python
summary_text = "This document covers the annual research results for 2024."
chunks = strategy.chunk(sections, document_id="doc-001", summary=summary_text)
```

### Common chunk fields

```python
chunk.document_id
chunk.chunk_index
chunk.text
chunk.vector
chunk.metadata
```
