"""Phase 3: Magaza urun listesi (paginated).

[DOGRULANMIS] Endpoint: discovery-sfint-search-service/api/search/products
Ilk istek: mid=, pi=0, os=1, channelId=1, storefrontId=1  (DevTools'ta dogrulandi)
Sonraki sayfalar: yanittaki _links.next takip edilir; yoksa pi+ / pageSize ile
manuel ilerleriz (os PARAMETRESI DUSURULUR -- os=1 sabiti sayfalamayi kilitliyordu).
Yanit yapisi: { products: [...], total: N, _links: { next: ... } }

Listeleme yaniti zaten cok sey iceriyor (category.name, brand, productCardAttributes)
-> detay endpoint'i olmasa bile bunlardan KISMI bir ProductDetail uretiriz.
"""

from __future__ import annotations

import json
from typing import Callable

import config
from api_client import ApiClient
from extract import (
    deep_find,
    extract_attributes,
    extract_brand,
    extract_breadcrumb,
    extract_dimensions,
    extract_next_url,
    extract_product_list,
    full_url,
    to_number,
)
from models import Product, ProductDetail


def _parse_product(item: dict, merchant_id: str, store_name: str | None) -> Product:
    pid = deep_find(item, ["id", "contentId", "productId", "productContentId"])
    name = deep_find(item, ["name", "productName", "title"])
    barcode = deep_find(item, ["barcode", "barkod", "gtin"])
    url = deep_find(item, ["url", "productUrl", "link"])

    # Satici adi listede gelmiyor; magaza sayfasini cektigimiz tedarikci = satici.
    seller = (
        deep_find(item, ["sellerName", "merchantName", "supplierName"])
        or store_name
    )

    # Dogrulanmis fiyat yapisi: price.discountedPrice (indirimli), price.original (liste)
    price_node = item.get("price", {}) if isinstance(item.get("price"), dict) else {}
    price = to_number(
        price_node.get("discountedPrice") or price_node.get("current") or
        deep_find(item, ["discountedPrice", "sellingPrice", "salePrice"])
    )
    original = to_number(
        price_node.get("original") or price_node.get("old") or
        deep_find(item, ["originalPrice", "marketPrice", "listPrice"])
    )

    return Product(
        product_id=str(pid) if pid is not None else "",
        merchant_id=str(merchant_id),
        name=str(name) if name else None,
        price=price,
        original_price=original,
        seller_name=str(seller) if seller else None,
        product_url=full_url(url),
        barcode=str(barcode) if barcode else None,
    )


def _parse_listing_detail(item: dict, product_id: str) -> ProductDetail:
    """Listeleme item'indan KISMI detay uretir (kategori yapragi, marka, kart ozellikleri).

    Detay endpoint'i calistiginda bu kayit zenginlestirilmis veriyle ustune yazilir
    (idempotent upsert). Boylece detay olmasa bile elimizde anlamli veri olur.
    """
    attributes = extract_attributes(item)
    barcode = deep_find(item, ["barcode", "barkod", "gtin"])
    return ProductDetail(
        product_id=str(product_id),
        category_path=extract_breadcrumb(item),       # listede genelde yaprak kategori
        description=None,                              # aciklama yalnizca detayda
        attributes_json=json.dumps(attributes, ensure_ascii=False) if attributes else None,
        dimensions=extract_dimensions(attributes),
        brand=extract_brand(item),
        barcode=str(barcode) if barcode else None,
    )


def fetch_products(
    client: ApiClient,
    merchant_id: str,
    store_name: str | None = None,
    reported_count: int | None = None,
    max_pages: int = config.MAX_PAGES,
    progress: Callable[[str], None] | None = None,
) -> tuple[list[Product], list[ProductDetail]]:
    """Tum sayfalari gezer. (urunler, listeden_uretilen_kismi_detaylar) doner."""
    collected: dict[str, Product] = {}
    partials: dict[str, ProductDetail] = {}
    seen_page_signatures: set[frozenset] = set()

    # 1. sayfa: DOGRULANMIS param seti (proven). os=1 burada KALIR.
    next_url: str | None = config.PRODUCTS_URL
    next_params: dict | None = {
        "mid": merchant_id,
        "pi": 0,
        "os": 1,
        "channelId": config.CHANNEL_ID,
        "storefrontId": 1,
    }

    for pi in range(0, max_pages):
        if not next_url:
            break
        data = client.get_json(next_url, params=next_params, referer="https://www.trendyol.com/magaza")
        items = extract_product_list(data)

        if pi == 0 and reported_count is None:
            api_total = deep_find(data, ["total", "totalCount", "roughTotal"])
            if api_total:
                try:
                    reported_count = int(api_total)
                except (TypeError, ValueError):
                    pass

        if not items:
            break  # bos sayfa = liste bitti

        page_ids: set[str] = set()
        new_in_page = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            product = _parse_product(item, merchant_id, store_name)
            if not product.product_id:
                continue
            page_ids.add(product.product_id)
            if product.product_id not in collected:
                collected[product.product_id] = product
                partials[product.product_id] = _parse_listing_detail(item, product.product_id)
                new_in_page += 1

        # Ayni id seti tekrar geldi mi? (sayfalama kilitlendi / shadow-ban)
        signature = frozenset(page_ids)
        if signature and signature in seen_page_signatures:
            if progress:
                progress(f"  sayfa {pi}: ayni urunler tekrar geldi, durduruluyor")
            break
        seen_page_signatures.add(signature)

        if progress:
            progress(f"  sayfa {pi}: +{new_in_page} (toplam {len(collected)})")

        if reported_count and len(collected) >= reported_count:
            break

        # --- sonraki sayfa: once API'nin verdigi _links.next, yoksa manuel pi+ (os YOK) ---
        api_next = extract_next_url(data, next_url)
        if api_next:
            next_url = api_next
            next_params = None
        else:
            next_url = config.PRODUCTS_URL
            next_params = {
                "mid": merchant_id,
                "pi": pi + 1,
                "channelId": config.CHANNEL_ID,
                "storefrontId": 1,
                "pageSize": config.PAGE_SIZE,
            }

    return list(collected.values()), list(partials.values())
