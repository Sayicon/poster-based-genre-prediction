import csv
import re
from pathlib import Path

import scrapy

from scraper.items import MovieItem

TMDB_BASE = "https://www.themoviedb.org"
POSTER_SIZE = "w500"


class TmdbIdSpider(scrapy.Spider):
    """Detail-only spider — reads movie IDs from a file, skips listing pages entirely.

    Listing pages trigger rate limits after ~600 films. This spider goes directly
    to /movie/{id} detail pages, which are rate-limited much more leniently.

    Usage:
        scrapy crawl tmdb_id -s IDS_FILE=/path/to/tmdb_movie_ids.txt
    """

    name = "tmdb_id"
    allowed_domains = ["www.themoviedb.org", "media.themoviedb.org"]

    custom_settings = {
        "CLOSESPIDER_ITEMCOUNT": 12000,
        "JOBDIR": "",  # kendi dedup'ımız var (labels.csv) — Scrapy'nin DupeFilter'ına gerek yok
    }

    def __init__(self, ids_file=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ids_file = ids_file

    async def start(self):
        if not self.ids_file or not Path(self.ids_file).exists():
            self.logger.error(f"ids_file not found: {self.ids_file}")
            return

        labels_path = self.settings.get("LABELS_PATH", "")
        seen_ids = set()
        if labels_path and Path(labels_path).exists():
            try:
                with open(labels_path, "r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        seen_ids.add(str(row["tmdb_id"]))
                self.logger.info(f"Skipping {len(seen_ids):,} already-scraped IDs")
            except Exception as e:
                self.logger.warning(f"Could not load seen IDs: {e}")

        ids = Path(self.ids_file).read_text(encoding="utf-8").splitlines()
        ids = [i.strip() for i in ids if i.strip() and i.strip() not in seen_ids]
        self.logger.info(f"Queuing {len(ids):,} detail page requests")

        for tmdb_id in ids:
            yield scrapy.Request(
                f"{TMDB_BASE}/movie/{tmdb_id}",
                callback=self.parse_detail,
                meta={"tmdb_id": tmdb_id},
            )

    def parse_detail(self, response):
        tmdb_id = response.meta["tmdb_id"]

        title = response.css("h2 > a::text").get(default="").strip()
        if not title:
            title = response.css('meta[property="og:title"]::attr(content)').get(default="").strip()
        if not title:
            return

        genres = response.css("span.genres a::text").getall()
        genres = [g.strip() for g in genres if g.strip()]
        if not genres:
            return

        poster_src = response.css('img[src*="media.themoviedb.org"]::attr(src)').get()
        if not poster_src:
            return

        poster_url = re.sub(r"/t/p/[^/]+/", f"/t/p/{POSTER_SIZE}/", poster_src)

        item = MovieItem()
        item["tmdb_id"] = tmdb_id
        item["title"] = title
        item["genres"] = genres
        item["poster_url"] = poster_url
        yield item
