"""Trendyol Scraper — web arayuzu (Streamlit).

Calistirmak icin:
    python -m streamlit run app.py
Tarayici otomatik acar: http://localhost:8501
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timedelta, timezone
from io import BytesIO
from urllib.parse import unquote_plus

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import streamlit as st

import config
import db
from api_client import ApiClient
from export import JOIN_QUERY
from pipeline import run_merchant

COOKIE_VALIDITY_DAYS = 21
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


# --------------------------------------------------------------------------
# Yardimci: .env okuma / yazma
# --------------------------------------------------------------------------
def _read_env() -> dict[str, str]:
    result: dict[str, str] = {}
    if not os.path.exists(ENV_PATH):
        return result
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                result[k.strip()] = v.strip()
    return result


def _save_to_env(key: str, value: str) -> None:
    lines: list[str] = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, encoding="utf-8") as f:
            lines = f.readlines()
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}\n")
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
    # dotenv'i yeniden yukle
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_PATH, override=True)
    except ImportError:
        pass


# --------------------------------------------------------------------------
# Cookie durum widget'i
# --------------------------------------------------------------------------
def _parse_cookie_date(raw_cookie: str) -> datetime | None:
    m = re.search(r"datestamp=([^&;]+)", raw_cookie)
    if not m:
        return None
    try:
        text = unquote_plus(m.group(1))
        dt = datetime.strptime(text[:15], "%a %b %d %Y")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _cookie_status(raw_cookie: str) -> None:
    dt = _parse_cookie_date(raw_cookie)
    if dt is None:
        st.info("Cookie tarihi okunamadı.")
        return
    expiry = dt + timedelta(days=COOKIE_VALIDITY_DAYS)
    days_left = (expiry - datetime.now(timezone.utc)).days
    if days_left > 7:
        st.success(
            f"✅ Cookie güncel — son güncelleme: {dt.strftime('%d %B %Y')} "
            f"· tahmini geçerlilik: {expiry.strftime('%d %B %Y')} (~{days_left} gün kaldı)"
        )
    elif days_left > 0:
        st.warning(
            f"⚠️ Cookie yakında dolacak — {expiry.strftime('%d %B %Y')} (~{days_left} gün kaldı). "
            "Bu hafta güncelle."
        )
    else:
        st.error(
            f"🚫 Cookie süresi dolmuş olabilir ({expiry.strftime('%d %B %Y')} geçti). "
            "Aşağıdan güncelle."
        )


# --------------------------------------------------------------------------
# Sayfa yapisi
# --------------------------------------------------------------------------
st.set_page_config(page_title="Trendyol Scraper", page_icon="🛍️", layout="centered")
st.title("🛍️ Trendyol Mağaza Scraper")
st.caption("Tedarikçi mağazasındaki ürünleri toplar ve Excel'e aktarır.")

# --------------------------------------------------------------------------
# AYARLAR
# --------------------------------------------------------------------------
with st.expander("⚙️ Ayarlar", expanded=False):

    st.markdown("---")

    # ---- Cookie ----
    st.markdown("#### 🍪 Cookie")
    st.markdown(
        "Program Trendyol'a istek atarken senin tarayıcı oturumunu kullanır. "
        "Bu bilgiye **cookie** denir. **Birkaç haftada bir yenilenmesi** gerekir."
    )

    cookie_ok = bool(config.RAW_COOKIE and len(config.RAW_COOKIE) > 50)
    if cookie_ok:
        _cookie_status(config.RAW_COOKIE)
    else:
        st.error("Cookie ayarlanmamış! Aşağıdan ekle.")

    use_default_cookie = st.checkbox(
        "Kayıtlı cookie'yi kullan (.env dosyasından)",
        value=cookie_ok,
        key="chk_cookie",
        help="İşaretliyken .env dosyasındaki cookie kullanılır. Kaldırırsan aşağıya yapıştırabilirsin.",
    )

    if not use_default_cookie:
        new_cookie = st.text_area(
            "Cookie değeri",
            height=100,
            placeholder="storefrontId=1; language=tr; ...",
            help=(
                "Nasıl alınır:\n"
                "1. Trendyol.com'u aç\n"
                "2. F12 → Network → Fetch/XHR\n"
                "3. Herhangi bir apigw.trendyol.com isteğine tıkla\n"
                "4. Request Headers → Cookie: satırını komple kopyala"
            ),
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Kalıcı Kaydet (.env)", key="save_cookie", use_container_width=True):
                if new_cookie.strip():
                    _save_to_env("TRENDYOL_COOKIE", new_cookie.strip())
                    config.RAW_COOKIE = new_cookie.strip()
                    st.success("Cookie .env dosyasına kaydedildi. Sayfayı yenile.")
                else:
                    st.warning("Cookie boş olamaz.")
        with col2:
            st.caption("Kalıcı kaydet → .env dosyasına yazar, bir daha girmene gerek kalmaz.")
        cookie_val = new_cookie.strip() if new_cookie.strip() else config.RAW_COOKIE
    else:
        cookie_val = config.RAW_COOKIE

    st.markdown("---")

    # ---- Detay URL ----
    st.markdown("#### 🔗 Detay URL")
    st.markdown(
        "Ürün açıklaması, kategori, ölçüler ve barkod bu endpoint'ten geliyor. "
        "Trendyol API'si değişmedikçe bu ayara dokunmana gerek yok."
    )

    use_default_detail = st.checkbox(
        "Kayıtlı Detay URL'ini kullan (.env dosyasından)",
        value=True,
        key="chk_detail",
        help="İşaretliyken .env veya varsayılan URL kullanılır.",
    )

    if not use_default_detail:
        new_detail = st.text_input(
            "Detay URL",
            value=config.DETAIL_URL,
            help=(
                "{product_id} kısmını değiştirme — program oraya ürün ID'sini otomatik yazar.\n\n"
                "Nasıl bulunur:\n"
                "1. Trendyol'da bir ürün sayfası aç\n"
                "2. F12 → Network → Fetch/XHR\n"
                "3. apigw.trendyol.com ile başlayan 'component-read' içeren isteği bul\n"
                "4. Request URL'ini kopyala, içindeki ID'yi {product_id} ile değiştir"
            ),
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Kalıcı Kaydet (.env)", key="save_detail", use_container_width=True):
                if new_detail.strip():
                    _save_to_env("TRENDYOL_DETAIL_URL", new_detail.strip())
                    config.DETAIL_URL = new_detail.strip()
                    st.success("Detay URL .env dosyasına kaydedildi.")
                else:
                    st.warning("URL boş olamaz.")
        with col2:
            st.caption("Kalıcı kaydet → .env dosyasına yazar.")
        detail_url_val = new_detail.strip() if new_detail.strip() else config.DETAIL_URL
    else:
        detail_url_val = config.DETAIL_URL
        st.code(config.DETAIL_URL, language="")

    st.markdown("---")

    # ---- Gelismis ----
    with st.expander("🔧 Gelişmiş Ayarlar (nadiren değişir)"):
        st.markdown(
            "Bu değerleri **yalnızca** Trendyol API'si değişirse düzenle. "
            "Yanlış değer girilirse program çalışmaz."
        )

        env_vals = _read_env()

        st.markdown("**x-agentname header değeri**")
        st.caption(
            "Detay isteğine eklenen özel header. "
            "Şu an doğrulanmış değer: `StorefrontProductGateway`"
        )
        new_agent = st.text_input(
            "x-agentname",
            value=env_vals.get("TRENDYOL_DETAIL_AGENT", config.DETAIL_AGENT),
            label_visibility="collapsed",
        )
        if st.button("💾 Kaydet", key="save_agent"):
            _save_to_env("TRENDYOL_DETAIL_AGENT", new_agent.strip())
            st.success("Kaydedildi.")

        st.markdown("**Ürün listesi endpoint'i**")
        st.caption(
            "Mağaza ürünlerinin listelendiği API. "
            "Şu an doğrulanmış: `discovery-sfint-search-service/api/search/products`"
        )
        new_products_url = st.text_input(
            "Products URL",
            value=env_vals.get("TRENDYOL_PRODUCTS_URL", config.PRODUCTS_URL),
            label_visibility="collapsed",
        )
        if st.button("💾 Kaydet", key="save_products_url"):
            _save_to_env("TRENDYOL_PRODUCTS_URL", new_products_url.strip())
            st.success("Kaydedildi.")

st.divider()

# --------------------------------------------------------------------------
# ANA ALAN: Mağaza ID + Çalıştır
# --------------------------------------------------------------------------
st.markdown("### Mağaza ID")
merchant_id = st.text_input(
    "Mağaza ID",
    placeholder="örn. 106280",
    label_visibility="collapsed",
    help=(
        "Trendyol'da tedarikçi mağaza sayfasının URL'sindeki merchantId= değeri.\n\n"
        "Örnek: trendyol.com/magaza/modatte?merchantId=**106280**"
    ),
)

cookie_ready = bool(cookie_val and len(cookie_val) > 50)
if not cookie_ready:
    st.error("⚠️ Cookie eksik — Ayarlar bölümünden ekle.")

can_run = bool(merchant_id.strip()) and cookie_ready

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
    config.RAW_COOKIE = cookie_val
    if detail_url_val:
        config.DETAIL_URL = detail_url_val

    st.divider()
    st.subheader("⏳ Çalışıyor...")
    st.caption(
        "İstekler arasında 3-6 saniye bekleniyor (IP ban riski azaltmak için). "
        "~100 ürünlük mağaza yaklaşık 10 dakika sürebilir."
    )

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

    if run_error is None:
        try:
            cur = conn.execute(
                "SELECT store_name FROM merchants WHERE merchant_id=?", (mid,)
            )
            row = cur.fetchone()
            store_name = row[0] if row else mid

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
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception as exc:
            st.error(f"Export hatası: {exc}")
    else:
        if "403" in str(run_error) or "challenge" in str(run_error).lower():
            st.error(
                "🚫 **Cookie süresi dolmuş veya IP engellendi.**\n\n"
                "Ayarlar bölümünden cookie'yi güncelle."
            )
        else:
            st.error(f"Hata: {run_error}")

    conn.close()

# --------------------------------------------------------------------------
# NASIL KULLANILIR
# --------------------------------------------------------------------------
with st.expander("ℹ️ Nasıl Kullanılır"):
    st.markdown("""
