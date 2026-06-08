"""Merkezi ayarlar.

Normal kullanimda SADECE iki yere dokunman gerekir:
  1) RAW_COOKIE  -> Trendyol'dan aldigin guncel cookie
  2) merchants.txt / --merchant -> hangi tedarikcileri cekecegin

Geri kalan ayarlar anti-ban icin guvenli varsayilanlarla geliyor.
"""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --------------------------------------------------------------------------
# Cookie
# --------------------------------------------------------------------------
# Trendyol'da DevTools (F12) > Network > herhangi bir apigw.trendyol.com istegine
# tikla > Request Headers > "Cookie:" satirini komple kopyala ve buraya yapistir.
# Suresi dolarsa istekler 403 doner -> cookie'yi yenile.
# Alternatif: TRENDYOL_COOKIE ortam degiskenini set et.
RAW_COOKIE = os.getenv(
    "TRENDYOL_COOKIE",
    "storefrontId=1; language=tr; countryCode=TR; hvtb=1; platform=web; anonUserId=0eaa1e30-4ed0-11f1-9356-a97e96a05df7; _gcl_au=1.1.1087189992.1778679096; _ga=GA1.1.673950538.1778679096; _twpid=tw.1778679095917.844570687651749187; _tt_enable_cookie=1; _ttp=01KRGRJ8YHAZCHJBQKQRE3T5AQ_.tt.1; pid=1300ce20-4ed0-11f1-afb1-4164ee36ae85; WebAbTesting=A_8-B_61-C_40-D_13-E_100-F_6-G_30-H_40-I_50-J_71-K_18-L_43-M_88-N_50-O_98-P_98-Q_58-R_54-S_99-T_57-U_86-V_76-W_69-X_32-Y_37-Z_67; OptanonAlertBoxClosed=2026-05-13T13:31:42.369Z; _ym_uid=1778679103690217815; _ym_d=1778679103; _fbp=fb.1.1778679102767.500069960269987341; navbarGenderId=2; VisitCount=1; AZ_SELECTED=false; sid=U36pZRt9tm; AbTesting=SFWDBSR_A-SFWDRS_A-STSBuynow_B-SFWDSFAG_B-SFWDTKV2_A-SFWDQL_B-STSImageSocialProof_A-STSRecoSocialProof_A-STSCouponV2_A-STSRecoRR_B-SFWDSAOFv2_B-SFWBFP_B-regGender_B-DynamicCard_B-SFWBPFF_B-WCBRecoSliderArrowIteration_B-SFWCSDC_B-ZZTest1_B-SFWBFPTF_B-WAccountMyOrdersReco_A-WAccEmpOrReco_B-SFWPRecoEngine_B-SFWPOtherSellerRedesign_B-WCBTyPlusBasketPopupOffer_B-SFWBFPA_B-SFWBSBHT_A-WSSEARCH_B-loginRegisterReverse_B-SFWCTYPassInfoInteration_B-SFWBOSMT_B-WSBROHIS_B-WSCOLLECTIOND_B-WSFAVORITES_A-WSHOMEPAGE_B-WSTOPRANK_B-SFWBHPSS_A-SFCWebShellMyPaymentMethods_B-WSC_B-PromotionSearch_A-WSSELLERHOME_B-WSSELLERPROFILE_B-WSFOLLOWINGSTORES_B-SFCWebShellSdAddress_A-SFWCCTASavingInfo_A-WSJ4OU_B-SFCWebShellSdBasket_B-WSPRECALL_B-WSPDP_B-SFWPCGiftProduct_B-SFWCAC_A-WSORDERCANCEL_B%7C1780947912%7C1300ce20-4ed0-11f1-afb1-4164ee36ae85; msearchAb=ABBSA_D-ABAdvertSlotPeriod_1-ABQR_B-ABSuggestionCorpusExpansion_B-ABSuggestionNI_B-ABPR_B-ABFSR_B-ABsr_b-ABTRR_B-ABKB_B-ABRRAIC_B-ABSuggestionNS_B-ABqrw_b; homepageAb=homepage%3AfirstComponent_V3_1-topWidgets_V1_1-componentSMHPLiveWidgetFix_V3_1-performanceSorting_V1_3-sectionBasedSorting_V2_1-widgetForecast_V1_1-segmentBasedSortingAsIs_V1_1-sectionBasedSortingAsIs_V1_1-widgetLayout_V2_2-widgetVersion_V1_2-segmentBasedSorting_V1_2-componentWebInSessionSorting_V1_1%2CnavigationSideMenu%3AsideMenu_V1_1%2CnavigationSection%3Asection_V1_1; WebAbDecider=ABKB_B-ABMRLO_B-ABres_B-ABBMSA_B-ABRRIn_B-ABSCB_B-ABSuggestionHighlight_B-ABBP_B-ABCatTR_B-ABSuggestionTermActive_A-ABAZSmartlisting_62-ABBH2_B-ABMB_B-ABMRF_1-ABARR_B-ABMA_B-ABSP_B-ABPastSearches_B-ABSuggestionJFYProducts_B-ABSuggestionQF_B-ABBadgeBoost_A-ABFilterRelevancy_1-ABSuggestionBadges_B-ABProductGroupTopPerformer_B-ABOpenFilterToggle_2-ABRR_2-ABBS_2-ABSuggestionPopularCTR_B; csrf-secret=4Wy5pdsmFF1sSPGXY6-XcSyf; __cf_bm=OrqXBIq8K3YqG5gZcyaagsxOkUhmCVA.xpE7H7TD47o-1780946112.6990983-1.0.1.1-hEewKtE5QDVD6DS6.YnUsJpB03w6heiS.rvTUpLnxhM0CsojQFRW6HEYNSBZD4fFNsbSMbvrJpkmeOWH7G87cJnwhBq3GYWXWjd25p_.czpyyZksvq3pmz.IYJAiITP5; _cfuvid=z7jk.1Q9Q4jniHi_lYGueo0u0FxbHrdpp3w3Gu54BBk-1780946112.6990983-1.0.1.1-KKZ8wPV.D7DP3BWEZJw1zuP6xpapS.WrOAQ4aotkECs; __cflb=04dToYCH9RsdhPpttDRHXoaqk1jEvnJbjQJ5LDsBpH; UserInfo=%7B%22Gender%22%3Anull%2C%22UserTypeStatus%22%3Anull%2C%22ForceSet%22%3Afalse%2C%22GenderId%22%3Anull%7D; cto_bundle=wZk09V9ZMyUyRk9EWkNmVlR2ZUhOYnphU3VYSEp1M3hoSnpKdUZlUEtnNlY3QTBxVWJudjZoaVdmTmppZ1ZuZnpteDVCS1MlMkI4T3RoYWlRNWdiemFWaWJBV1FmSGtudyUyRkJhdyUyRkdxY3k0aWVrQ2JsaWVHN2YyQzltTFdibXolMkJoWGlzSnU0ZzI; OptanonConsent=isGpcEnabled=0&datestamp=Mon+Jun+08+2026+22%3A16%3A21+GMT%2B0300+(T%C3%BCrkiye+Standart+Saati)&version=202402.1.0&browserGpcFlag=0&isIABGlobal=false&hosts=&genVendors=V77%3A0%2CV67%3A0%2CV79%3A0%2CV71%3A0%2CV69%3A0%2CV7%3A0%2CV5%3A0%2CV9%3A0%2CV1%3A0%2CV70%3A0%2CV3%3A0%2CV68%3A0%2CV78%3A0%2CV17%3A0%2CV76%3A0%2CV80%3A0%2CV16%3A0%2CV72%3A0%2CV10%3A0%2CV40%3A0%2C&consentId=ce786fe8-581b-47d8-9279-beb5a2e540b9&interactionCount=1&isAnonUser=1&landingPath=NotLandingPage&groups=C0002%3A1%2CC0004%3A1%2CC0003%3A1%2CC0005%3A1%2CC0001%3A1%2CC0007%3A1%2CC0009%3A1&AwaitingReconsent=false&geolocation=TR%3B06; ttcsid=1780946122410::CsASKkBQwmNMZ7W4W8vI.18.1780946245586.0::1.58298.61730::123165.10.86.238::47906.37.1400; ttcsid_CJ94PP3C77U0073JONJ0=1780946122409::NXa1MIXkgu4Rr47ri8pK.17.1780946245586.1; _ga_DBFTZS0GYC=GS2.1.s1780946122$o20$g1$t1780946246$j60$l0$h0; ty-lb-vid=L2Rpc2NvdmVyeS1zZmludC1jaGVja291dC1zZXJ2aWNlL3NkLWJhc2tldC1oaWdobGlnaHQvc3I6MzQ1OTNiOTY0ZDFkNzllOGYyMjZlYjI1NjVlZTVkMjA6MTc4MDk0NjI0NzoxOmpZN2Ywb2RMOW92UUlGNFdiejdNbWJFd3N6VitpWFR2SFV0ckhzbTArTVU9",
)

