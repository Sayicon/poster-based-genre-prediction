import re

import scrapy

from scraper.items import MovieItem

TMDB_BASE = "https://www.themoviedb.org"
POSTER_SIZE = "w500"


class TmdbSpider(scrapy.Spider):
    name = "tmdb"
    allowed_domains = ["www.themoviedb.org", "media.themoviedb.org"]

    custom_settings = {
        "CLOSESPIDER_ITEMCOUNT": 12000,
    }

    def __init__(self, max_pages=500, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_ids = set()

    async def start(self):
        for page in range(1, self.max_pages + 1):
            url = f"{TMDB_BASE}/movie?page={page}"
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        seen_on_page = set()
        for href in response.css("a::attr(href)").getall():
            m = re.match(r"^/movie/(\d+)", href)
            if not m:
                continue
            tmdb_id = m.group(1)
            if tmdb_id in seen_on_page:
                continue
            seen_on_page.add(tmdb_id)
            if tmdb_id in self._seen_ids:
                continue
            self._seen_ids.add(tmdb_id)
            yield scrapy.Request(
                TMDB_BASE + href,
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

        # w300_and_h450_face → w500 ile değiştir
        poster_url = re.sub(r"/t/p/[^/]+/", f"/t/p/{POSTER_SIZE}/", poster_src)

        item = MovieItem()
        item["tmdb_id"] = tmdb_id
        item["title"] = title
        item["genres"] = genres
        item["poster_url"] = poster_url
        yield item
