"""Phase 4: Urun detay zenginlestirme.

[VERIFY] DETAIL_URL Phase 0'da dogrulanmali.
Her urun icin: kategori breadcrumb, aciklama, olculer, marka, barkod ceker.
En cok istek atilan / en riskli asama -> en yavas burada gidilir.
"""

from __future__ import annotations

import json

import config
from api_client import ApiClient
from extract import (
    deep_find,
    extract_attributes,
    extract_breadcrumb,
    extract_dimensions,
)
from models import ProductDetail


def fetch_detail(client: ApiClient, product_id: str, product_url: str | None = None) -> ProductDetail:
    url = config.DETAIL_URL.format(product_id=product_id)
    data = client.get_json(url, referer=product_url or "https://www.trendyol.com/")

    attributes = extract_attributes(data)
    description = deep_find(data, ["description", "contentDescriptionText", "productDescription"])
    brand = deep_find(data, ["brand", "brandName"])
    if isinstance(brand, dict):
        brand = deep_find(brand, ["name", "text"])
    barcode = deep_find(data, ["barcode", "barkod", "gtin"])

    return ProductDetail(
        product_id=str(product_id),
        category_path=extract_breadcrumb(data),
        description=str(description) if description else None,
        attributes_json=json.dumps(attributes, ensure_ascii=False) if attributes else None,
        dimensions=extract_dimensions(attributes),
        brand=str(brand) if brand else None,
        barcode=str(barcode) if barcode else None,
    )
