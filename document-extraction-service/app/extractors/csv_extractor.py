import io

import pandas as pd

from app.extractors.base import BaseExtractor
from app.models.semantic import SemanticExtractionResult


class CsvExtractor(BaseExtractor):
    supported_extensions = ["csv", "tsv"]

    def extract(self, file_bytes: bytes, filename: str) -> SemanticExtractionResult:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "csv"
        sep = "\t" if ext == "tsv" else ","

        df = pd.read_csv(io.BytesIO(file_bytes), sep=sep, dtype=str, keep_default_na=False)

        headers = list(df.columns)
        rows = [list(row) for row in df.values]

        blocks = []
        heading_stack: dict[int, str] = {}

        blocks.append(self._make_table_block(0, headers, rows, heading_stack))

        metadata = self._create_metadata(filename)
        raw_content = self._build_raw_content(blocks)

        return SemanticExtractionResult(metadata=metadata, blocks=blocks, raw_content=raw_content)
