from __future__ import annotations

import re
from typing import Dict, Any, List

from .base import SupplierParser
from ..types import ParseResult, LineItem
from ..utils import normalize_ws


def clean_number(s: str) -> str:
    """
    Normalize numeric strings to "1234.56" (dot decimal) and strip non-numeric chars.
    """
    s = (s or "").strip()
    s = re.sub(r"[^0-9,\.]", "", s)

    # "1,23" -> "1.23" (if only comma present)
    if s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")

    # "1,234.56" or "1.234,56" -> best effort: remove thousands separator commas
    if s.count(".") >= 1 and s.count(",") >= 1:
        # assume comma thousands
        s = s.replace(",", "")

    return s


class OmniaParser(SupplierParser):
    """
    Omnia invoice (table with: PRODUCT CODE, DESCRIPTION, QUANTITY, PREZZO, ...)

    Handles:
    - one-line items:
        125709  LAMP ...  100 PZ  1.15 €  115.00 €
    - two-line items:
        125709  LAMP ...
        100 PZ  1.15 €  115.00 €
    - prefix-only codes split:
        VEN-
        9161.167  D.35.8 SHOWER
        1 PZ  1.95 €  1.95 €
    - "merged prefix + first word of description" bug:
        SS-POIGNEE  EQUIPEE C&S MULTI
        2230002839
        2 PZ  8.82 €  17.63 €
      => SS-2230002839 + POIGNEE EQUIPEE C&S MULTI
    """

    supplier_key = "omnia"
    display_name = "Omnia (enterprise invoice)"

    # Full row: CODE + DESC + QTY PZ + PRICE € + TOTAL €
    _row_full_re = re.compile(
        r"^(?P<code>[A-Z0-9][A-Z0-9\-\./]{2,})\s+"
        r"(?P<desc>.+?)\s+"
        r"(?P<qty>\d+)\s+PZ\s+"
        r"(?P<price>[\d.,]+)\s*€\s+"
        r"(?P<total>[\d.,]+)\s*€?\s*$"
    )

    # Quantity line (for 2-line items)
    _qty_line_re = re.compile(
        r"^(?P<qty>\d+)\s+PZ\s+"
        r"(?P<price>[\d.,]+)\s*€\s+"
        r"(?P<total>[\d.,]+)\s*€?\s*$"
    )

    # Prefix-only line like "VEN-" or "SS-"
    _prefix_only_re = re.compile(r"^[A-Z]{2,8}-$")

    # First token must look like a product code
    _code_token_re = re.compile(r"^[A-Z0-9][A-Z0-9\-\./]{2,}$")

    def can_parse(self, pdf_text_pages: List[str], tables: list) -> bool:
        text = "\n".join(pdf_text_pages).lower()
        return ("omniacomponents" in text) or ("26vin" in text) or ("product code" in text)

    @staticmethod
    def _is_header_line(s: str) -> bool:
        lo = (s or "").lower()
        header_words = ("product", "code", "description", "quantity", "prezzo", "sconto", "importo", "totale")
        hits = sum(1 for w in header_words if w in lo)
        return hits >= 3

    def parse(self, pdf_text_pages: List[str], tables: list, options: Dict[str, Any]) -> ParseResult:
        # Flatten and normalize lines
        lines: List[str] = []
        for page in pdf_text_pages:
            for l in (page or "").splitlines():
                l = normalize_ws(l)
                if l:
                    lines.append(l)

        items: List[LineItem] = []
        warnings: List[str] = []

        pending_prefix: str | None = None          # e.g. "VEN-" / "SS-"
        pending_code: str | None = None            # e.g. "125709" or "SS-2230002839"
        pending_desc: str | None = None            # description buffer
        pending_prefix_desc: str | None = None     # e.g. "POIGNEE EQUIPEE C&S MULTI" when token becomes SS-POIGNEE

        for line in lines:
            # 0) skip headers
            if self._is_header_line(line):
                continue

            # 1) prefix-only line e.g. "VEN-"
            if self._prefix_only_re.fullmatch(line):
                pending_prefix = line
                pending_code = None
                pending_desc = None
                # do NOT clear pending_prefix_desc here; new prefix resets meaning
                pending_prefix_desc = None
                continue

            # 2) FULL one-line item
            m = self._row_full_re.match(line)
            if m:
                code = m.group("code").strip()
                desc = m.group("desc").strip()
                qty = clean_number(m.group("qty"))
                price = clean_number(m.group("price"))
                total = clean_number(m.group("total"))

                if pending_prefix:
                    code = pending_prefix + code
                    pending_prefix = None

                # if we previously captured prefix-desc, prepend it and clear
                if pending_prefix_desc:
                    desc = (pending_prefix_desc + " " + desc).strip()
                    pending_prefix_desc = None

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
                pending_code = None
                pending_desc = None
                continue

            # 2.5) Special case: we have prefix+desc first (SS-POIGNEE...), then a numeric-only line is the code
            if pending_prefix and pending_prefix_desc and re.fullmatch(r"\d{6,}", line):
                pending_code = pending_prefix + line
                pending_desc = pending_prefix_desc
                pending_prefix = None
                pending_prefix_desc = None
                continue

            # 3) Quantity line attaches to buffered code+desc
            q = self._qty_line_re.match(line)
            if q and pending_code and pending_desc:
                qty = clean_number(q.group("qty"))
                price = clean_number(q.group("price"))
                total = clean_number(q.group("total"))

                items.append(
                    LineItem(
                        product_number=pending_code,
                        product_name=pending_desc,
                        delivered_qty=qty,
                        net_unit_price=price,
                        total_price=total,
                        customs_code="",
                        weight_g="",
                    )
                )
                pending_code = None
                pending_desc = None
                continue

            # 4) "CODE + rest..." candidate (first line of 2-line item)
            parts = line.split(" ", 1)
            if len(parts) == 2 and self._code_token_re.fullmatch(parts[0]):
                token = parts[0].strip()
                rest = parts[1].strip()

                # 4a) Handle merged prefix+first-word-of-description like "SS-POIGNEE"
                # Detect: PREFIX + WORD (letters only), no digits inside the token
                m_pref = re.fullmatch(r"(?P<prefix>[A-Z]{2,8}-)(?P<word>[A-Z]{2,})", token)
                if m_pref and not re.search(r"\d", token):
                    pending_prefix = m_pref.group("prefix")
                    pending_prefix_desc = (m_pref.group("word") + " " + rest).strip()
                    pending_code = None
                    pending_desc = None
                    continue

                # normal code+desc buffering
                pending_code = token
                pending_desc = rest

                if pending_prefix:
                    pending_code = pending_prefix + pending_code
                    pending_prefix = None

                # if we already captured prefix-desc earlier, prepend it now
                if pending_prefix_desc:
                    pending_desc = (pending_prefix_desc + " " + pending_desc).strip()
                    pending_prefix_desc = None

                continue

            # 5) Continuation of description while we wait for quantity line
            if pending_code and pending_desc:
                # ignore accidental headers
                if not self._is_header_line(line):
                    pending_desc = (pending_desc + " " + line).strip()
                continue

            # otherwise ignore

        if not items:
            warnings.append("OmniaParser: Nenalezeny položky. Ověř, že PDF obsahuje řádky s 'PZ' a cenami s €.")

        return ParseResult(header={"supplier": "omnia"}, items=items, warnings=warnings)


def create() -> OmniaParser:
    return OmniaParser()
