"""curl_cffi tabanli istek katmani + anti-ban.

Tum HTTP trafigi buradan gecer:
  - curl_cffi impersonate (gercek Chrome TLS/JA3 parmak izi)
  - token-bucket + random gecikme ile yavas/insansi hiz
  - retryable hatalarda exponential backoff
  - 403/429/challenge/HTML-yerine-JSON -> BlockedError (fail-closed)
"""

from __future__ import annotations

import logging
import random
import threading
import time

from curl_cffi import requests as cffi

import config
from detect_block import is_block_status, looks_like_html, text_has_challenge

logger = logging.getLogger("trendyol.api")


class BlockedError(Exception):
    """Blok/challenge sinyali. Proxysiz modda isi HEMEN durdururuz."""

    def __init__(self, reason: str, url: str = "", status: int | None = None) -> None:
        super().__init__(f"Blok tespit edildi: {reason} (status={status}) url={url}")
        self.reason = reason
        self.url = url
        self.status = status


def parse_cookie(raw: str) -> dict[str, str]:
    """'a=b; c=d' formatindaki cookie string'ini dict'e cevirir."""
    out: dict[str, str] = {}
    for part in raw.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


class _TokenBucket:
    def __init__(self, rate: float) -> None:
        self.rate = max(rate, 0.05)
        self.capacity = max(1.0, rate * 2)
        self.tokens = self.capacity
        self.updated_at = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> float:
        with self._lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.updated_at) * self.rate)
            self.updated_at = now
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return 0.0
            wait = (1.0 - self.tokens) / self.rate
            self.tokens = 0.0
            return wait


