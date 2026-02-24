from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional, Dict, List

@dataclass
class ConvertRequest:
    pdf_path: str
    template_xlsx_path: str
    output_xlsx_path: str
    supplier_key: str
    options: Dict[str, Any]

@dataclass
class LineItem:
    product_number: str = ""
    product_name: str = ""
    customs_code: str = ""
    weight_g: str = ""
    delivered_qty: str = ""
    net_unit_price: str = ""
    total_price: str = ""

@dataclass
class ParseResult:
    header: Dict[str, Any]
    items: List[LineItem]
    warnings: List[str]
