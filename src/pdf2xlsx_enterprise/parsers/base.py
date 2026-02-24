from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any
from ..types import ParseResult

class SupplierParser(ABC):
    supplier_key: str
    display_name: str

    @abstractmethod
    def can_parse(self, pdf_text_pages: list[str], tables: list[list[list[str]]]) -> bool:
        ...

    @abstractmethod
    def parse(self, pdf_text_pages: list[str], tables: list[list[list[str]]], options: Dict[str, Any]) -> ParseResult:
        ...
