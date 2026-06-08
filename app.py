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

COOKIE_VALIDITY_DAYS = 21  # Trendyol cookie'si genellikle ~3 hafta gecerli


def _parse_cookie_date(raw_cookie: str) -> datetime | None:
    """OptanonConsent icindeki datestamp'i okur. Bulamazsa None doner."""
    m = re.search(r"datestamp=([^&;]+)", raw_cookie)
    if not m:
        return None
    try:
        # URL-encoded: "Mon+Jun+08+2026+22%3A16%3A21+GMT%2B0300" -> "Mon Jun 08 2026 ..."
        text = unquote_plus(m.group(1))
        # "Mon Jun 08 2026 22:16:21 GMT+0300" -> parse sadece tarih kismini aliyoruz
        dt = datetime.strptime(text[:15], "%a %b %d %Y")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _cookie_status_widget(raw_cookie: str) -> None:
    """Cookie tarihini ve tahmini gecerlilik durumunu gosterir."""
    dt = _parse_cookie_date(raw_cookie)
    if dt is None:
        st.info("Cookie tarihi okunamadı — `.env` dosyasındaki cookie güncel mi kontrol et.")
        return

    expiry = dt + timedelta(days=COOKIE_VALIDITY_DAYS)
    now = datetime.now(timezone.utc)
    days_left = (expiry - now).days

    update_str = dt.strftime("%d %B %Y")
    expiry_str = expiry.strftime("%d %B %Y")

    if days_left > 7:
        st.success(
            f"✅ Cookie güncel  \n"
            f"**Son güncelleme:** {update_str}  \n"
            f"**Tahmini son geçerlilik tarihi:** {expiry_str} (~{days_left} gün kaldı)"
        )
    elif days_left > 0:
        st.warning(
            f"⚠️ Cookie yakında dolacak  \n"
            f"**Son güncelleme:** {update_str}  \n"
            f"**Tahmini son geçerlilik tarihi:** {expiry_str} (**{days_left} gün kaldı**) — "
            f"bu hafta güncellemeyi planla."
        )
    else:
        st.error(
            f"🚫 Cookie süresi dolmuş olabilir  \n"
            f"**Son güncelleme:** {update_str}  \n"
            f"**Tahmini son geçerlilik tarihi:** {expiry_str} (geçti)  \n"
            f"Aşağıdaki adımlarla cookie'yi güncelle."
        )


# --------------------------------------------------------------------------
st.set_page_config(page_title="Trendyol Scraper", page_icon="🛍️", layout="centered")
st.title("🛍️ Trendyol Mağaza Scraper")
st.caption("Tedarikçi mağazasındaki ürünleri toplar ve Excel'e aktarır.")

