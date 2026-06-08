"""Phase 5: SQLite -> CSV + Excel disa aktarim.

merchants + products + product_details tablolarini birlestirip tek tabloya dokar.
"""

from __future__ import annotations

import os
import sqlite3

import pandas as pd

import config

JOIN_QUERY = """
SELECT
    m.merchant_id                 AS magaza_kodu,
    m.store_name                  AS magaza_adi,
    m.store_url                   AS magaza_linki,
    p.product_id                  AS urun_id,
    p.name                        AS urun_adi,
    d.category_path               AS kategori,
    d.description                 AS aciklama,
    d.dimensions                  AS olculer,
    p.price                       AS fiyat,
    p.original_price              AS liste_fiyati,
    p.seller_name                 AS satici,
    p.product_url                 AS urun_linki,
    COALESCE(d.barcode, p.barcode) AS barkod,
    d.brand                       AS marka,
    d.attributes_json             AS ozellikler_json
FROM products p
LEFT JOIN merchants m       ON m.merchant_id = p.merchant_id
LEFT JOIN product_details d ON d.product_id = p.product_id
ORDER BY p.merchant_id, p.product_id
"""


def export(db_path: str = config.DB_PATH, out_dir: str = config.EXPORT_DIR) -> tuple[str, str]:
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(JOIN_QUERY, conn)
    finally:
        conn.close()

    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "trendyol_urunler.csv")
    xlsx_path = os.path.join(out_dir, "trendyol_urunler.xlsx")

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    df.to_excel(xlsx_path, index=False, engine="openpyxl", sheet_name="urunler")

    print(f"{len(df)} satir disa aktarildi:")
    print(f"  {csv_path}")
    print(f"  {xlsx_path}")
    return csv_path, xlsx_path


if __name__ == "__main__":
    export()
