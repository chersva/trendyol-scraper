"""Veri modelleri (dataclass'lar)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Store:
    merchant_id: str
    name: str | None = None
    product_count: int | None = None
    store_url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Product:
    product_id: str
    merchant_id: str
    name: str | None = None
    price: float | None = None
    original_price: float | None = None
    seller_name: str | None = None
    product_url: str | None = None
    barcode: str | None = None


@dataclass
class ProductDetail:
    product_id: str
    category_path: str | None = None
    description: str | None = None
    attributes_json: str | None = None   # tum ozellikler ham JSON (string)
    dimensions: str | None = None        # ayiklanmis olculer
    brand: str | None = None
    barcode: str | None = None
