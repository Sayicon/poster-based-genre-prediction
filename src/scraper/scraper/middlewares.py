import random
import time

from curl_cffi import requests as cffi_requests
from scrapy.http import HtmlResponse


class CurlCffiMiddleware:
    """
    Scrapy'nin Python ssl downloader'ını curl_cffi ile değiştirir.
    Chrome'un TLS parmak izini (JA3) birebir taklit eder — TLS tabanlı bot
    tespitini (Cloudflare, TMDB vb.) atlatır.
    """

    def __init__(self, crawler):
        self._crawler = crawler
        self._session = cffi_requests.Session(impersonate="chrome124")

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def process_request(self, request):
        headers = {}
        for k, v in request.headers.items():
            key = k.decode() if isinstance(k, bytes) else k
            val = v[0].decode() if isinstance(v[0], bytes) else v[0]
            headers[key] = val

        try:
            r = self._session.get(
                request.url,
                headers=headers,
                timeout=20,
                allow_redirects=True,
            )
            # curl_cffi already decompresses — strip Content-Encoding so
            # Scrapy's HttpCompressionMiddleware doesn't try to decode again
            headers = {k: v for k, v in r.headers.items()
                       if k.lower() != "content-encoding"}
            return HtmlResponse(
                url=r.url,
                status=r.status_code,
                headers=headers,
                body=r.content,
                request=request,
            )
        except Exception as e:
            self._crawler.spider.logger.warning(f"curl_cffi error ({request.url}): {e}")
            return None  # Scrapy'nin kendi downloader'ına düş


class ExponentialBackoffMiddleware:
    """
    429 Too Many Requests handler with exponential backoff.
    Delays: 2s, 4s, 8s, 16s. Returns a retry Request on 429.
    Safe with CONCURRENT_REQUESTS=1.
    """

    MAX_RETRIES = 4

    @classmethod
    def from_crawler(cls, crawler):
        obj = cls()
        obj._crawler = crawler
        return obj

    def process_response(self, request, response):
        if response.status != 429:
            return response
        spider = self._crawler.spider
        retries = request.meta.get("_backoff_retries", 0)
        if retries >= self.MAX_RETRIES:
            spider.logger.error(f"429 max retries exhausted: {request.url}")
            return response
        delay = 2 ** (retries + 1) + random.uniform(0, 2)
        spider.logger.warning(
            f"429 — backoff {delay:.1f}s "
            f"(attempt {retries + 1}/{self.MAX_RETRIES}): {request.url}"
        )
        time.sleep(delay)
        retry = request.copy()
        retry.meta["_backoff_retries"] = retries + 1
        retry.dont_filter = True
        return retry

    def process_exception(self, request, exception):
        return None
