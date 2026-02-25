from __future__ import annotations
import re
from typing import Dict, Any, List

from .base import SupplierParser
from ..types import ParseResult, LineItem
from ..utils import normalize_ws


def clean_number(s: str) -> str:
    s = re.sub(r"[^0-9,\.]", "", s)
    return s.replace(",", ".")


CODE_TOKEN = re.compile(r"^[A-Z0-9][A-Z0-9\-\./]{2,}$")   # dovolí i tečky (161.167) a pomlčky
PREFIX_ONLY = re.compile(r"^[A-Z]{2,8}-$")                # VEN-
SUFFIX_DOTS = re.compile(r"^\d+(?:\.\d+)+$")              # 161.167
NUMS_LINE = re.compile(r"(\d+)\s+PZ\s+([\d.,]+)\s*€\s+([\d.,]+)\s*€")


class OmniaParser(SupplierParser):
    supplier_key = "omnia"
    display_name = "Omnia (enterprise robust)"

    def can_parse(self, pdf_text_pages: List[str], tables: list) -> bool:
        text = "\n".join(pdf_text_pages).lower()
        return ("omniacomponents" in text) or ("26vin" in text) or ("invoice" in text)

    def parse(self, pdf_text_pages: List[str], tables: list, options: Dict[str, Any]) -> ParseResult:
    # 1) připrav řádky
    lines: List[str] = []
    for page in pdf_text_pages:
        for l in (page or "").splitlines():
            l = normalize_ws(l)
            if l:
                lines.append(l)

    items: List[LineItem] = []
    warnings: List[str] = []

    # 2) regex pro celý řádek položky:
    #    CODE  DESCRIPTION ...  100 PZ  1.15 €  115.00 €
    row_re = re.compile(
        r"^(?P<code>[A-Z0-9][A-Z0-9\-\./]{2,})\s+"
        r"(?P<desc>.+?)\s+"
        r"(?P<qty>\d+)\s+PZ\s+"
        r"(?P<price>[\d.,]+)\s*€\s+"
        r"(?P<total>[\d.,]+)\s*€?\s*$"
    )

    prefix_only = re.compile(r"^[A-Z]{2,8}-$")  # VEN-

    pending_prefix: str | None = None
    buffer = ""

    def clean_number(s: str) -> str:
        s = re.sub(r"[^0-9,\.]", "", s)
        return s.replace(",", ".")

    for line in lines:
        # VEN- na samostatném řádku
        if prefix_only.fullmatch(line):
            pending_prefix = line
            buffer = ""  # reset bufferu
            continue

        # Některé popisy se mohou zalomit -> skládáme buffer
        buffer = (buffer + " " + line).strip() if buffer else line

        m = row_re.match(buffer)
        if not m:
            # ještě nemáme kompletní řádek -> čekáme na další řádek
            # ale buffer nenecháme růst donekonečna
            if len(buffer) > 400:
                buffer = ""
            continue

        code = m.group("code")
        desc = m.group("desc").strip()
        qty = clean_number(m.group("qty"))
        price = clean_number(m.group("price"))
        total = clean_number(m.group("total"))

        if pending_prefix:
            code = pending_prefix + code   # VEN- + 9161.167 => VEN-9161.167
            pending_prefix = None

        items.append(
            LineItem(
                product_number=code,
                product_name=desc,
                delivered_qty=qty,
                net_unit_price=price,
                total_price=total,
                customs_code="",
                weight_g="",
            )
        )

        buffer = ""  # připrav se na další položku

    if not items:
        warnings.append("OmniaParser: Nenalezeny žádné položky (neodpovídá formát řádků s 'PZ' a €).")

    return ParseResult(
        header={"supplier": "omnia"},
        items=items,
        warnings=warnings
    )


def create() -> OmniaParser:
    return OmniaParser()
