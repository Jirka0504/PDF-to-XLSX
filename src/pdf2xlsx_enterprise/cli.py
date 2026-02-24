from __future__ import annotations
import argparse
import json
from .logging_config import setup_logging
from .types import ConvertRequest
from .convert import convert
from .parsers import bootstrap

def main() -> int:
    bootstrap()
    p = argparse.ArgumentParser(description="Enterprise PDF→XLSX converter (multi-supplier)")
    p.add_argument("--pdf", required=True, help="Input PDF path")
    p.add_argument("--template", required=True, help="XLSX template path")
    p.add_argument("--out", required=True, help="Output XLSX path")
    p.add_argument("--supplier", required=True, help="Supplier key (e.g. omnia, generic)")
    p.add_argument("--options", default="{}", help="JSON options (sheet_name, mapping, clear_existing, etc.)")
    p.add_argument("--log", default="INFO", help="Log level")
    args = p.parse_args()

    setup_logging(args.log)

    options = json.loads(args.options) if args.options else {}
    req = ConvertRequest(
        pdf_path=args.pdf,
        template_xlsx_path=args.template,
        output_xlsx_path=args.out,
        supplier_key=args.supplier,
        options=options,
    )
    res = convert(req)
    if res.warnings:
        print("\nWARNINGS:")
        for w in res.warnings:
            print("-", w)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
