"""Phase 2: Magaza metadata (header-information endpoint).

Kullanicinin elindeki calisan endpoint = header-information.
Magaza adi, urun sayisi ve magaza URL'sini ceker.
"""

from __future__ import annotations

import config
from api_client import ApiClient
from extract import deep_find, full_url
from models import Store


def fetch_store(client: ApiClient, merchant_id: str) -> Store:
    url = config.HEADER_INFO_URL.format(merchant_id=merchant_id)
    data = client.get_json(
        url,
        params={"channelId": config.CHANNEL_ID},
        referer="https://www.trendyol.com/magaza",
    )

    name = deep_find(data, ["name", "storeName", "sellerName", "displayName"])
    count = deep_find(data, ["productCount", "totalProductCount", "count", "contentCount"])
    store_url = deep_find(data, ["url", "storeUrl", "sellerUrl", "link", "webUrl"])

    try:
        count_int = int(count) if count is not None else None
    except (TypeError, ValueError):
        count_int = None

    return Store(
        merchant_id=str(merchant_id),
        name=str(name) if name else None,
        product_count=count_int,
        store_url=full_url(store_url),
        raw=data if isinstance(data, dict) else {},
    )
