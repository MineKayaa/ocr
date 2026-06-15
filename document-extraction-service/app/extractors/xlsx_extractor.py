import io

from openpyxl import load_workbook

from app.extractors.base import BaseExtractor
from app.models.semantic import SemanticExtractionResult
from app.utils.text import clean_cell_value


class XlsxExtractor(BaseExtractor):
    supported_extensions = ["xlsx", "xls"]

    def extract(self, file_bytes: bytes, filename: str) -> SemanticExtractionResult:
        wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)

        blocks = []
        heading_stack: dict[int, str] = {}
        block_index = 0

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]

            # Sheet name as heading
            blocks.append(
                self._make_heading_block(block_index, sheet_name, 1, heading_stack, sheet_name=sheet_name)
            )
            block_index += 1

            # Read all rows
            all_rows: list[list[str]] = []
            for row in ws.iter_rows():
                cell_values = [clean_cell_value(cell.value) for cell in row]
                # Skip entirely empty rows
                if any(v for v in cell_values):
                    all_rows.append(cell_values)

            if not all_rows:
                continue

            headers = all_rows[0]
            data_rows = all_rows[1:]

            blocks.append(
                self._make_table_block(block_index, headers, data_rows, heading_stack, sheet_name=sheet_name)
            )
            block_index += 1

        wb.close()

        metadata = self._create_metadata(filename, title=wb.sheetnames[0] if wb.sheetnames else "")
        raw_content = self._build_raw_content(blocks)

        return SemanticExtractionResult(metadata=metadata, blocks=blocks, raw_content=raw_content)
