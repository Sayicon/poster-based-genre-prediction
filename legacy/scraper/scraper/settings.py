from pathlib import Path

BOT_NAME = "scraper"

SPIDER_MODULES = ["scraper.spiders"]
NEWSPIDER_MODULE = "scraper.spiders"

ADDONS = {}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

ROBOTSTXT_OBEY = False

CONCURRENT_REQUESTS = 1
DOWNLOAD_DELAY = 8
RANDOMIZE_DOWNLOAD_DELAY = True

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 8
AUTOTHROTTLE_MAX_DELAY = 120
AUTOTHROTTLE_TARGET_CONCURRENCY = 0.5

COOKIES_ENABLED = True

ITEM_PIPELINES = {
    "scraper.pipelines.PosterImagesPipeline": 1,
    "scraper.pipelines.CsvExportPipeline": 2,
}

IMAGES_STORE = str(Path(__file__).resolve().parents[3] / "posters")

# Scrapy'nin kendi kuyruk checkpoint'i — spider durduğu yerden devam eder
JOBDIR = str(Path(__file__).resolve().parents[3] / ".scrapy_job")

DOWNLOADER_MIDDLEWARES = {
    "scraper.middlewares.CurlCffiMiddleware": 1,
    "scraper.middlewares.ExponentialBackoffMiddleware": 545,
}

RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504]

FEED_EXPORT_ENCODING = "utf-8"

REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