class ApiClient:
    RETRYABLE = {408, 425, 429, 500, 502, 503, 504}

    def __init__(self) -> None:
        self.cookies = parse_cookie(config.RAW_COOKIE)
        self.proxies = (
            {"http": config.PROXY_URL, "https": config.PROXY_URL} if config.PROXY_URL else None
        )
        self.session = cffi.Session()
        self._bucket = _TokenBucket(config.REQUESTS_PER_SECOND)
        self._last_request_at = 0.0
        self._pace_lock = threading.Lock()
        self.metrics: dict[str, object] = {
            "total": 0, "retries": 0, "blocked": 0, "failures": 0, "status": {},
        }
        if self.proxies:
            logger.info("Proxy aktif")
        else:
            logger.info("Proxy YOK - fail-closed mod (ilk blok isaretinde durur)")

    # -- ic yardimcilar -----------------------------------------------------
    def _headers(self, referer: str | None) -> dict[str, str]:
        # User-Agent/sec-ch-ua gibi parmak izi header'larini impersonate hallediyor;
        # ezmiyoruz. Sadece istege ozel olanlari ekliyoruz.
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": referer or "https://www.trendyol.com/",
            "Origin": "https://www.trendyol.com",
        }

    def _pace(self) -> None:
        with self._pace_lock:
            wait = self._bucket.acquire()
            if wait > 0:
                time.sleep(wait)
            gap = random.uniform(config.MIN_DELAY, config.MAX_DELAY)
            since = time.monotonic() - self._last_request_at
            if since < gap:
                time.sleep(gap - since)
            self._last_request_at = time.monotonic()

    def _backoff(self, attempt: int, resp=None) -> None:
        if resp is not None:
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                try:
                    time.sleep(min(float(retry_after), config.BACKOFF_MAX))
                    return
                except ValueError:
                    pass
        delay = min(config.BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 0.75), config.BACKOFF_MAX)
        time.sleep(delay)

    def _record_status(self, status: int) -> None:
        stat = self.metrics["status"]
        assert isinstance(stat, dict)
        stat[status] = stat.get(status, 0) + 1

    # -- ana metot ----------------------------------------------------------
    def get_text(self, url: str, referer: str | None = None) -> str:
        """Tam HTML sayfasini dondurur (urun sayfasi __NEXT_DATA__ icin)."""
        last_exc: Exception | None = None
        attempts = config.MAX_RETRY + 1
        headers = self._headers(referer)

        for attempt in range(attempts):
            self._pace()
            self.metrics["total"] = int(self.metrics["total"]) + 1  # type: ignore[index]
            try:
                resp = self.session.get(
                    url,
                    headers=headers,
                    cookies=self.cookies,
                    timeout=config.TIMEOUT,
                    proxies=self.proxies,
                    impersonate=config.IMPERSONATE,
                )
            except Exception as exc:
                last_exc = exc
                if attempt < attempts - 1:
                    self._backoff(attempt)
                    continue
                raise RuntimeError(f"Ag hatasi: {url}") from exc

            status = resp.status_code
            self._record_status(status)
            if status in (401, 403):
                raise BlockedError("403", url=url, status=status)
            if status == 429:
                if attempt < attempts - 1:
                    self._backoff(attempt, resp)
                    continue
                raise BlockedError("429", url=url, status=status)
            if status >= 400:
                raise RuntimeError(f"HTTP {status}: {url}")
            return resp.text or ""

        raise RuntimeError(f"Istek basarisiz: {url}") from last_exc

    def get_json(
        self,
        url: str,
        params: dict | None = None,
        referer: str | None = None,
        extra_headers: dict | None = None,
    ) -> dict:
        """Tek GET istegi -> parse edilmis JSON. Blok halinde BlockedError firlatir."""
        last_exc: Exception | None = None
        attempts = config.MAX_RETRY + 1
        headers = {**self._headers(referer), **(extra_headers or {})}

        for attempt in range(attempts):
            self._pace()
            self.metrics["total"] = int(self.metrics["total"]) + 1  # type: ignore[index]
            try:
                resp = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    cookies=self.cookies,
                    timeout=config.TIMEOUT,
                    proxies=self.proxies,
                    impersonate=config.IMPERSONATE,
                )
            except Exception as exc:  # ag/timeout hatasi
                last_exc = exc
                logger.warning("ag hatasi (deneme %s): %s", attempt + 1, exc)
                if attempt < attempts - 1:
                    self.metrics["retries"] = int(self.metrics["retries"]) + 1  # type: ignore[index]
                    self._backoff(attempt)
                    continue
                self.metrics["failures"] = int(self.metrics["failures"]) + 1  # type: ignore[index]
                raise RuntimeError(f"Ag hatasi: {url}") from exc

            status = resp.status_code
            self._record_status(status)
            text = resp.text or ""

            # --- NET BLOK: 401/403 veya govdede challenge -> hemen dur ---
            if status in (401, 403) or text_has_challenge(text):
                self.metrics["blocked"] = int(self.metrics["blocked"]) + 1  # type: ignore[index]
                raise BlockedError("403/challenge", url=url, status=status)

            # --- 429 / 5xx: retryable ---
            if status == 429 or status in self.RETRYABLE:
                if attempt < attempts - 1:
                    self.metrics["retries"] = int(self.metrics["retries"]) + 1  # type: ignore[index]
                    self._backoff(attempt, resp)
                    continue
                # denemeler bitti
                if status == 429:
                    self.metrics["blocked"] = int(self.metrics["blocked"]) + 1  # type: ignore[index]
                    raise BlockedError("429 rate limit", url=url, status=status)
                self.metrics["failures"] = int(self.metrics["failures"]) + 1  # type: ignore[index]
                raise RuntimeError(f"HTTP {status}: {url}")

            if status >= 400:
                self.metrics["failures"] = int(self.metrics["failures"]) + 1  # type: ignore[index]
                raise RuntimeError(f"HTTP {status}: {url}")

            # --- 2xx ama JSON yerine HTML -> shadow-ban/challenge ---
            if looks_like_html(text):
                self.metrics["blocked"] = int(self.metrics["blocked"]) + 1  # type: ignore[index]
                raise BlockedError("HTML-yerine-JSON", url=url, status=status)

            try:
                return resp.json()
            except Exception as exc:
                raise RuntimeError(f"JSON parse hatasi: {url}: {exc}") from exc

        raise RuntimeError(f"Istek basarisiz: {url}") from last_exc

    def metrics_summary(self) -> str:
        m = self.metrics
        return (
            f"istek={m['total']} retry={m['retries']} blok={m['blocked']} "
            f"hata={m['failures']} status={m['status']}"
        )
