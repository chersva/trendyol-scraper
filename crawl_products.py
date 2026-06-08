"""Phase 3: Magaza urun listesi (paginated).

[DOGRULANMIS] Endpoint: discovery-sfint-search-service/api/search/products
Parametreler: mid=merchant_id, pi=sayfa(0'dan), os=1, channelId=1
Yanit yapisi: products[], total, _links.next
"""

from __future__ import annotations

from typing import Callable

import config
from api_client import ApiClient
from extract import deep_find, extract_product_list, full_url, to_number
from models import Product


def _parse_product(item: dict, merchant_id: str) -> Product:
    pid = deep_find(item, ["id", "contentId", "productId", "productContentId"])
    name = deep_find(item, ["name", "productName", "title"])
    # seller_name listede gelmiyor; merchantId var ama ad yok
    # -> detay aşamasında zenginleştirilir
    seller = deep_find(item, ["sellerName", "merchantName", "seller", "supplierName"])
    barcode = deep_find(item, ["barcode", "barkod", "gtin"])
    url = deep_find(item, ["url", "productUrl", "link"])

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


def fetch_products(
    client: ApiClient,
    merchant_id: str,
    reported_count: int | None = None,
    max_pages: int = config.MAX_PAGES,
    progress: Callable[[str], None] | None = None,
) -> list[Product]:
    # DOGRULANMIS param seti (DevTools'tan)
    base_params = {
        "mid": merchant_id,
        "os": 1,
        "channelId": config.CHANNEL_ID,
        "storefrontId": 1,
    }
    url = config.PRODUCTS_URL
    collected: dict[str, Product] = {}
    seen_page_signatures: set[frozenset] = set()

    for pi in range(0, max_pages):
        params = {**base_params, "pi": pi}
        data = client.get_json(url, params=params, referer="https://www.trendyol.com/magaza")
        items = extract_product_list(data)

        # API'nin bildirdiği toplam (ilk sayfada alınır, sonrakinde de aynı gelir)
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
            product = _parse_product(item, merchant_id)
            if not product.product_id:
                continue
            page_ids.add(product.product_id)
            if product.product_id not in collected:
                collected[product.product_id] = product
                new_in_page += 1

        # Sayfalama ilerlemiyor mu? (ayni id seti tekrar = donguye girme / shadow-ban)
        signature = frozenset(page_ids)
        if signature and signature in seen_page_signatures:
            if progress:
                progress(f"  sayfa {pi}: ayni urunler tekrar geldi, durduruluyor")
            break
        seen_page_signatures.add(signature)

        if progress:
            progress(f"  sayfa {pi}: +{new_in_page} (toplam {len(collected)})")

        if new_in_page == 0:
            break
        if reported_count and len(collected) >= reported_count:
            break

    return list(collected.values())
