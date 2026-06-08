"""Phase 4: Urun detay zenginlestirme.

[DOGRULANMIS] Endpoint: discovery-storefront-trproductgw-service/api/component-read/component/{id}
Gerekli header: x-agentname: StorefrontProductGateway
Yanit yapisi: { isSuccess, result: { descriptions[], attributes[]?, category? } }
"""

from __future__ import annotations

import json

import config
from api_client import ApiClient
from extract import (
    deep_find,
    extract_attributes,
    extract_brand,
    extract_breadcrumb,
    extract_dimensions,
)
from models import ProductDetail

_DETAIL_HEADERS = {"x-agentname": config.DETAIL_AGENT}


def _extract_description(data: dict) -> str | None:
    """result.descriptions[] dizisinden aciklama metni ayiklar."""
    result = data.get("result") if isinstance(data, dict) else None
    if isinstance(result, dict):
        descs = result.get("descriptions") or []
        if isinstance(descs, list):
            parts = []
            for d in descs:
                if not isinstance(d, dict):
                    continue
                # Her desc objesinde "description" veya "value" anahtari
                text = d.get("description") or d.get("value") or d.get("text")
                if text and isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            if parts:
                return "\n".join(parts)
    # Fallback: derin arama
    return deep_find(data, ["description", "contentDescriptionText", "productDescription"])


_debug_saved = False  # ilk urun icin JSON'u dosyaya kaydet


def fetch_detail(client: ApiClient, product_id: str, product_url: str | None = None) -> ProductDetail:
    global _debug_saved
    url = config.DETAIL_URL.format(product_id=product_id)
    data = client.get_json(
        url,
        referer=product_url or "https://www.trendyol.com/",
        extra_headers=_DETAIL_HEADERS,
    )

    # DEBUG: ilk urun icin ham JSON'u kaydet -> hangi alanlarin geldigi gorulsun
    if not _debug_saved:
        import json as _json
        with open("debug_detail.json", "w", encoding="utf-8") as _f:
            _json.dump(data, _f, ensure_ascii=False, indent=2)
        _debug_saved = True

    # Yanit basarisizsa veya result yoksa bosla devam et (ban degil, veri yok)
    if isinstance(data, dict) and not data.get("isSuccess", True):
        pass  # devam et, result icinde bos listeler olabilir

    # result alt objesi varsa oradan cek, yoksa root'tan
    result = data.get("result", data) if isinstance(data, dict) else data

    attributes = extract_attributes(result) or extract_attributes(data)
    brand = extract_brand(result) or extract_brand(data)
    barcode = (
        deep_find(result, ["barcode", "barkod", "gtin"])
        or deep_find(data, ["barcode", "barkod", "gtin"])
    )

    return ProductDetail(
        product_id=str(product_id),
        category_path=extract_breadcrumb(result) or extract_breadcrumb(data),
        description=_extract_description(data),
        attributes_json=json.dumps(attributes, ensure_ascii=False) if attributes else None,
        dimensions=extract_dimensions(attributes),
        brand=str(brand) if brand else None,
        barcode=str(barcode) if barcode else None,
    )
