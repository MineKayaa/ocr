"""Legacy model matching C# DocumentExtractionResult with PascalCase field names."""

from pydantic import BaseModel, ConfigDict


class ExtractedPage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    PageNumber: int = 0
    Width: float = 0.0
    Height: float = 0.0
    Unit: str = ""


class ExtractedParagraph(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    Content: str = ""
    PageNumber: int = 0
    Role: str = ""


class ExtractedSection(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    SectionIndex: int = 0
    Title: str = ""
    StartPageNumber: int = 0
    EndPageNumber: int = 0
    Content: str = ""
    Paragraphs: list[ExtractedParagraph] = []


class ExtractedTable(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    TableIndex: int = 0
    StartPageNumber: int = 0
    EndPageNumber: int = 0
    RowCount: int = 0
    ColumnCount: int = 0
    Headers: list[str] = []
    Rows: list[list[str]] = []
    SectionContext: str = ""
    MarkdownContent: str = ""
    Caption: str = ""
    Footnotes: list[str] = []


class ExtractedKeyValuePair(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    Key: str = ""
    Value: str = ""
    PageNumber: int = 0
    Confidence: float = 0.0


class DocumentExtractionResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    RawContent: str = ""
    PageCount: int = 0
    Title: str = ""
    Languages: list[str] = []
    Pages: list[ExtractedPage] = []
    Tables: list[ExtractedTable] = []
    Sections: list[ExtractedSection] = []
    KeyValuePairs: list[ExtractedKeyValuePair] = []
