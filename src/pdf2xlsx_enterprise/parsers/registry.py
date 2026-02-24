from __future__ import annotations
from typing import Dict, Type, List
from .base import SupplierParser

_REGISTRY: Dict[str, SupplierParser] = {}

def register(parser: SupplierParser) -> None:
    key = parser.supplier_key
    _REGISTRY[key] = parser

def get(key: str) -> SupplierParser:
    if key not in _REGISTRY:
        raise KeyError(f"Unknown supplier key: {key}. Available: {list(_REGISTRY.keys())}")
    return _REGISTRY[key]

def all_parsers() -> List[SupplierParser]:
    return [p for _, p in sorted(_REGISTRY.items(), key=lambda kv: kv[0])]
