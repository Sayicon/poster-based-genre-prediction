# AGENTS.md — Film Afişinden Tür Tahmini Projesi

Multi-label film türü sınıflandırması. TMDB web scraping → scratch CNN (PyTorch).
Yerel geliştirme (RTX 3050) + Google Colab (eğitim). Notebook-first yaklaşım.

## Genel Kural
Her fazın sonunda AGENTS.md'yi oku, tamamlanan maddeleri işaretle ve gerekiyorsa güncelle.

## Klasör Yapısı

**Kod (git):**
```
film-genre-project/
├── src/
│   ├── scraper/          ← Scrapy projesi
│   ├── dataset.py        ← PyTorch Dataset
│   ├── model.py          ← Scratch CNN
│   ├── transforms.py     ← Augmentation pipeline
│   ├── loss.py           ← Focal Loss
│   ├── train.py          ← Eğitim döngüsü
│   └── eval.py           ← Metrik hesaplama
├── notebooks/
│   ├── 01_scraper.ipynb
│   ├── 02_preprocessing.ipynb
│   ├── 03_train_baseline.ipynb
│   ├── 04_train_scratch.ipynb
│   └── 05_eval.ipynb
├── checkpoints/          ← .gitignore'da
└── requirements.txt
```

**Veri (Google Drive — `MyDrive/film-genre-project-data/`):**
```
film-genre-project-data/
├── posters/              ← {tmdb_id}.jpg
├── labels.csv            ← ham çekim çıktısı
├── train.csv             ← Phase 2 sonrası
├── val.csv
├── test.csv
└── mlb.pkl               ← MultiLabelBinarizer
```

Tüm path'ler `pathlib.Path` ile yaz. Her notebook'ta `CODE_ROOT` ve `DATA_ROOT` ayrı tanımlanır; Colab mount bloğu yorum satırı olarak bırakılır.

---

## Phase 0 — Kurulum

- [x] `git init`, `.gitignore` oluştur (`posters/`, `checkpoints/`, `*.pt`, `__pycache__/`)
- [x] `requirements.txt` yaz: `scrapy`, `torch`, `torchvision`, `albumentations`, `scikit-learn`, `scikit-multilearn`, `iterative-stratification`, `pandas`, `tqdm`
- [x] Sanal ortam kur, bağımlılıkları yükle, CUDA varlığını doğrula

> `git commit -m "chore: project scaffold"` ✅

---

## Phase 1 — Web Scraping

**Kaynak:** `themoviedb.org` — listing sayfaları → detay sayfaları.
**Hedef:** 10.000–12.000 afiş + `labels.csv` (`tmdb_id, title, genres`).

- [x] Scrapy projesi kur, `settings.py`'de `DOWNLOAD_DELAY=2`, `RANDOMIZE_DOWNLOAD_DELAY=True`, `CONCURRENT_REQUESTS=4` ayarla
- [x] Spider: listing → detay crawl, her filmden `tmdb_id`, `title`, `genres` (liste), `poster_url` çek
- [x] Posterler `{tmdb_id}.jpg` olarak kaydediliyor (`requests` ile, ImagesPipeline yerine — redirect sorunu nedeniyle)
- [x] Filtre: `genres` boşsa atla, poster yoksa atla, görsel 300×400px altındaysa atla (Pillow ile boyut kontrolü)
- [x] `01_scraper.ipynb` yazıldı (Colab mount bloğu, 100-film test hücresi, tam çekim hücresi, dağılım grafiği)
- [x] 100 film ile test et — 4m36s, 100 poster, sorunsuz ✅
- [ ] Sınıf dağılımını kontrol et, hedef tür listesini belirle (min. 500 örnek/tür) ← `02_preprocessing.ipynb` cell-2'de yapılıyor
- [ ] Tam çekim tamamlansın — **~11.300 film, devam ediyor** (`tmdb_id` spider, hedef 12.000)
- [ ] `posters/` + `labels.csv`'yi Google Drive'a yükle (Colab üzerinden)

