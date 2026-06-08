"""Trendyol Scraper — web arayuzu (Streamlit).

Calistirmak icin:
    streamlit run app.py
Tarayici otomatik acar: http://localhost:8501
"""

from __future__ import annotations

import os
import sys
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import streamlit as st

import config
import db
from api_client import ApiClient
from export import JOIN_QUERY
from pipeline import run_merchant

# --------------------------------------------------------------------------
st.set_page_config(page_title="Trendyol Scraper", page_icon="🛍️", layout="centered")
st.title("🛍️ Trendyol Mağaza Scraper")
st.caption("Tedarikçi mağazasındaki ürünleri toplar ve Excel'e aktarır.")
st.divider()

# --------------------------------------------------------------------------
# Giris alanlari
# --------------------------------------------------------------------------
merchant_id = st.text_input(
    "Mağaza ID",
    placeholder="örn. 106280",
    help=(
        "Trendyol'da tedarikçi mağaza sayfasının URL'sindeki merchantId= değeri.\n\n"
        "Örnek URL: trendyol.com/magaza/modatte?merchantId=**106280**\n"
        "→ buraya yazacağın değer: 106280"
    ),
)

cookie = st.text_area(
    "Cookie",
    height=130,
    placeholder="storefrontId=1; language=tr; countryCode=TR; ...",
    help=(
        "**Nasıl alınır:**\n\n"
        "1. Trendyol.com'u tarayıcıda aç (giriş yapmış olman lazım)\n"
        "2. **F12** → **Network** sekmesi → üstten **Fetch/XHR** filtrele\n"
        "3. Herhangi bir sayfaya git veya yenile — listede `apigw.trendyol.com` ile başlayan bir istek görünecek\n"
        "4. O isteğe tıkla → sağda **Request Headers** sekmesi → **Cookie:** satırını komple kopyala\n\n"
        "Cookie birkaç haftada bir yenilenmesi gerekebilir."
    ),
)

detail_url = st.text_input(
    "Detay URL  *(opsiyonel — açıklama, ölçü, barkod için)*",
    value=config.DETAIL_URL,
    help=(
        "Açıklama, tam kategori yolu, ölçüler ve barkod bu endpoint'ten geliyor.\n\n"
        "**Nasıl alınır:**\n\n"
        "1. Trendyol'da bir ürün sayfası aç\n"
        "2. F12 → Network → Fetch/XHR\n"
        "3. `apigw.trendyol.com` ile başlayan ve `productgw` içeren isteği bul "
        "(`marketing`, `seo`, `review`, `linking` içerenleri atla)\n"
        "4. O isteğin **Request URL**'ini kopyala\n"
        "5. URL'deki ürün ID numarasını `{product_id}` ile değiştir\n\n"
        "⚠️ `{product_id}` kısmını koru — program oraya ID'yi otomatik yazar.\n\n"
        "Boş bırakırsan: kategori yaprağı, marka ve kart özellikleri listeden alınır "
        "(açıklama ve tam breadcrumb olmaz)."
    ),
)

st.divider()

# --------------------------------------------------------------------------
# Calistir butonu
# --------------------------------------------------------------------------
can_run = bool(merchant_id.strip() and cookie.strip())
if not can_run:
    st.info("Çalıştırmak için Mağaza ID ve Cookie gir.")

run_btn = st.button(
    "▶  Çalıştır",
    disabled=not can_run,
    type="primary",
    use_container_width=True,
)

# --------------------------------------------------------------------------
# Scraper kosusu
# --------------------------------------------------------------------------
if run_btn:
    mid = merchant_id.strip()

    # Config'i kullanici girdisiyle eziyoruz (runtime override)
    config.RAW_COOKIE = cookie.strip()
    if detail_url.strip():
        config.DETAIL_URL = detail_url.strip()

    st.subheader("Çalışıyor...")
    log_box = st.empty()
    logs: list[str] = []

    def show_progress(msg: str) -> None:
        logs.append(msg)
        log_box.code("\n".join(logs[-100:]), language="")

    conn = db.connect(config.DB_PATH)
    client = ApiClient()
    run_error: Exception | None = None

    try:
        run_merchant(client, conn, mid, progress=show_progress)
    except Exception as exc:
        run_error = exc
        show_progress(f"\n!!! HATA: {exc}")

    # ---------- Export ----------
    if run_error is None:
        try:
            cur = conn.execute(
                "SELECT store_name FROM merchants WHERE merchant_id=?", (mid,)
            )
            row = cur.fetchone()
            store_name = row[0] if row else mid

            # Dosya adi: MağazaAdı_ID_sonuclar.xlsx
            safe = "".join(
                c if c.isalnum() or c in "- " else "_"
                for c in (store_name or mid)
            ).strip("_ ")
            out_name = f"{safe}_{mid}_sonuclar.xlsx"

            df = pd.read_sql_query(JOIN_QUERY, conn)
            buf = BytesIO()
            df.to_excel(buf, index=False, engine="openpyxl", sheet_name="urunler")
            buf.seek(0)

            st.success(f"✅ Tamamlandı — **{len(df)} ürün** toplandı.")
            st.download_button(
                label=f"⬇  {out_name}  indir",
                data=buf,
                file_name=out_name,
                mime=(
                    "application/vnd.openxmlformats-officedocument"
                    ".spreadsheetml.sheet"
                ),
                use_container_width=True,
            )

        except Exception as exc:
            st.error(f"Export hatası: {exc}")
    else:
        st.error(
            f"Scraper durdu: {run_error}\n\n"
            "Cookie süresi dolmuş olabilir — yeni cookie yapıştırıp tekrar dene."
        )

    conn.close()
