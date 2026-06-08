"""SQLite katmani: schema + idempotent upsert + scrape_log + resume yardimcilari.

Tum yazmalar idempotent (INSERT OR REPLACE / ON CONFLICT) oldugu icin uygulamayi
tekrar tekrar calistirmak guvenlidir; ayni kayit iki kez yazilmaz.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from models import Product, ProductDetail, Store

SCHEMA = """
CREATE TABLE IF NOT EXISTS merchants (
    merchant_id   TEXT PRIMARY KEY,
    store_name    TEXT,
    product_count INTEGER,
    store_url     TEXT,
    scraped_at    TEXT,
    status        TEXT
);

CREATE TABLE IF NOT EXISTS products (
    product_id         TEXT PRIMARY KEY,
    merchant_id        TEXT,
    name               TEXT,
    price              REAL,
    original_price     REAL,
    seller_name        TEXT,
    product_url        TEXT,
    barcode            TEXT,
    listing_scraped_at TEXT
);

CREATE TABLE IF NOT EXISTS product_details (
    product_id        TEXT PRIMARY KEY,
    category_path     TEXT,
    description       TEXT,
    attributes_json   TEXT,
    dimensions        TEXT,
    brand             TEXT,
    barcode           TEXT,
    detail_scraped_at TEXT,
    source            TEXT DEFAULT 'detail'   -- 'listing' (kismi) | 'detail' (tam)
);

CREATE TABLE IF NOT EXISTS scrape_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id TEXT,
    product_id  TEXT,
    phase       TEXT,
    status      TEXT,
    http_status INTEGER,
    message     TEXT,
    ts          TEXT
);

CREATE INDEX IF NOT EXISTS idx_products_merchant ON products(merchant_id);
CREATE INDEX IF NOT EXISTS idx_log_merchant ON scrape_log(merchant_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    # Eski DB'lerde 'source' sutunu olmayabilir -> guvenli migration.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(product_details)")}
    if "source" not in cols:
        conn.execute("ALTER TABLE product_details ADD COLUMN source TEXT DEFAULT 'detail'")
    conn.commit()
    return conn


def upsert_merchant(conn: sqlite3.Connection, store: Store, status: str = "ok") -> None:
    conn.execute(
        """
        INSERT INTO merchants (merchant_id, store_name, product_count, store_url, scraped_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(merchant_id) DO UPDATE SET
            store_name=excluded.store_name,
            product_count=excluded.product_count,
            store_url=excluded.store_url,
            scraped_at=excluded.scraped_at,
            status=excluded.status
        """,
        (store.merchant_id, store.name, store.product_count, store.store_url, _now(), status),
    )
    conn.commit()


def update_merchant_status(conn: sqlite3.Connection, merchant_id: str, status: str) -> None:
    conn.execute("UPDATE merchants SET status=? WHERE merchant_id=?", (status, merchant_id))
    conn.commit()


def upsert_product(conn: sqlite3.Connection, p: Product) -> None:
    conn.execute(
        """
        INSERT INTO products
            (product_id, merchant_id, name, price, original_price, seller_name,
             product_url, barcode, listing_scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(product_id) DO UPDATE SET
            merchant_id=excluded.merchant_id,
            name=excluded.name,
            price=excluded.price,
            original_price=excluded.original_price,
            seller_name=excluded.seller_name,
            product_url=excluded.product_url,
            barcode=excluded.barcode,
            listing_scraped_at=excluded.listing_scraped_at
        """,
        (
            p.product_id, p.merchant_id, p.name, p.price, p.original_price,
            p.seller_name, p.product_url, p.barcode, _now(),
        ),
    )
    conn.commit()


def upsert_detail(conn: sqlite3.Connection, d: ProductDetail, source: str = "detail") -> None:
    """Tam detay (endpoint'ten). Kismi/listeleme kaydinin uzerine yazar."""
    conn.execute(
        """
        INSERT INTO product_details
            (product_id, category_path, description, attributes_json, dimensions,
             brand, barcode, detail_scraped_at, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(product_id) DO UPDATE SET
            category_path=excluded.category_path,
            description=excluded.description,
            attributes_json=excluded.attributes_json,
            dimensions=excluded.dimensions,
            brand=excluded.brand,
            barcode=excluded.barcode,
            detail_scraped_at=excluded.detail_scraped_at,
            source=excluded.source
        """,
        (
            d.product_id, d.category_path, d.description, d.attributes_json,
            d.dimensions, d.brand, d.barcode, _now(), source,
        ),
    )
    conn.commit()


def insert_detail_if_absent(conn: sqlite3.Connection, d: ProductDetail, source: str = "listing") -> None:
    """Kismi detay (listeden). Zaten kayit varsa DOKUNMAZ -> tam detayi ezmez."""
    conn.execute(
        """
        INSERT INTO product_details
            (product_id, category_path, description, attributes_json, dimensions,
             brand, barcode, detail_scraped_at, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(product_id) DO NOTHING
        """,
        (
            d.product_id, d.category_path, d.description, d.attributes_json,
            d.dimensions, d.brand, d.barcode, _now(), source,
        ),
    )
    conn.commit()


def has_detail(conn: sqlite3.Connection, product_id: str) -> bool:
    """Resume icin: bu urunun TAM detayi zaten cekilmis mi? (kismi sayilmaz)"""
    cur = conn.execute(
        "SELECT 1 FROM product_details WHERE product_id=? AND source='detail'",
        (product_id,),
    )
    return cur.fetchone() is not None


def log(
    conn: sqlite3.Connection,
    merchant_id: str | None,
    product_id: str | None,
    phase: str,
    status: str,
    http_status: int | None = None,
    message: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO scrape_log (merchant_id, product_id, phase, status, http_status, message, ts)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (merchant_id, product_id, phase, status, http_status, message, _now()),
    )
    conn.commit()