# --------------------------------------------------------------------------
# YÖNETİCİ NOTU — cookie dolunca buraya bakılsın
# --------------------------------------------------------------------------
with st.expander("⚙️ Yönetici: Cookie / API Ayarları (burayı oku)"):
    st.markdown("""
### Cookie nedir, neden lazım?
Program Trendyol'a istek atarken "sen kimsin?" sorusuna senin tarayıcı oturumunla cevap verir.
Bu oturum bilgisine **cookie** denir. **Birkaç haftada bir** süresi dolar ve güncellenmesi gerekir.

---

### Cookie süresi dolunca ne olur?
Program çalıştırılınca log'da şu mesaj çıkar:
```
!!! BLOK: Blok tespit edildi: 403/challenge
```
Bu görününce aşağıdaki adımları izle.

---

### Cookie nasıl güncellenir?

1. **Trendyol.com**'u tarayıcıda aç ve hesabına giriş yap
2. Klavyede **F12**'ye bas (geliştirici araçları açılır)
3. Üstten **Network** sekmesine tıkla
4. Hemen yanındaki filtreden **Fetch/XHR**'ı seç
5. Trendyol'da herhangi bir sayfaya git veya sayfayı yenile (F5)
6. Solda çıkan listeden `apigw.trendyol.com` ile başlayan herhangi bir satıra tıkla
7. Sağda **Request Headers** sekmesine tıkla
8. **Cookie:** yazan satırı bul — satırın tüm değerini kopyala (çok uzun olabilir, hepsi lazım)
9. Proje klasöründeki `.env` dosyasını Not Defteri ile aç
10. `TRENDYOL_COOKIE=` kısmından sonrasını silip yeni cookie'yi yapıştır
11. Kaydet — bir sonraki çalıştırmada yeni cookie kullanılır

---

### Detay URL nedir?
Açıklama, tam kategori yolu, ölçüler ve barkod için detay endpoint'i gerekiyor.
Şu an bu alan ayarlanmamış, program çalışıyor ama o sütunlar boş geliyor.

**Detay URL'i nasıl bulunur:**
1. Trendyol'da bir ürün sayfası aç
2. F12 → Network → Fetch/XHR
3. `apigw.trendyol.com` ile başlayan ve `productgw` içeren isteği bul
   (`marketing`, `seo`, `review`, `linking` içerenleri atla)
4. O isteğin **Request URL**'ini kopyala
5. URL içindeki ürün ID numarasını `{product_id}` ile değiştir
6. `.env` dosyasında `TRENDYOL_DETAIL_URL=` satırına yapıştır

---

### Mağaza ID nereden bulunur?
Trendyol'da tedarikçi mağazasına git, URL'ye bak:
```
trendyol.com/magaza/modatte?merchantId=106280
                                        ^^^^^^
                                    bu sayı = Mağaza ID
```
    """)

    st.markdown("### Cookie Durumu")
    _cookie_status_widget(config.RAW_COOKIE)

    st.info(
        "`.env` dosyası proje klasöründe bulunur. "
        "Not Defteri ile açılır, kaydet ve programı tekrar çalıştır — başka bir şey gerekmez."
    )

st.divider()

# --------------------------------------------------------------------------
# Kullanici girisi: sadece magaza ID
# --------------------------------------------------------------------------
st.markdown("### Mağaza ID gir ve çalıştır")

merchant_id = st.text_input(
    "Mağaza ID",
    placeholder="örn. 106280",
    label_visibility="collapsed",
)

st.caption(
    "Mağaza ID'yi bulmak için: Trendyol'da tedarikçi mağazasına git → "
    "URL'de `merchantId=` kısmındaki sayıyı kopyala."
)

# Cookie yuklendi mi kontrol et
cookie_ok = bool(config.RAW_COOKIE and len(config.RAW_COOKIE) > 50)
if not cookie_ok:
    st.error(
        "Cookie ayarlanmamış! Yukarıdaki **Yönetici: Cookie / API Ayarları** bölümünü aç ve "
        "talimatları izleyerek `.env` dosyasına cookie ekle."
    )

can_run = bool(merchant_id.strip()) and cookie_ok

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

    st.divider()
    st.subheader("⏳ Çalışıyor...")
    st.caption(
        "İstekler arasında 3-6 saniye bekleniyor (ban riski azaltmak için). "
        "112 ürünlük bir mağaza ~10 dakika sürebilir."
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

    # ---------- Export ----------
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
                mime=(
                    "application/vnd.openxmlformats-officedocument"
                    ".spreadsheetml.sheet"
                ),
                use_container_width=True,
            )

        except Exception as exc:
            st.error(f"Export hatası: {exc}")

    else:
        if "403" in str(run_error) or "challenge" in str(run_error).lower():
            st.error(
                "🚫 **Cookie süresi dolmuş veya IP engellendi.**\n\n"
                "Yukarıdaki **Yönetici: Cookie / API Ayarları** bölümünü aç, "
                "cookie güncelleme adımlarını izle."
            )
        else:
            st.error(f"Hata: {run_error}")

    conn.close()
