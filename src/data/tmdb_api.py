"""TMDB resmî API ile dengeli, kombinasyon-farkında film + poster toplama.

Neden API? HTML kazıma (legacy/scraper) ban yiyordu (targeted run'da 9.619×429,
864 film kaybı — bkz. BULGULAR.md). Resmî JSON API ücretsiz, günlük limiti yok,
~40-50 istek/s'ye izin veriyor.

Verimlilik: /discover/movie her filmin `genre_ids` ve `poster_path`'ini TEK istekte
döndürür. Yani multi-label etiketleri bedavaya alır, poster'i SADECE kabul ettiğimiz
filmler için indiririz (eski spider önce sayfayı indirip sonra atıyordu → ~%90 israf).

Kimlik doğrulama (ikisinden biri):
  - TMDB_API_KEY  : v3 API key (query param ?api_key=...)
  - TMDB_BEARER   : v4 read access token (Authorization: Bearer ...)

Kullanım (script):
    python -m src.data.tmdb_api --out /path/to/DATA_ROOT --per-genre 2500 --min-votes 30

Kullanım (Colab):
    import os
    from google.colab import userdata
    os.environ["TMDB_API_KEY"] = userdata.get("TMDB_API_KEY")
    from src.data.tmdb_api import collect_balanced, download_posters, save_labels
"""

from __future__ import annotations

import argparse
import math
import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

API_BASE   = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p"


def _load_dotenv():
    """Proje kökündeki .env'i (varsa) os.environ'a yükler. Mevcut değişkenleri EZMEZ
    (Colab'da userdata ile set edilenler korunur)."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and val and key not in os.environ:
            os.environ[key] = val


_load_dotenv()

# Projedeki 15 hedef tür (TMDB genre id -> ad). Music/TV Movie/War/Western dışarıda.
GENRE_ID_TO_NAME = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 80: "Crime",
    99: "Documentary", 18: "Drama", 10751: "Family", 14: "Fantasy", 36: "History",
    27: "Horror", 9648: "Mystery", 10749: "Romance", 878: "Science Fiction", 53: "Thriller",
}
NAME_TO_GENRE_ID = {v: k for k, v in GENRE_ID_TO_NAME.items()}

# Tüm türler varsayılan olarak per_genre hedefine eşit. Belirli bir türü farklı
# tutmak istersen caps ile override edilir (örn. caps={"Drama": 2000}).
DEFAULT_CAPS = {}

# En az veriden çok veriye doğru çekersek, az türlerin filmleri çok türlerin
# sayaçlarını da doldurur → baskın türler doğal olarak erken dolup kapanır.
SCARCITY_ORDER = [
    "History", "Mystery", "Animation", "Fantasy", "Science Fiction", "Family",
    "Horror", "Adventure", "Documentary", "Crime", "Romance", "Action",
    "Thriller", "Comedy", "Drama",
]

# Baskın türler — seçimde "yolcu" olarak önceliği en sona atılır (overshoot azaltma).
COMMON_GENRES = {"Drama", "Comedy"}


# --------------------------------------------------------------------------- HTTP

def _auth(session: requests.Session) -> dict:
    """Bearer varsa header'a koy; yoksa boş dön (api_key query param ile gidilir)."""
    bearer = os.environ.get("TMDB_BEARER", "").strip()
    if bearer:
        session.headers["Authorization"] = f"Bearer {bearer}"
    return {}


def _get(session: requests.Session, path: str, params: dict, max_retries: int = 5) -> dict:
    """GET + 429/5xx için saygılı backoff. Başarısızsa boş dict döner."""
    # Bearer (v4) varsa header'dan gider; yoksa api_key (v3) query param'a eklenir.
    if not os.environ.get("TMDB_BEARER", "").strip():
        api_key = os.environ.get("TMDB_API_KEY", "").strip()
        if api_key:
            params = {**params, "api_key": api_key}
    url = f"{API_BASE}{path}"
    for attempt in range(max_retries):
        try:
            r = session.get(url, params=params, timeout=20)
        except requests.RequestException as e:
            time.sleep(1.5 * (attempt + 1))
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            wait = float(r.headers.get("Retry-After", 1)) + 0.5
            time.sleep(wait)
            continue
        if 500 <= r.status_code < 600:
            time.sleep(1.5 * (attempt + 1))
            continue
        # 401/404 vb. — tekrar denemenin anlamı yok
        r.raise_for_status()
        return {}
    return {}