# --------------------------------------------------------------------------
# Proxy (opsiyonel) - sirket IP'sini korumak icin
# --------------------------------------------------------------------------
# Proxysiz baslayacagiz. Ileride residential proxy alinca SADECE burayi doldur
# (veya TRENDYOL_PROXY env degiskenini set et). Kod degisikligi GEREKMEZ.
# Format: "http://kullanici:sifre@host:port"
PROXY_URL = os.getenv("TRENDYOL_PROXY") or None

# True ise: proxy yokken 403/429/challenge gorulunce ANINDA durur (sirket IP'sini korur).
# Proxy varsa False yapip backoff ile devam edebilirsin.
FAIL_CLOSED = PROXY_URL is None

# --------------------------------------------------------------------------
# Anti-ban / hiz ayarlari
# --------------------------------------------------------------------------
IMPERSONATE = "chrome120"        # curl_cffi TLS/JA3 parmak izi
MIN_DELAY = 3.0                  # istekler arasi minimum bekleme (sn)
MAX_DELAY = 6.0                  # istekler arasi maksimum bekleme (sn)
REQUESTS_PER_SECOND = 0.25       # token-bucket tavani (~4 sn'de 1 istek)
TIMEOUT = 15                     # tek istek timeout (sn)
MAX_RETRY = 2                    # proxysiz modda DUSUK (fail-closed felsefesi)
BACKOFF_BASE = 3.0               # exponential backoff taban (sn)
BACKOFF_MAX = 60.0               # backoff tavani (sn)
DELAY_BETWEEN_MERCHANTS = 10.0   # bir tedarikciden digerine gecerken ekstra bekleme

