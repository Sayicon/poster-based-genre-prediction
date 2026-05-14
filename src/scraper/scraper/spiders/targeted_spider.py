import ast
import csv
import re
from pathlib import Path

import scrapy
from scrapy.exceptions import CloseSpider

from scraper.items import MovieItem

TMDB_BASE   = "https://www.themoviedb.org"
POSTER_SIZE = "w500"

TARGET_GENRES = {
    "Action", "Adventure", "Animation", "Comedy", "Crime",
    "Documentary", "Drama", "Family", "Fantasy", "History",
    "Horror", "Mystery", "Romance", "Science Fiction", "Thriller",
}


class TargetedSpider(scrapy.Spider):
    """Genre-gap-aware spider.

    Reads remaining IDs from tmdb_movie_ids.txt (same source as tmdb_id spider),
    but only accepts films whose genres fill at least one underrepresented slot.
    Stops automatically when all single-genre targets are met.

    Usage:
        scrapy crawl targeted \\
            -s IDS_FILE=/path/to/tmdb_movie_ids.txt \\
            -s LABELS_PATH=/path/to/labels.csv \\
            -s GAP_REPORT_PATH=/path/to/gap_report.csv
    """

    name = "targeted"
    allowed_domains = ["www.themoviedb.org", "media.themoviedb.org"]

    custom_settings = {
        "JOBDIR": "",  # kendi dedup'imiz var (labels.csv)
    }

    def __init__(self, ids_file=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ids_file = ids_file
        self.targets       = {}  # genre -> hedef sayi
        self.genre_counts  = {}  # genre -> simdiki sayi (labels.csv + bu seans)
        self.accepted      = 0
        self.skipped_genre = 0   # hedef turler zaten doluydu, atlandı

    # ------------------------------------------------------------------ startup

    async def start(self):
        gap_report_path = self.settings.get("GAP_REPORT_PATH", "")
        if not gap_report_path or not Path(gap_report_path).exists():
            self.logger.error("GAP_REPORT_PATH ayarlanmamis veya dosya yok")
            return

        # gap_report.csv'den tek-tur hedeflerini yukle
        with open(gap_report_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["type"] == "single" and int(row["deficit"]) > 0:
                    self.targets[row["combination"]] = int(row["target_count"])

        self.logger.info(f"Hedef turler ({len(self.targets)}): {list(self.targets)}")

        # labels.csv'den mevcut sayimlari yukle + gorulmus ID'leri topla
        labels_path = self.settings.get("LABELS_PATH", "")
        seen_ids = set()
        if labels_path and Path(labels_path).exists():
            with open(labels_path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    seen_ids.add(str(row["tmdb_id"]))
                    try:
                        genres = ast.literal_eval(row["genres"])
                    except Exception:
                        continue
                    for g in genres:
                        if g in TARGET_GENRES:
                            self.genre_counts[g] = self.genre_counts.get(g, 0) + 1

            self.logger.info(
                f"labels.csv: {len(seen_ids):,} gorulmus ID, "
                f"mevcut sayimlar: {dict(sorted(self.genre_counts.items()))}"
            )

        # labels_v2.csv varsa onu da say (devam edilen cekim)
        labels_v2 = Path(labels_path).parent / "labels_v2.csv" if labels_path else None
        if labels_v2 and labels_v2.exists():
            with open(labels_v2, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    tid = str(row["tmdb_id"])
                    if tid in seen_ids:
                        continue
                    seen_ids.add(tid)
                    try:
                        genres = ast.literal_eval(row["genres"])
                    except Exception:
                        continue
                    for g in genres:
                        if g in TARGET_GENRES:
                            self.genre_counts[g] = self.genre_counts.get(g, 0) + 1
            self.logger.info(f"labels_v2.csv de yuklendi. Toplam gorulmus: {len(seen_ids):,}")

        if self._all_targets_met():
            self.logger.info("Tum hedefler zaten karsilandi. Cekim gerekmiyor.")
            return

        self._log_remaining()

        if not self.ids_file or not Path(self.ids_file).exists():
            self.logger.error(f"ids_file bulunamadi: {self.ids_file}")
            return

        ids = Path(self.ids_file).read_text(encoding="utf-8").splitlines()
        ids = [i.strip() for i in ids if i.strip() and i.strip() not in seen_ids]
        self.logger.info(f"{len(ids):,} ID kuyruga alindi")

        for tmdb_id in ids:
            yield scrapy.Request(
                f"{TMDB_BASE}/movie/{tmdb_id}",
                callback=self.parse_detail,
                meta={"tmdb_id": tmdb_id},
            )

    # ------------------------------------------------------------------ helpers

    def _all_targets_met(self):
        return all(
            self.genre_counts.get(g, 0) >= t
            for g, t in self.targets.items()
        )

    def _should_accept(self, genres):
        """En az bir tur hala hedefin altindaysa filmi kabul et."""
        return any(
            g in self.targets and self.genre_counts.get(g, 0) < self.targets[g]
            for g in genres
        )

    def _log_remaining(self):
        remaining = {
            g: self.targets[g] - self.genre_counts.get(g, 0)
            for g in self.targets
            if self.genre_counts.get(g, 0) < self.targets[g]
        }
        self.logger.info(f"Kalan aciklar: {remaining}")

    # ------------------------------------------------------------------ parsing

    def parse_detail(self, response):
        if self._all_targets_met():
            raise CloseSpider("all_targets_met")

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

        if not self._should_accept(genres):
            self.skipped_genre += 1
            if self.skipped_genre % 200 == 0:
                self.logger.info(
                    f"[atlanan={self.skipped_genre}] Turler zaten hedefte, film atlanıyor"
                )
            return

        poster_src = response.css('img[src*="media.themoviedb.org"]::attr(src)').get()
        if not poster_src:
            return

        poster_url = re.sub(r"/t/p/[^/]+/", f"/t/p/{POSTER_SIZE}/", poster_src)

        # Sayaci guncelle
        for g in genres:
            if g in TARGET_GENRES:
                self.genre_counts[g] = self.genre_counts.get(g, 0) + 1

        self.accepted += 1
        if self.accepted % 200 == 0:
            self._log_remaining()

        item = MovieItem()
        item["tmdb_id"] = tmdb_id
        item["title"]   = title
        item["genres"]  = genres
        item["poster_url"] = poster_url
        yield item
