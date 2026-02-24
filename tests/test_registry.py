from pdf2xlsx_enterprise.parsers import bootstrap
from pdf2xlsx_enterprise.parsers.registry import all_parsers, get

def test_bootstrap():
    bootstrap()
    ps = all_parsers()
    assert len(ps) >= 2
    assert get("omnia").supplier_key == "omnia"
