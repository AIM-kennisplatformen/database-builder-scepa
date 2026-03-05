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

    def __init__(self) -> None:
        self._converter = VectorizeDocument()

    def extract(self, pdf_path: str) -> List[Tuple[str, str, List[DataFrame]]]:
        """
        Returns a list of tuples:
            (section_title, section_text, tables)
        """

        doc = self._convert(pdf_path)
        return self._extract_sections(doc)


    def _convert(self, pdf_path: str) -> DoclingDocument:
        path = Path(pdf_path)

        with path.open("rb") as f:
            result = self._converter.vectorize(path.name, f)

        if not isinstance(result, DoclingDocument):
            raise RuntimeError(f"Docling conversion failed: {type(result)}")

        return result

    def _extract_sections(
        self,
        doc: DoclingDocument,
    ) -> List[Tuple[str, str, List[DataFrame]]]:

        sections: List[Tuple[str, str, List[DataFrame]]] = []

        current_title = ""
        buffer = ""
        tables: List[DataFrame] = []

        def flush():
            nonlocal buffer, tables
            text = buffer.strip()
            if text:
                sections.append((current_title, text, tables))
            buffer = ""
            tables = []

        for nodeitem, _ in doc.iterate_items():

            match nodeitem:

                case SectionHeaderItem(text=text):
                    flush()
                    current_title = text.strip()

                case TextItem(text=text):
                    cleaned = text.strip()
                    if cleaned:
                        buffer += cleaned + "\n"

                case TableItem():
                    tables.append(nodeitem.export_to_dataframe())

        flush()
        return sections