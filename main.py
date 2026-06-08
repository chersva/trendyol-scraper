"""CLI giris noktasi.

Ornekler (PowerShell):
  python main.py --merchant 12345 --dry-run      # canary: sadece 1 sayfa, detay yok
  python main.py --merchant 12345                # tek tedarikci, ucdan uca
  python main.py --merchants merchants.txt       # dosyadaki tum tedarikciler
  python main.py --export                        # mevcut DB'yi CSV/Excel'e aktar
"""

from __future__ import annotations

import argparse
import logging
import sys

import config
import db
from api_client import ApiClient
from pipeline import run_merchants


def _read_merchants_file(path: str) -> list[str]:
    ids: list[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                ids.append(line)
    return ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trendyol tedarikci urun toplama (API tabanli)")
    parser.add_argument("--merchant", help="Tek tedarikci merchant_id")
    parser.add_argument("--merchants", help="Her satirda bir merchant_id olan dosya")
    parser.add_argument("--dry-run", action="store_true", help="Canary: sadece 1 sayfa, detay cekme")
    parser.add_argument("--export", action="store_true", help="DB'yi CSV/Excel'e aktar ve cik")
    parser.add_argument("--verbose", action="store_true", help="Detayli log")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.export:
        from export import export
        export()
        return 0

    merchant_ids: list[str] = []
    if args.merchant:
        merchant_ids.append(args.merchant.strip())
    if args.merchants:
        merchant_ids.extend(_read_merchants_file(args.merchants))

    if not merchant_ids:
        parser.error("En az --merchant veya --merchants vermelisin (ya da --export).")

    # cookie placeholder kontrolu
    if "storefrontId=1; language=tr; countryCode=TR;" == config.RAW_COOKIE.strip():
        print("! UYARI: config.RAW_COOKIE hala placeholder. Gercek cookie olmadan istekler 403 donebilir.")

    conn = db.connect(config.DB_PATH)
    client = ApiClient()

    try:
        run_merchants(client, conn, merchant_ids, dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("\nKullanici durdurdu. Veriler DB'de kayitli, tekrar calistirinca kaldigi yerden devam eder.")
    finally:
        conn.close()

    if not args.dry_run:
        print("\nDisa aktarmak icin: python main.py --export")
    return 0


if __name__ == "__main__":
    sys.exit(main())