# --------------------------------------------------------------------------
# Endpoint'ler
# --------------------------------------------------------------------------
# [DOGRULANMIS] Magaza metadata (header-information)
HEADER_INFO_URL = (
    "https://apigw.trendyol.com/discovery-storefront-trproductgw-service"
    "/api/seller-store/{merchant_id}/header-information"
)

# [DOGRULANMIS] Magaza urun listesi — mid=, pi=, os=1, channelId=1, storefrontId=1
# Yanit: { products: [...], total: N, _links: { next: "...?pi=1..." } }
PRODUCTS_URL = (
    "https://apigw.trendyol.com/discovery-sfint-search-service/api/search/products"
)

# Urun detay endpoint'i — .env dosyasindaki TRENDYOL_DETAIL_URL'den okunur.
# {product_id} kismini degistirme, program oraya ID'yi otomatik girer.
# [DOGRULANMIS] x-agentname: StorefrontProductGateway header'i gerekli
DETAIL_URL = os.getenv(
    "TRENDYOL_DETAIL_URL",
    "https://apigw.trendyol.com/discovery-storefront-trproductgw-service/api/component-read/component/{product_id}?channelId=1",
)
DETAIL_AGENT = "StorefrontProductGateway"  # x-agentname header degeri

CHANNEL_ID = 1
PAGE_SIZE = 24       # listeleme sayfa basi urun (DevTools'tan dogrula)
MAX_PAGES = 50       # guvenlik tavani (sonsuz donguyu engeller)

# Tamamlik esigi: toplanan urun, bildirilen sayinin bu oraninin altindaysa
# "incomplete" uyarisi log'lanir (shadow-ban olabilir).
COMPLETENESS_THRESHOLD = 0.5

# --------------------------------------------------------------------------
# Depolama
# --------------------------------------------------------------------------
DB_PATH = os.getenv("TRENDYOL_DB", "trendyol.db")
EXPORT_DIR = os.getenv("TRENDYOL_EXPORT_DIR", ".")
