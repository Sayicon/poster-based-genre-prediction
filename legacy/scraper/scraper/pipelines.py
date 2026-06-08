import csv
from io import BytesIO
from pathlib import Path

import requests
from itemadapter import ItemAdapter
from PIL import Image


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
            resp = self.session.get(poster_url, timeout=20, allow_redirects=True)
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content))
            w, h = img.size
            if w < 100 or h < 140:
                raise Exception(f"Poster too small: {w}x{h}")
            dest.write_bytes(resp.content)
        except Exception as e:
            # Poster indirilemedi — label yine de CSV'ye yazılır, Phase 2'de filtrelenir
            if spider:
                spider.logger.warning(f"Poster skip ({tmdb_id}): {e}")

        return item


class CsvExportPipeline:
    @classmethod
    def from_crawler(cls, crawler):
        obj = cls()
        obj.settings = crawler.settings
        return obj

    def open_spider(self, spider=None):
        labels_path = self.settings.get("LABELS_PATH")
        if labels_path:
            output_path = Path(labels_path)
        else:
            output_path = Path(self.settings.get("IMAGES_STORE")).parent / "labels.csv"
        file_exists = output_path.exists() and output_path.stat().st_size > 0

        self._seen_ids = set()
        if file_exists:
            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        self._seen_ids.add(row["tmdb_id"])
            except Exception:
                pass

        self.file = open(output_path, "a", newline="", encoding="utf-8")
        self.writer = csv.writer(self.file)
        if not file_exists:
            self.writer.writerow(["tmdb_id", "title", "genres"])

    def close_spider(self, spider=None):
        self.file.close()

    def process_item(self, item, spider=None):
        adapter = ItemAdapter(item)
        tmdb_id = adapter["tmdb_id"]
        if tmdb_id in self._seen_ids:
            return item
        self._seen_ids.add(tmdb_id)
        genres = "|".join(adapter.get("genres", []))
        self.writer.writerow([tmdb_id, adapter["title"], genres])
        self.file.flush()
        return item