# ----------------------------------------------------------------------- discover

def discover_page(session, genre_id, page, min_votes, sort_by="popularity.desc",
                  language="en-US"):
    """Tek discover sayfası (20 film). Ham TMDB film kayıtlarını döndürür."""
    data = _get(session, "/discover/movie", {
        "with_genres": genre_id,
        "sort_by": sort_by,
        "vote_count.gte": min_votes,
        "include_adult": "false",
        "include_video": "false",
        "language": language,
        "page": page,
    })
    return data.get("results", []), data.get("total_pages", 0)


def _target_genres(genre_ids):
    """Filmin tür id listesinden sadece 15 hedef türü ada çevirir."""
    return [GENRE_ID_TO_NAME[g] for g in genre_ids if g in GENRE_ID_TO_NAME]


# --------------------------------------------------------------- havuz + dengeli seçim

def build_pool(targets, min_votes=30, pool_factor=1.5, max_pages_cap=500,
               sort_by="popularity.desc", language="en-US", verbose=True):
    """Her tür için discover ile dedupe edilmiş aday havuzu kurar.

    Rare türlerin hedefe ulaşabilmesi için her türde hedefin ~pool_factor katı aday
    çekilir. Dönüş: dict tmdb_id -> {title, genres(list), poster_path}
    """
    session = requests.Session()
    session.headers["User-Agent"] = "film-genre-project/0.1"
    _auth(session)

    pool = {}
    for genre in SCARCITY_ORDER:
        gid = NAME_TO_GENRE_ID[genre]
        pages_needed = min(max_pages_cap, math.ceil(targets[genre] * pool_factor / 20))
        page, total_pages, added = 1, pages_needed, 0
        while page <= min(pages_needed, total_pages):
            results, total_pages = discover_page(session, gid, page, min_votes,
                                                 sort_by=sort_by, language=language)
            if not results:
                break
            for m in results:
                tid = m.get("id")
                if tid is None or tid in pool or not m.get("poster_path"):
                    continue
                genres = _target_genres(m.get("genre_ids", []))
                if not genres:
                    continue
                pool[tid] = {
                    "title": (m.get("title") or m.get("original_title") or "").strip(),
                    "genres": genres,
                    "poster_path": m["poster_path"],
                }
                added += 1
            page += 1
        if verbose:
            print(f"  havuz [{genre:16s}] {pages_needed:3d} sayfa -> +{added:5d} yeni, "
                  f"havuz toplam={len(pool):6d}")
    return pool


def select_balanced(pool, targets, verbose=True):
    """Havuzdan eksiklik-güdümlü greedy ile dengeli alt-küme seçer.

    Her adımda en eksik tür seçilir; o türü içeren ve EN AZ tür taşıyan film eklenir
    (overshoot minimize). Multi-label'da tam denge imkânsızdır ama bu yöntem baskın
    türlerin "yolcu" olarak şişmesini ciddi biçimde azaltır.

    Dönüş: (DataFrame[tmdb_id,title,genres,poster_path], counts)
    """
    genre_films = {g: [] for g in targets}
    for fid, info in pool.items():
        gs = info["genres"]
        n = len(gs)
        penalty = sum(1 for g in gs if g in COMMON_GENRES)  # baskin yolcuyu sona at
        for g in gs:
            if g in genre_films:
                genre_films[g].append((n, penalty, fid))
    for g in genre_films:
        genre_films[g].sort()           # (tur sayisi, baskin-yolcu) -> az overshoot

    ptr = {g: 0 for g in targets}
    counts = Counter()
    selected = {}
    exhausted = set()

    while True:
        deficits = [(targets[g] - counts[g], g) for g in targets
                    if g not in exhausted and counts[g] < targets[g]]
        if not deficits:
            break
        deficits.sort(reverse=True)     # en eksik tür önce
        g = deficits[0][1]

        lst = genre_films[g]
        i = ptr[g]
        while i < len(lst) and lst[i][2] in selected:
            i += 1
        if i >= len(lst):
            exhausted.add(g)
            ptr[g] = i
            continue
        fid = lst[i][2]
        ptr[g] = i + 1

        info = pool[fid]
        selected[fid] = info
        for gg in info["genres"]:
            counts[gg] += 1

    if verbose:
        print("\nTür başına nihai sayım (seçilen):")
        for g in SCARCITY_ORDER:
            mark = "" if counts[g] >= targets[g] else "  <- hedef alti (havuz yetersiz)"
            print(f"  {g:16s} {counts[g]:5d} / {targets[g]}{mark}")
        print(f"Toplam seçilen film: {len(selected)}")

    rows = [{"tmdb_id": tid, **v} for tid, v in selected.items()]
    return pd.DataFrame(rows), counts