> **Not:** `CsvExportPipeline.process_item`'a `self.file.flush()` eklendi (veri buffer'da kalıyordu).
> **Not:** JOBDIR'ı notebook'tan `-s` ile geçme — `tmdb_id` spider'ı kendi `custom_settings`'inde `JOBDIR=""` ile devre dışı bırakıyor; global ayar listing spider içindir.
> **Not:** Listing spider (`tmdb`) 429 ban'ına ~600-700 filmde çarpıyor. `tmdb_id` spider'ı TMDB günlük export'undan (1.19M ID) okuyarak doğrudan detay sayfalarına gider.
> **Not:** TMDB TLS parmak izi tespiti — `curl_cffi` (Chrome124 impersonation) `CurlCffiMiddleware` olarak Scrapy'ye entegre edildi. VPN (ProtonVPN Pro) + curl_cffi kombinasyonu ile çalışıyor.
> **Not:** `ExponentialBackoffMiddleware` — 429'da 2s→4s→8s→16s backoff. `PosterImagesPipeline` poster indirme başarısız olursa raise etmez, label yine de CSV'ye yazılır (Phase 2'de postersiz satırlar filtrelenir).
> **Not:** Letterboxd, FilmAffinity, IMDb, RT — Cloudflare/JS engeli, vazgeçildi.

> `git commit -m "feat: scrapy spider and poster pipeline"` ✅

---

## Phase 2 — Veri Ön İşleme

**Notebook:** `02_preprocessing.ipynb`

- [x] Eksik poster dosyası olan satırları düşür, `genres`'i Python listesine parse et ✅
- [x] `TARGET_GENRES` sabitini belirle (görsel sinyali güçlü türler: Action, Animation, Horror, Sci-Fi vb.) ✅
- [x] `MultiLabelBinarizer` ile multi-hot matris oluştur, `mlb` nesnesini pickle'la ✅
- [x] `iterative-stratification` ile 70/15/15 split → `train.csv`, `val.csv`, `test.csv` ✅
- [x] Split sonrası sınıf dağılımını görselleştir, dengeli olduğunu doğrula ✅
- [x] `transforms.py`: eğitim (RandomCrop, ColorJitter, Rotate — dikey flip yok) ve val/test (sadece Resize+Normalize) pipeline'ları ✅

> `git commit -m "feat: preprocessing and stratified split"`

---

## Phase 3 — Baseline Model (Pretrained)

**Notebook:** `03_train_baseline.ipynb` — başarı tavanını hızlıca görmek için.

- [x] `torchvision` üzerinden pretrained MobileNetV3-Small yükle ✅
- [x] Son katmanı değiştir: `Linear(in, N_CLASSES)` + Sigmoid çıkış ✅
- [x] Sadece son katmanı eğit (backbone dondurulmuş), 10 epoch ✅
- [x] `BCEWithLogitsLoss` + `Adam`, val Macro F1'i logla ✅
- [x] Eğitimi çalıştır — **Best val Macro F1: 0.3206** (frozen backbone, 10 epoch) ✅

> `git commit -m "feat: pretrained baseline"`

---

## Phase 4 — Scratch CNN

**Notebook:** `04_train_scratch.ipynb` | **Kaynak:** `src/model.py`, `src/loss.py`, `src/train.py`

### Model (`src/model.py`)
- [x] 4 Conv blok: `Conv2d → BN → ReLU → MaxPool → Dropout(0.25)`, filtreler 32→64→128→256 ✅
- [x] `GlobalAvgPool → FC(512) → FC(256) → FC(N_CLASSES)` + Sigmoid ✅
- [x] He (Kaiming) initialization — ReLU ile zorunlu, Xavier kullanma ✅

### Loss (`src/loss.py`)
- [x] `BCEWithLogitsLoss` ile başla, `pos_weight` ile azınlık sınıflara ağırlık ver ✅
- [x] Azınlık sınıflar öğrenilmiyorsa Focal Loss'a (`gamma=2`) geç ✅

### Eğitim (`src/train.py`)
- [x] `WeightedRandomSampler` ile class imbalance'ı minibatch seviyesinde dengele ✅
- [x] `AdamW (lr=1e-3, weight_decay=1e-4)` + `CosineAnnealingLR` (ilk 3 epoch warmup) ✅
- [x] Her epoch sonunda val Macro F1 hesapla, en iyi checkpoint'i kaydet ✅
- [x] Early stopping: patience=10, val Macro F1 üzerinden ✅

### Augmentation
- [x] Eğitimde `CutMix` ve `MixUp` uygula — etiket vektörlerini de alan oranına göre güncelle ✅

- [x] Notebook'ta eğitimi başlat, loss/F1 eğrilerini çiz — **Best val Macro F1: 0.2946** (50 epoch) ✅

> `git commit -m "feat: scratch CNN training pipeline"`

---

## Phase 5 — Değerlendirme

**Notebook:** `05_eval.ipynb` ✅ | **Kaynak:** `src/eval.py` ✅

- [x] Test seti üzerinde inference çalıştır ✅
- [x] Metrikler: **Macro F1** (ana metrik), Micro F1, Hamming Loss ✅
- [x] Her sınıf için ayrı threshold optimize et (0.3–0.7 aralığında grid search) ✅
- [x] Per-class F1 bar chart çiz ✅
- [x] En az 8 örnek için görsel + tahmin + gerçek etiket göster ✅
- [x] Baseline (Phase 3) ile karşılaştır — Scratch %86.8, **BAŞARILI** ✅

> `git commit -m "feat: evaluation and metrics"`

---

## Beklenen Performans

| Model | Beklenen Macro F1 |
|---|---|
| Pretrained baseline (frozen) | 0.55 – 0.65 beklenti / **0.3832 gerçek** |
| Scratch CNN | 0.35 – 0.45 beklenti / **0.3327 gerçek** |

Scratch CNN baseline'ın %60–70'ine ulaşırsa proje başarılıdır. **Sonuç: %86.8 — BAŞARILI.**

> **Notlar:**
> - pos_weight max 5.0 ile sınırlandı (14x+ değerler eğitimi bozuyordu)
> - CutMix/MixUp ilk turda kapatıldı, continuation'da açıldı (katkısı minimal)
> - Threshold optimizasyonu val Macro F1'i 0.2946 → test 0.3327'ye taşıdı (+0.038)
> - En zayıf türler: History (F1=0.10), Documentary (F1=0.11) — veri azlığı
> - En güçlü türler: Drama (F1=0.63), Comedy (F1=0.62)
