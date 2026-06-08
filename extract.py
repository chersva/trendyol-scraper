"""JSON ayiklama yardimcilari.

Trendyol endpoint'lerinin JSON sekli henuz %100 dogrulanmadigi icin (Phase 0),
bu fonksiyonlar SAVUNMACI yazildi: ic ice yapida birden cok olasi anahtar adini
dener. Endpoint sekli netlesince buradaki anahtar listelerini daraltabilirsin.
"""

from __future__ import annotations

import re
from typing import Any, Iterable


def deep_find(obj: Any, keys: Iterable[str], default: Any = None) -> Any:
    """Ic ice dict/list icinde verilen anahtarlardan ilk dolu eslesmeyi dondurur.

    DFS ile gezer; ilk bos olmayan deger kazanir. Anahtarlar kucuk/buyuk harf
    duyarsiz karsilastirilir.
    """
    targets = {k.lower() for k in keys}
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if isinstance(k, str) and k.lower() in targets and v not in (None, "", [], {}):
                    return v
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return default


def to_number(value: Any) -> float | None:
    """Fiyat gibi alanlari float'a cevirir. dict ise icindeki value/amount'i alir."""
    if isinstance(value, dict):
        value = deep_find(value, ["value", "amount", "price", "sellingPrice"])
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(".", "").replace(",", ".")) if _looks_tr_money(str(value)) else float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _looks_tr_money(text: str) -> bool:
    # "1.299,90" gibi TR formatini yakala (binlik nokta + ondalik virgul)
    return "." in text and "," in text and text.rfind(",") > text.rfind(".")


def full_url(url: Any) -> str | None:
    """Goreli (/...) linkleri tam Trendyol URL'sine cevirir."""
    if not url:
        return None
    url = str(url)
    if url.startswith("http"):
        return url
    if url.startswith("/"):
        return "https://www.trendyol.com" + url
    return "https://www.trendyol.com/" + url


def extract_product_list(data: Any) -> list:
    """Listeleme yanitindan urun dizisini bulur."""
    for key in ("products", "content", "items", "productList", "result", "hits"):
        node = deep_find(data, [key])
        if isinstance(node, list) and node:
            return node
    return []


def extract_breadcrumb(data: Any) -> str | None:
    """Kategori breadcrumb'ini 'A > B > C' formatinda dondurur."""
    for key in ("breadcrumb", "breadcrumbs", "categoryHierarchy", "categories"):
        node = deep_find(data, [key])
        if isinstance(node, list) and node:
            names = [deep_find(x, ["name", "text", "title"]) for x in node if isinstance(x, dict)]
            names = [str(n).strip() for n in names if n]
            if names:
                return " > ".join(names)
    cat = deep_find(data, ["category"])
    if isinstance(cat, dict):
        hierarchy = deep_find(cat, ["hierarchy"])
        if hierarchy:
            return str(hierarchy).replace("/", " > ")
        name = deep_find(cat, ["name"])
        if name:
            return str(name)
    return None


def extract_attributes(data: Any) -> dict:
    """Urun ozelliklerini {ad: deger} dict'i olarak dondurur."""
    for key in ("attributes", "productAttributes", "contentDescriptions", "characteristics"):
        node = deep_find(data, [key])
        if isinstance(node, list) and node:
            out: dict[str, str] = {}
            for x in node:
                if not isinstance(x, dict):
                    continue
                k = deep_find(x, ["key", "name", "title", "attributeName", "label"])
                v = deep_find(x, ["value", "valueName", "attributeValue", "text", "values"])
                if k and v:
                    out[str(k).strip()] = str(v).strip()
            if out:
                return out
    return {}


_DIM_NEEDLES = (
    "genislik", "genişlik", "yukseklik", "yükseklik", "derinlik",
    "uzunluk", "olcu", "ölçü", "olculer", "ölçüler", "ebat", "ebatlar",
    "boyut", "boyutlar", "en", "boy", "cap", "çap", "kalinlik", "kalınlık",
    "width", "height", "depth", "length", "diameter", "thickness",
    "size", "dimension", "dimensions",
)
# Kelime-sinir eslesmesi: "en" -> "renk" icindeki "en"e takilmaz.
_DIM_PATTERN = re.compile(
    r"(?<![\wığüşöçİ])(?:" + "|".join(re.escape(n) for n in _DIM_NEEDLES) + r")(?![\wığüşöçİ])",
    re.IGNORECASE,
)


def extract_dimensions(attributes: dict) -> str | None:
    """Ozellikler icinden olcu (en/boy/yukseklik vb.) iceren alanlari ayiklar.

    Anahtar adinda olcu kelimesi TAM kelime olarak gecmeli (substring degil),
    boylece 'Renk' gibi alanlar yanlislikla olcu sayilmaz.
    """
    if not attributes:
        return None
    found = []
    for k, v in attributes.items():
        if _DIM_PATTERN.search(str(k)):
            found.append(f"{k}: {v}")
    return "; ".join(found) if found else None
