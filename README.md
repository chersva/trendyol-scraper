# Trendyol Tedarikçi Ürün Toplama (API tabanlı)

Tedarikçilerin Trendyol mağazalarındaki ürünleri **JSON API** üzerinden toplar:
isim, açıklama, kategori breadcrumb, ölçüler, fiyat, satıcı, mağaza linki, ürün linki, barkod.

Tarayıcı (Selenium/UC) **kullanmaz** — sadece `curl_cffi` ile API çağırır. Bu, istek sayısını
10-50x azaltır (her sayfa = 1 istek, ~24 ürün) ve şirket IP'sine binen yükü düşürür.

> **Önemli:** API kullanmak IP-ban riskini **azaltır ama sıfırlamaz.** İstek hâlâ senin IP'nden
> çıkar. Proxysiz başlıyoruz; bu yüzden çok yavaş gidiyoruz ve ilk blok işaretinde **duruyoruz**
> (fail-closed). Şirket IP'sini garantilemek istiyorsan ileride `config.PROXY_URL` doldur.

---

## Kurulum (Windows / PowerShell)

```powershell
cd C:\Users\alibaran\Desktop\projects\trendyol-scraper
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## Phase 0 — Endpoint Recon (BAŞLAMADAN ÖNCE, tek seferlik)

Kod 2 endpoint'i **bilerek** (header-information + arama) kullanıyor; diğer 2'si `config.py`'de
**[VERIFY]** notuyla tahmini path olarak duruyor. Onları gerçekleriyle değiştirmen lazım:

1. Trendyol'da bir **tedarikçi mağaza sayfası** aç.
2. `F12` → **Network** sekmesi → üstten **Fetch/XHR** filtrele.
3. Sayfayı **aşağı kaydır** → `apigw.trendyol.com/...` istekleri belirir.
4. Şu ikisini bul ve `config.py`'ye yapıştır:
   - **Ürün listesi** isteği → `PRODUCTS_URL` + sayfa param'ı (`pi`, `size`?) + yanıttaki ürün dizisinin adı (`products`/`content`?).
   - Bir ürüne tıkla, açılan **ürün detay** isteği → `DETAIL_URL` + `category`/`attributes`/`description`/`barcode` alanlarının JSON yolu.
5. İstekteki **Cookie** satırını komple kopyalayıp `config.RAW_COOKIE`'ye yapıştır.

> `extract.py` savunmacı yazıldı (birçok olası anahtar adını dener), bu yüzden alan adlarını birebir
> bilmesen de büyük ihtimalle çalışır. Yine de `--dry-run` çıktısına bakıp doğrula.

---

## Kullanım

```powershell
# 1) CANARY: önce tek tedarikçide deneme koşusu (sadece 1 sayfa, detay yok)
python main.py --merchant 12345 --dry-run

# 2) Tek tedarikçi, uçtan uca (liste + detay)
python main.py --merchant 12345

# 3) merchants.txt'teki tüm tedarikçiler
python main.py --merchants merchants.txt

# 4) Toplanan veriyi Excel + CSV'ye aktar
python main.py --export
```

Çıktılar: `trendyol.db` (SQLite) + `trendyol_urunler.csv` + `trendyol_urunler.xlsx`.

---

## Güvenli çalışma kuralları (şirket IP'si proxysiz)

- **Önce `--dry-run`** ile dene. Temizse devam et.
- **Gece / mesai dışı** çalıştır.
- 403/429/captcha görülürse uygulama **kendiliğinden durur** — zorlama, **cookie'yi yenile** veya bekle.
- `config.py`'deki `MIN_DELAY`/`MAX_DELAY` değerlerini düşürme; gerekirse **artır**.
- Risk büyürse `config.PROXY_URL`'e residential proxy gir (kod hazır, başka değişiklik gerekmez).

---

## Dosya yapısı

| Dosya | Görev |
|---|---|
| `config.py` | Cookie, hız, proxy, endpoint'ler |
| `api_client.py` | curl_cffi + rate limit + retry + blok tespiti |
| `detect_block.py` | shadow-ban / challenge sinyalleri |
| `extract.py` | JSON ayıklama (savunmacı) |
| `models.py` | Store / Product / ProductDetail |
| `db.py` | SQLite şema + idempotent upsert + log |
| `crawl_store.py` | Phase 2: mağaza metadata |
| `crawl_products.py` | Phase 3: ürün listesi (paginated) |
| `crawl_detail.py` | Phase 4: ürün detay |
| `pipeline.py` | orchestrator (resume + fail-closed) |
| `export.py` | SQLite → CSV/Excel |
| `main.py` | CLI |

## Kapsam dışı (sonraya)
- Eşleştirme (kendi sistemin ile barkod/isim eşleme).
- Görsel URL'leri, varyant linkleri.
- Periyodik çalışma / scheduler.
