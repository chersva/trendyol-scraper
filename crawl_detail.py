"""Phase 4: Urun detay — urun sayfasinin HTML'inden __NEXT_DATA__ parse eder.

Trendyol, kategori breadcrumb / ozellikler / marka / barkod bilgisini ayri bir
JSON API'de degil, sayfa HTML'ine gomulmus __NEXT_DATA__ script blogu icinde
gonderiyor. Her urun linki zaten elimizde oldugu icin o sayfayi cekip parse
ediyoruz.
"""

from __future__ import annotations

import json
import re

import config
from api_client import ApiClient
from extract import deep_find, extract_attributes, extract_brand, extract_dimensions
from models import ProductDetail

# __NEXT_DATA__ JSON'unu HTML'den cikaran regex
_NEXT_DATA_RE = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>\s*(\{.*?\})\s*</script>',
    re.DOTALL,
)

_debug_saved = False  # ilk urun JSON'unu kaydet (DEBUG)


def _parse_next_data(html: str) -> dict:
    m = _NEXT_DATA_RE.search(html)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except Exception:
        return {}


def _breadcrumb_from_next(data: dict) -> str | None:
    """pageProps.breadcrumbs listesinden 'A > B > C' formatinda yol olusturur."""
    try:
        crumbs = data["props"]["pageProps"]["breadcrumbs"]
        if isinstance(crumbs, list) and crumbs:
            names = [c.get("name", "") for c in crumbs if isinstance(c, dict) and c.get("name")]
            return " > ".join(names) if names else None
    except (KeyError, TypeError):
        pass
    # Fallback: derinlemesine ara
    node = deep_find(data, ["breadcrumbs", "breadcrumb", "categoryHierarchy"])
    if isinstance(node, list):
        names = [deep_find(x, ["name", "text"]) for x in node if isinstance(x, dict)]
        names = [str(n) for n in names if n]
        return " > ".join(names) if names else None
    return None


def _product_node(data: dict) -> dict:
    """pageProps altindaki urun objesini dondurur."""
    try:
        pp = data["props"]["pageProps"]
        for key in ("product", "productModel", "item", "productDetail"):
            if key in pp and isinstance(pp[key], dict):
                return pp[key]
        return pp  # en azindan pageProps
    except (KeyError, TypeError):
        return {}


def fetch_detail(client: ApiClient, product_id: str, product_url: str | None = None) -> ProductDetail:
    global _debug_saved

    if not product_url:
        # URL yoksa bos detay dondur
        return ProductDetail(product_id=str(product_id))

    html = client.get_text(product_url, referer="https://www.trendyol.com/")
    data = _parse_next_data(html)

    # DEBUG: ilk urun icin ham JSON'u kaydet
    if not _debug_saved and data:
        try:
            with open("debug_detail.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        _debug_saved = True

    product = _product_node(data)

    # Kategori breadcrumb
    category_path = _breadcrumb_from_next(data)

    # Aciklama
    description = (
        deep_find(product, ["description", "productDescription", "contentDescription"])
        or deep_find(data, ["description"])
    )

    # Ozellikler
    attributes = extract_attributes(product) or extract_attributes(data)

    # Marka
    brand = extract_brand(product) or extract_brand(data)

    # Barkod
    barcode = (
        deep_find(product, ["barcode", "barkod", "gtin", "sku"])
        or deep_find(data, ["barcode", "barkod", "gtin"])
    )

    return ProductDetail(
        product_id=str(product_id),
        category_path=category_path,
        description=str(description).strip() if description else None,
        attributes_json=json.dumps(attributes, ensure_ascii=False) if attributes else None,
        dimensions=extract_dimensions(attributes),
        brand=str(brand).strip() if brand else None,
        barcode=str(barcode).strip() if barcode else None,
    )
