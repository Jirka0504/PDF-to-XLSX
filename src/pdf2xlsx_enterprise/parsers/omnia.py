from __future__ import annotations

import re
from typing import Dict, Any, List, Optional, Tuple

from .base import SupplierParser
from ..types import ParseResult, LineItem
from ..utils import normalize_ws, money_to_str


# -----------------------------
# Helpers
# -----------------------------

_RE_HEADER = re.compile(
    r"\bPRODUCT\s+CODE\b.*\bDESCRIPTION\b.*\bQUANTITY\b.*\bPREZZO\b.*\bIMPORTO\s+TOTALE\b",
    re.IGNORECASE,
)

# Token that looks like a product code at start of a line (very permissive)
_RE_STARTS_WITH_CODE = re.compile(r"^(?P<code>[A-Z0-9][A-Z0-9.\-]{1,})\b")

# Lines that are only a prefix ending with dash (e.g., "SS-" or "VEN-")
_RE_PREFIX_ONLY = re.compile(r"^(?P<prefix>[A-Z]{2,6}-)$")

# End-of-line pattern for Omnia rows (qty + PZ + price + total)
# Example:
# 125709  LAMP COVER ... 100 PZ 1.15€ 115.00€
_RE_ROW_TAIL = re.compile(
    r"(?P<desc>.+?)\s+(?P<qty>\d+)\s+PZ\s+(?P<price>\d+[.,]\d{2})\s*€?\s+(?P<total>\d+[.,]\d{2})\s*€?\s*$",
    re.IGNORECASE,
)


def _clean_money(s: str) -> str:
    """Return normalized money string like '1.95'."""
    s = normalize_ws(s).replace("€", "").strip()
    # money_to_str already normalizes comma/dot; keep using it
    return money_to_str(s)


def _clean_qty(s: str) -> str:
    s = normalize_ws(s).strip()
    # keep digits only
    m = re.search(r"\d+", s)
    return m.group(0) if m else ""


def _fix_prefix_code(prefix: str, first_token: str) -> str:
    """
    Special handling for cases like:
      VEN- + 9161.167  -> expected VEN-161.167 (per user requirement)
      SS-  + 2230002839 -> SS-2230002839
    """
    token = first_token.strip()

    # Your explicit rule: for VEN- drop leading '9' if it forms 4 digits before dot (9161.167)
    if prefix.upper() == "VEN-" and re.fullmatch(r"9\d{3}\.\d{3}", token):
        token = token[1:]  # 9161.167 -> 161.167

    return f"{prefix}{token}"


