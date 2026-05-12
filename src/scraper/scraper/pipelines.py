import csv
from pathlib import Path

import requests
from itemadapter import ItemAdapter


POSTERS_DIR = None


class PosterImagesPipeline:
    @classmethod
    def from_crawler(cls, crawler):
        obj = cls()
        obj.settings = crawler.settings
        return obj

    def open_spider(self, spider=None):
        self.posters_dir = Path(self.settings.get("IMAGES_STORE"))
        self.posters_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = self.settings.get("USER_AGENT")

    def close_spider(self, spider=None):
        self.session.close()

    def process_item(self, item, spider=None):
        adapter = ItemAdapter(item)
        tmdb_id = adapter["tmdb_id"]
        poster_url = adapter.get("poster_url")

        dest = self.posters_dir / f"{tmdb_id}.jpg"
        if dest.exists():
            return item

        try:
            resp = self.session.get(poster_url, timeout=10, allow_redirects=True)
            resp.raise_for_status()
            if len(resp.content) < 5000:
                raise Exception("Poster too small")
            dest.write_bytes(resp.content)
        except Exception as e:
            raise Exception(f"Poster download failed for {tmdb_id}: {e}")

        return item


class CsvExportPipeline:
    @classmethod
    def from_crawler(cls, crawler):
        obj = cls()
        obj.settings = crawler.settings
        return obj

    def open_spider(self, spider=None):
        output_path = Path(self.settings.get("IMAGES_STORE")).parent / "labels.csv"
        self.file = open(output_path, "w", newline="", encoding="utf-8")
        self.writer = csv.writer(self.file)
        self.writer.writerow(["tmdb_id", "title", "genres"])

    def close_spider(self, spider=None):
        self.file.close()

    def process_item(self, item, spider=None):
        adapter = ItemAdapter(item)
        genres = "|".join(adapter.get("genres", []))
        self.writer.writerow([adapter["tmdb_id"], adapter["title"], genres])
        return item
