from database_builder_libs.utility.embedding.vectorize_document import VectorizeDocument
from docling_core.types.doc import (
    DoclingDocument,
    SectionHeaderItem,
    TableItem,
    TextItem,
)
from pathlib import Path
from pandas import DataFrame
from typing import List, Tuple


class TextStructureExtractor:
    """Convert documents with Docling and extract structured sections."""

    def __init__(self) -> None:
        self._converter = VectorizeDocument()

    def convert(self, pdf_path: str) -> DoclingDocument:
        """Convert a PDF file into a DoclingDocument."""

        path = Path(pdf_path)

        with path.open("rb") as f:
            result = self._converter.vectorize(path.name, f)

        if not isinstance(result, DoclingDocument):
            raise RuntimeError(f"Docling conversion failed: {type(result)}")

        return result

    def extract_sections(
        self,
        doc: DoclingDocument,
    ) -> List[Tuple[str, str, List[DataFrame]]]:
        """Extract sections with their text content and tables."""

        sections: List[Tuple[str, str, List[DataFrame]]] = []

        current_title = ""
        buffer: List[str] = []
        tables: List[DataFrame] = []

        def flush():
            nonlocal buffer, tables

            if buffer:
                text = "\n".join(buffer).strip()

                if text:
                    sections.append((current_title, text, tables))

            buffer = []
            tables = []

        for nodeitem, _ in doc.iterate_items():

            match nodeitem:

                case SectionHeaderItem(text=text):
                    flush()
                    current_title = text.strip()

                case TextItem(text=text):
                    cleaned = text.strip()

                    if cleaned:
                        buffer.append(cleaned)

                case TableItem():
                    tables.append(nodeitem.export_to_dataframe(doc=doc))

        flush()
        return sections