from __future__ import annotations
import re
from typing import Dict, Any, List
from .base import SupplierParser
from ..types import ParseResult, LineItem
from ..utils import normalize_ws, money_to_str


class OmniaParser(SupplierParser):
    supplier_key = "omnia"
    display_name = "Omnia (enterprise invoice layout)"

    row_pattern = re.compile(
        r"^(?P<code>[A-Z0-9\-]{3,})\s+"
        r"(?P<desc>.+?)\s+"
        r"(?P<qty>\d+)\s+PZ\s+"
        r"(?P<price>\d+(?:[.,]\d+)?)\s+€\s+"
        r"(?P<total>\d+(?:[.,]\d+)?)\s+€?$"
    )

    def can_parse(self, pdf_text_pages: List[str], tables: list) -> bool:
        text = "\n".join(pdf_text_pages).lower()
        return "omniacomponents" in text or "26vin" in text

    def parse(self, pdf_text_pages: List[str], tables: list, options: Dict[str, Any]) -> ParseResult:
        lines = []
        for page in pdf_text_pages:
            for l in (page or "").splitlines():
                l = normalize_ws(l)
                if l:
                    lines.append(l)

        items: List[LineItem] = []
        warnings: List[str] = []

        in_table = False
        pending_desc = None

        for line in lines:

            if "PRODUCT CODE" in line and "DESCRIPTION" in line:
                in_table = True
                continue

            if not in_table:
                continue

            if line.startswith("TOTALE") or line.startswith("IMPONIBILE"):
                break

            m = self.row_pattern.match(line)
            if m:
                code = m.group("code")
                desc = m.group("desc")
                qty = m.group("qty")
                price = money_to_str(m.group("price"))
                total = money_to_str(m.group("total"))

                item = LineItem(
                    product_number=code,
                    product_name=desc,
                    delivered_qty=qty,
                    net_unit_price=price,
                    total_price=total,
                    customs_code="",
                    weight_g=""
                )
                items.append(item)
                continue

            # zachytí případy kdy je popis na řádku nad tím
            if re.search(r"\d+\s+PZ\s+\d", line):
                parts = line.split()
                if len(parts) >= 5:
                    code = parts[0]
                    qty = parts[-5]
                    price = money_to_str(parts[-3])
                    total = money_to_str(parts[-1])

                    desc = " ".join(parts[1:-5])

                    item = LineItem(
                        product_number=code,
                        product_name=desc,
                        delivered_qty=qty,
                        net_unit_price=price,
                        total_price=total,
                        customs_code="",
                        weight_g=""
                    )
                    items.append(item)

        if not items:
            warnings.append("OmniaParser: Nenalezeny žádné položky.")

        return ParseResult(
            header={"supplier": "omnia"},
            items=items,
            warnings=warnings
        )


def create() -> OmniaParser:
    return OmniaParser()