def collect_balanced(per_genre=2500, min_votes=30, caps=None, pool_factor=1.5,
                     max_pages=500, language="en-US", verbose=True):
    """Havuz kur + dengeli seç. Dönüş: DataFrame[tmdb_id,title,genres,poster_path]."""
    caps = {**DEFAULT_CAPS, **(caps or {})}
    targets = {g: caps.get(g, per_genre) for g in SCARCITY_ORDER}
    if verbose:
        print("== 1/2 aday havuzu kuruluyor ==")
    pool = build_pool(targets, min_votes=min_votes, pool_factor=pool_factor,
                      max_pages_cap=max_pages, language=language, verbose=verbose)
    if verbose:
        print(f"\n== 2/2 dengeli seçim (havuz={len(pool)}) ==")
    df, _ = select_balanced(pool, targets, verbose=verbose)
    return df


# --------------------------------------------------------------------- poster indir

def _download_one(args):
    poster_path, dest, size = args
    if dest.exists():
        return True
    url = f"{IMAGE_BASE}/{size}{poster_path}"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200 and r.content:
            dest.write_bytes(r.content)
            return True
    except requests.RequestException:
        pass
    return False


def download_posters(df, posters_dir, size="w500", workers=16, verbose=True):
    """Seçilen filmlerin posterlerini {tmdb_id}.jpg olarak indirir (resumable, threaded)."""
    posters_dir = Path(posters_dir)
    posters_dir.mkdir(parents=True, exist_ok=True)
    tasks = [
        (row.poster_path, posters_dir / f"{row.tmdb_id}.jpg", size)
        for row in df.itertuples(index=False)
    ]
    ok = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_download_one, t) for t in tasks]
        for i, f in enumerate(as_completed(futures), 1):
            ok += bool(f.result())
            if verbose and i % 500 == 0:
                print(f"  poster {i}/{len(tasks)} indirildi (başarılı: {ok})")
    if verbose:
        print(f"Poster indirme bitti: {ok}/{len(tasks)} başarılı")
    return ok


# ------------------------------------------------------------------------ kaydet

def save_labels(df, path):
    """labels.csv ile aynı format: tmdb_id,title,genres (pipe-separated)."""
    out = df.copy()
    out["genres"] = out["genres"].apply(lambda gs: "|".join(gs))
    out = out[["tmdb_id", "title", "genres"]]
    out.to_csv(path, index=False, encoding="utf-8")
    print(f"{len(out)} satır yazıldı: {path}")


# --------------------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(description="TMDB API ile dengeli film/poster toplama")
    ap.add_argument("--out", required=True, help="DATA_ROOT (labels_v2.csv + posters/ buraya)")
    ap.add_argument("--per-genre", type=int, default=2500)
    ap.add_argument("--min-votes", type=int, default=30)
    ap.add_argument("--max-pages", type=int, default=500)
    ap.add_argument("--pool-factor", type=float, default=1.5,
                    help="havuzda hedefin kaç katı aday çekilsin (rare türler için artır)")
    ap.add_argument("--size", default="w500")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--no-posters", action="store_true", help="sadece etiket çek, poster indirme")
    args = ap.parse_args()

    if not (os.environ.get("TMDB_API_KEY") or os.environ.get("TMDB_BEARER")):
        raise SystemExit("TMDB_API_KEY veya TMDB_BEARER ortam değişkeni gerekli.")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print("== discover ile dengeli çekim ==")
    df = collect_balanced(per_genre=args.per_genre, min_votes=args.min_votes,
                          max_pages=args.max_pages, pool_factor=args.pool_factor)
    save_labels(df, out / "labels_v2.csv")

    if not args.no_posters:
        print("== poster indirme ==")
        download_posters(df, out / "posters", size=args.size, workers=args.workers)


if __name__ == "__main__":
    main()
