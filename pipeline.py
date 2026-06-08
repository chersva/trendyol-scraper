"""Orchestrator: bir tedarikciyi (veya listeyi) ucdan uca calistirir.

Akis (tek merchant):
  Phase 2 (magaza)  ->  Phase 3 (urun listesi)  ->  Phase 4 (detaylar)
Idempotent: tekrar calistirinca zaten cekilmis detaylari atlar (resume).
Fail-closed: BlockedError gelince temiz durur, sirket IP'sini yakmaz.
"""

from __future__ import annotations

import time
from typing import Callable

import config
import db
from api_client import ApiClient, BlockedError
from crawl_detail import fetch_detail
from crawl_products import fetch_products
from crawl_store import fetch_store
from detect_block import listing_incomplete

Progress = Callable[[str], None]


def run_merchant(
    client: ApiClient,
    conn,
    merchant_id: str,
    dry_run: bool = False,
    progress: Progress = print,
) -> None:
    """Tek tedarikciyi isler. BlockedError yukari firlatilir (fail-closed)."""

    # --- Phase 2: magaza ---
    progress(f"[{merchant_id}] magaza bilgisi cekiliyor...")
    store = fetch_store(client, merchant_id)
    db.upsert_merchant(conn, store, status="running")
    db.log(conn, merchant_id, None, "store", "ok", message=f"{store.name} | count={store.product_count}")
    progress(f"  -> {store.name or '(isim yok)'} | bildirilen urun sayisi: {store.product_count}")

    # --- Phase 3: urun listesi ---
    progress(f"[{merchant_id}] urun listesi cekiliyor...")
    products = fetch_products(
        client,
        merchant_id,
        reported_count=store.product_count,
        max_pages=1 if dry_run else config.MAX_PAGES,
        progress=progress,
    )
    for product in products:
        db.upsert_product(conn, product)
    db.log(conn, merchant_id, None, "products", "ok", message=f"{len(products)} urun")
    progress(f"  -> {len(products)} urun toplandi")

    # tamamlik kontrolu (shadow-ban sinyali)
    if not dry_run and listing_incomplete(len(products), store.product_count, config.COMPLETENESS_THRESHOLD):
        db.log(
            conn, merchant_id, None, "products", "incomplete",
            message=f"{len(products)}/{store.product_count}",
        )
        progress(
            f"  ! UYARI: toplanan ({len(products)}) bildirilen ({store.product_count}) "
            "sayinin yarisindan az -> shadow-ban / eksik veri olabilir."
        )

    if dry_run:
        progress("  (dry-run: detaylar cekilmedi)")
        _print_sample(products, progress)
        db.update_merchant_status(conn, merchant_id, "dry-run")
        return

    # --- Phase 4: detaylar ---
    progress(f"[{merchant_id}] urun detaylari cekiliyor ({len(products)} urun)...")
    ok, skipped, errors = 0, 0, 0
    for i, product in enumerate(products, start=1):
        if db.has_detail(conn, product.product_id):
            skipped += 1
            continue
        try:
            detail = fetch_detail(client, product.product_id, product.product_url)
            db.upsert_detail(conn, detail)
            db.log(conn, merchant_id, product.product_id, "detail", "ok")
            ok += 1
        except BlockedError:
            raise  # fail-closed: yukari firlat, tum isi durdur
        except Exception as exc:  # tek urun hatasi -> logla, devam et
            db.log(conn, merchant_id, product.product_id, "detail", "error", message=str(exc))
            errors += 1
        if i % 10 == 0:
            progress(f"  detay {i}/{len(products)} (yeni={ok} atlandi={skipped} hata={errors})")

    db.update_merchant_status(conn, merchant_id, "ok")
    progress(f"  -> detay bitti: yeni={ok} atlandi={skipped} hata={errors}")


def run_merchants(
    client: ApiClient,
    conn,
    merchant_ids: list[str],
    dry_run: bool = False,
    progress: Progress = print,
) -> None:
    """Birden cok tedarikciyi tek tek isler. Blok gorulurse tum kosu durur."""
    for idx, merchant_id in enumerate(merchant_ids, start=1):
        progress(f"\n=== ({idx}/{len(merchant_ids)}) tedarikci {merchant_id} ===")
        try:
            run_merchant(client, conn, merchant_id, dry_run=dry_run, progress=progress)
        except BlockedError as ban:
            db.log(conn, merchant_id, None, "store", "blocked", http_status=ban.status, message=ban.reason)
            db.update_merchant_status(conn, merchant_id, "blocked")
            progress(f"\n!!! BLOK: {ban}")
            progress("!!! Sirket IP'sini korumak icin kosu durduruldu.")
            progress("!!! Yapilabilecekler: cookie'yi yenile, bir sure bekle, veya PROXY_URL ayarla.")
            break

        if idx < len(merchant_ids):
            time.sleep(config.DELAY_BETWEEN_MERCHANTS)

    progress(f"\nOzet: {client.metrics_summary()}")


def _print_sample(products, progress: Progress) -> None:
    progress("  --- ornek (ilk 3) ---")
    for p in products[:3]:
        progress(f"    {p.product_id} | {p.name} | {p.price} | {p.product_url}")