def _split_first_token(line: str) -> Tuple[str, str]:
    """Split line into first token and remainder."""
    parts = normalize_ws(line).split(" ", 1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _looks_like_item_start(line: str) -> bool:
    line = normalize_ws(line)
    if not line:
        return False
    if _RE_PREFIX_ONLY.match(line):
        return True
    return bool(_RE_STARTS_WITH_CODE.match(line))


# -----------------------------
# Parser
# -----------------------------

class OmniaParser(SupplierParser):
    """
    Parser for Omnia invoice layout (e.g., 26VIN...).

    Extracts rows in table:
      PRODUCT CODE | DESCRIPTION | QUANTITY | PREZZO | IMPORTO TOTALE

    Handles wrapped rows:
      SS-
      2230002839 POIGNEE EQUIPEE C&S MULTI 2 PZ 8.82€ 17.63€

    And the known VEN- anomaly:
      VEN-
      9161.167 D.35.8 SHOWER 1 PZ 1.95€ 1.95€
      -> code: VEN-161.167 (per requirement)
    """

    supplier_key = "omnia"
    display_name = "Omnia (enterprise invoice layout)"

    def can_parse(self, pdf_text_pages: List[str], tables: list) -> bool:
        text = "\n".join(pdf_text_pages).lower()
        # robust signatures seen in your PDFs
        return ("omniacomponents" in text) or ("26vin" in text) or ("product code" in text and "importo totale" in text)

    def parse(self, pdf_text_pages: List[str], tables: list, options: Dict[str, Any]) -> ParseResult:
        warnings: List[str] = []
        items: List[LineItem] = []

        # We intentionally prefer text parsing for this supplier (tables from PDF are often messy).
        raw_lines: List[str] = []
        for page in pdf_text_pages:
            for ln in (page or "").splitlines():
                ln = normalize_ws(ln)
                if ln:
                    raw_lines.append(ln)

        # 1) Find the item table start by header line
        start_idx = 0
        for i, ln in enumerate(raw_lines):
            if _RE_HEADER.search(ln):
                start_idx = i + 1
                break

        lines = raw_lines[start_idx:]

        # 2) Walk lines and assemble logical rows
        pending_prefix: Optional[str] = None
        buf: List[str] = []

        def flush_buf_if_complete() -> bool:
            nonlocal buf, pending_prefix, items
            if not buf:
                return False

            candidate = normalize_ws(" ".join(buf))
            # candidate should start with code token
            code_token, rest = _split_first_token(candidate)
            if not code_token:
                buf = []
                return False

            # Tail (qty/price/total) must match
            m = _RE_ROW_TAIL.match(rest)
            if not m:
                return False

            desc = normalize_ws(m.group("desc")).strip()
            qty = _clean_qty(m.group("qty"))
            price = _clean_money(m.group("price"))
            total = _clean_money(m.group("total"))

            # extra safety: if price/total not numeric-like after cleanup, drop
            if not re.fullmatch(r"\d+(?:\.\d{2})?", price):
                price = ""
            if not re.fullmatch(r"\d+(?:\.\d{2})?", total):
                total = ""

            items.append(
                LineItem(
                    product_number=code_token,
                    product_name=desc,
                    customs_code="",
                    weight_g="",
                    delivered_qty=qty,
                    net_unit_price=price,
                    total_price=total,
                )
            )
            buf = []
            return True

        i = 0
        while i < len(lines):
            ln = lines[i]
            ln = normalize_ws(ln)

            # Stop heuristics (optional): if invoice totals section starts
            if re.search(r"\bTOTAL\b|\bTOTALE\b|\bIMPONIBILE\b", ln, re.IGNORECASE) and not _looks_like_item_start(ln):
                # Do not break too aggressively; but usually items are over here.
                # We'll only break if we already collected something and buffer is empty.
                if items and not buf:
                    break

            # prefix-only line like "SS-" or "VEN-"
            pm = _RE_PREFIX_ONLY.match(ln)
            if pm and not buf:
                pending_prefix = pm.group("prefix")
                i += 1
                continue

            # If we have a pending prefix, attach it to next line's first token
            if pending_prefix and not buf:
                first_token, rest = _split_first_token(ln)
                if first_token:
                    combined_code = _fix_prefix_code(pending_prefix, first_token)
                    ln = f"{combined_code} {rest}".strip()
                pending_prefix = None

            # Start of a new item row?
            if not buf and _looks_like_item_start(ln):
                buf = [ln]
                # If complete immediately, flush
                if flush_buf_if_complete():
                    i += 1
                    continue
                # else keep accumulating next lines (wrapped description)
                i += 1
                continue

            # If we are accumulating, add line and try to flush
            if buf:
                # Sometimes there is a stray header repeat line, skip it
                if _RE_HEADER.search(ln):
                    i += 1
                    continue

                buf.append(ln)
                if flush_buf_if_complete():
                    i += 1
                    continue

                # Guard: if buffer becomes too long, reset to avoid runaway
                if len(buf) > 4:
                    warnings.append(f"Could not parse row (skipped): {' | '.join(buf)}")
                    buf = []
                i += 1
                continue

            # Otherwise ignore line
            i += 1

        # Final flush attempt
        if buf and not flush_buf_if_complete():
            warnings.append(f"Incomplete row at end (skipped): {' | '.join(buf)}")

        if not items:
            warnings.append("No line items detected by OmniaParser. (Header not found or format differs.)")

        header = {"source": "omnia"}
        return ParseResult(header=header, items=items, warnings=warnings)


def create() -> OmniaParser:
    return OmniaParser()