### Mağaza ID nereden bulunur?
Trendyol'da tedarikçi mağazasına git, URL'ye bak:
```
trendyol.com/magaza/modatte?merchantId=106280
                                        ^^^^^^
                                    bu sayı = Mağaza ID
```

---

### Cookie nedir, nasıl alınır?
Program Trendyol'a istek atarken senin tarayıcı oturumunu taklit eder.
Bu bilgiye **cookie** denir ve birkaç haftada bir yenilenmesi gerekir.

**Adımlar:**
1. Trendyol.com'u tarayıcıda aç (hesabına giriş yapmış ol)
2. **F12** → **Network** sekmesi → **Fetch/XHR** filtrele
3. Sayfayı yenile (F5)
4. Solda `apigw.trendyol.com` ile başlayan herhangi bir satıra tıkla
5. Sağda **Request Headers** → **Cookie:** satırını komple kopyala
6. Yukarıdaki **Ayarlar** bölümünden yapıştır → **Kalıcı Kaydet**

---

### Cookie ne zaman yenilenmeli?
- Program çalışınca log'da `403/challenge` mesajı çıkarsa
- Ayarlar bölümündeki cookie durum göstergesi ⚠️ veya 🚫 olursa

---

### Detay URL nedir?
Ürün açıklaması, tam kategori yolu, ölçüler ve barkod için ayrı bir API endpoint'i gerekiyor.
Şu an varsayılan değer doğrulanmış durumda — değiştirmene gerek yok.
API değişirse Ayarlar → Detay URL bölümünden güncelleyebilirsin.

---

### Kalıcı Kaydet ne yapar?
Girdiğin değeri proje klasöründeki `.env` dosyasına yazar.
Bir sonraki çalıştırmada otomatik okunur, tekrar girmen gerekmez.
    """)
