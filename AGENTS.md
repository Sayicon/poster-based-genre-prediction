# AGENTS.md — Film Afişinden Tür Tahmini Projesi

Multi-label film türü sınıflandırması. TMDB web scraping → progressive fine-tune (PyTorch).
Yerel geliştirme (RTX 3050) + Google Colab (eğitim). Notebook-first yaklaşım.

## Genel Kural
Her fazın sonunda AGENTS.md'yi oku, tamamlanan maddeleri işaretle ve gerekiyorsa güncelle.

## Klasör Yapısı

**Kod (git):**
```
film-genre-project/
├── src/
│   ├── scraper/
│   │   └── spiders/
│   │       ├── tmdb_id_spider.py      ← Phase 1: export ID'lerinden detay spider ✅
│   │       └── targeted_spider.py    ← Phase 7: genre-odaklı hedefli spider
│   ├── dataset.py
│   ├── model.py          ← Scratch CNN v1 (tarihsel)
│   ├── transforms.py
│   ├── loss.py
│   ├── train.py
│   └── eval.py
├── notebooks/
│   ├── 01_scraper.ipynb            ← Phase 1 ✅
│   ├── 02_preprocessing.ipynb     ← Phase 2 ✅
│   ├── 03_train_baseline.ipynb    ← Phase 3 ✅
│   ├── 04_train_scratch.ipynb     ← Phase 4 ✅
│   ├── 05_eval.ipynb              ← Phase 5 ✅
│   ├── 06_data_analysis.ipynb     ← Phase 6: dengesizlik analizi
│   ├── 07_targeted_scrape.ipynb   ← Phase 7: hedefli veri toplama
│   ├── 08_rebalance.ipynb         ← Phase 8: birleştirme + yeni split
│   ├── 09_train_finetune.ipynb    ← Phase 9: progressive fine-tuning
│   └── 10_eval_v2.ipynb           ← Phase 10: v1 vs v2 karşılaştırması
├── checkpoints/          ← .gitignore'da
└── requirements.txt
```

**Veri (Google Drive — `MyDrive/film-genre-project-data/`):**
```
film-genre-project-data/
├── posters/              ← {tmdb_id}.jpg (mevcut ~12k + yeni ~10k)
├── labels.csv            ← v1 ham çekim (~12k film)
├── labels_v2.csv         ← v1 + hedefli çekim birleşimi (~20-22k film)
├── gap_report.csv        ← Phase 6 çıktısı: tür kombinasyonu boşlukları
├── train.csv / val.csv / test.csv   ← Phase 8 sonrası yenilenir
└── mlb.pkl
```

Tüm path'ler `pathlib.Path` ile yaz. Her notebook'ta `CODE_ROOT` ve `DATA_ROOT` ayrı tanımlanır.

---

## Revizyon Stratejisi — Neden Yeniden Başlıyoruz?

Phase 1–5 tamamlandı ama sonuç tatmin edici değil. Modelin posterleri gerçekten okuması yerine istatistik ezberlediğini kanıtlayan bulgular:

**Ne gördük:**
- Drama (F1=0.63) ve Comedy (F1=0.62) yüksek aldı — ama veri setinin %46'sı Drama içeriyor. Model "her şeye Drama de" öğrendi.
- History (F1=0.10), Documentary (F1=0.11) — veri az, model neredeyse hiç öğrenemedi.
- Model örnek başına 5–7 tür tahmin ediyor; gerçek ortalama ~1.8 tür.
- Frozen baseline (0.3832) ile scratch CNN (0.3327) arasındaki fark sadece %13 — "afişten tür" sinyali çok zayıf kalıyor.

**Kök neden:**
Veri dengesizliği + bunu kapatmak için kullanılan pos_weight (5x) modeli false positive'e zorladı. Veri dengelenmeden model eğitimine devam etmek sorunu büyütür.

**Çözüm yolu:**
1. Mevcut dengesizliği nicel olarak ölç (tür bazı + kombinasyon bazı).
2. Eksik türler için hedefli scraping — her tür ≥ 2.000 film.
3. Drama ve Comedy'yi 2.500'e downsample et — frekans avantajını kaldır.
4. Dengeli veriyle yeniden eğit: pos_weight gerekmez, over-prediction doğal düzelir.
5. Model: MobileNetV3 progressive fine-tuning (scratch CNN yerine) — ImageNet'ten gelen gerçek görsel özellikler üstüne ince ayar.

---

## Phase 6 — Veri Dengeleme Analizi

**Notebook:** `06_data_analysis.ipynb` ✅

**Hedef:** Mevcut `labels.csv`'deki dengesizliği görselleştir, Phase 7 için öncelik sırası çıkar.

- [x] `labels.csv` yükle, `genres` sütununu Python listesine parse et
- [x] Per-genre sayımı → yatay bar chart (mevcut vs hedef 2.000 çizgisi)
- [x] Mevcut açıkları hesapla:

  | Tür | Mevcut | Hedef | Açık |
  |---|---|---|---|
  | History | 532 | 2.000 | **+1.468** |
  | Documentary | 593 | 2.000 | **+1.407** |
  | Animation | 656 | 2.000 | **+1.344** |
  | Mystery | 830 | 2.000 | **+1.170** |
  | Fantasy | 960 | 2.000 | **+1.040** |
  | Family | 1.057 | 2.000 | **+943** |
  | Science Fiction | 1.146 | 2.000 | **+854** |
  | Horror | 1.401 | 2.000 | **+599** |
  | Adventure | 1.558 | 2.000 | **+442** |
  | Crime | 1.835 | 2.000 | **+165** |
  | Drama | 5.539 | 2.500 | downsample |
  | Comedy | 4.473 | 2.500 | downsample |

- [x] Tür kombinasyonu frekans tablosu: tüm unique genre-set'leri say
- [x] 15×15 co-occurrence heatmap — hangi türler birlikte geliyor?
- [x] `gap_report.csv` yaz: `genre_combination, current_count, target_count, deficit`
- [x] Scraping öncelik listesini belirle: en çok açık olan türden başla

---

## Phase 7 — Hedefli Veri Toplama

**Notebook:** `07_targeted_scrape.ipynb` | **Spider:** `src/scraper/scraper/spiders/targeted_spider.py`

**Strateji:** `tmdb_id_spider.py`'nin yeniden düzenlenmiş versiyonu. Aynı altyapı (curl_cffi, backoff, poster pipeline), farklı durdurma mantığı: tüm türler hedefe ulaşana kadar devam et.

**Spider farkı `tmdb_id_spider.py`'den:**
- Başlangıçta `labels.csv` + `labels_v2.csv` (varsa) okunarak mevcut tür sayımları hesaplanır
- Her item işlendiğinde sayaç güncellenir
- `should_accept(genres)` fonksiyonu: en az bir türün sayısı hâlâ hedefin altındaysa `True`
- Hedefin üstündeki türlerin filmlerini atlayarak scraping verimliliğini artırır
- `CLOSESPIDER` yerine manuel kontrol: tüm türler hedefe ulaştığında spider kapanır

**TMDB Genre ID'leri** (discover URL filtresi için referans):
```
Action=28, Adventure=12, Animation=16, Comedy=35, Crime=80
Documentary=99, Drama=18, Family=10751, Fantasy=14, History=36
Horror=27, Mystery=9648, Romance=10749, SciFi=878, Thriller=53
```

- [ ] `targeted_spider.py` yaz — `tmdb_id_spider.py` üzerine inşa et
- [ ] 300 film ile test et — hedef türlerden geliyor mu doğrula, atlama mantığı çalışıyor mu?
- [ ] Tam çekim: tüm türler 2.000'e ulaşana kadar (~10.000 film, ~5-6 saat)
- [ ] Çekim bittikten sonra `labels.csv` + yeni çekim → `labels_v2.csv` olarak birleştir (duplikat kaldır)

---

## Phase 8 — Veri Birleştirme ve Yeni Split

**Notebook:** `08_rebalance.ipynb`

- [ ] `labels_v2.csv` yükle, poster dosyası kontrolü — postersiz satırları düşür
- [ ] Per-genre sayımını görselleştir — tüm türler 2.000 bandında mı?
- [ ] Drama → 2.500, Comedy → 2.500 rastgele downsample et (seed=42)
- [ ] Son dağılım: tüm türler 2.000–2.500 bandında olmalı (max/min oranı ≤ 1.25x)
- [ ] `MultiLabelBinarizer` — tür seti değişmediyse mevcut `mlb.pkl` yeterli
- [ ] `iterative-stratification` ile yeni 70/15/15 split
- [ ] `train.csv`, `val.csv`, `test.csv` yaz (v2 — Drive'a yükle)
- [ ] Split sonrası co-occurrence matrix'i tekrar çiz — v1 vs v2 karşılaştır

---

## Phase 9 — Progressive Fine-tuning (Model v2)

**Notebook:** `09_train_finetune.ipynb`

**Temel değişiklik:** Dengeli veriyle pos_weight ≈ 1.0, over-prediction sorunu kaynağından çözülmüş olur. CutMix/MixUp kapalı — dengeli veriyle label sinyali bulanıklaştırmaya gerek yok.

**Model:** MobileNetV3-Small (ImageNet pretrained)

### 3 Aşamalı Eğitim

**Stage 1 — Classifier ısınması (10 epoch)**
- Backbone tamamen dondurulmuş
- Sadece `classifier[-1]` eğitiliyor (15,375 parametre)
- LR: 1e-3, AdamW
- Hedef: val Macro F1 ~0.35+

**Stage 2 — Son blokları aç (20 epoch)**
- `features[9:]` (son 3 inverted residual blok) + classifier açık
- LR: 3e-4, AdamW, weight_decay=1e-4
- CosineAnnealingLR (T_max=20)
- Hedef: val Macro F1 ~0.42–0.48

**Stage 3 — Tam ağ (20 epoch)**
- Tüm parametreler açık
- LR: 1e-4, AdamW, weight_decay=1e-4
- CosineAnnealingLR (T_max=20)
- Hedef: val Macro F1 ~0.48–0.55

### Ortak Ayarlar
- Loss: `BCEWithLogitsLoss` — pos_weight **kullanma** (veri dengeli)
- Batch size: 64, num_workers: 2
- Early stopping: patience=10, her stage başında sıfırla
- Checkpoint: `checkpoints/finetune/stage{1,2,3}_best.pt`
- Her stage'in son checkpoint'i bir sonraki stage'in başlangıcı

- [ ] Stage 1 kodla ve çalıştır
- [ ] Stage 2 kodla ve çalıştır (Stage 1 best'ten başlat)
- [ ] Stage 3 kodla ve çalıştır (Stage 2 best'ten başlat)
- [ ] Her stage için loss + val Macro F1 eğrilerini çiz

---

## Phase 10 — Değerlendirme v2

**Notebook:** `10_eval_v2.ipynb`

- [ ] Fine-tuned model (Stage 3 best) yükle, test seti inference
- [ ] Val seti üzerinde per-class threshold optimizasyonu (0.3–0.7 grid)
- [ ] Metrikler: Macro F1, Micro F1, Hamming Loss
- [ ] **Kritik kontrol 1:** Ortalama tahmin edilen tür sayısı/film (hedef: 1.5–2.5)
- [ ] **Kritik kontrol 2:** Drama ve Comedy F1 düştü mü? (frekans biası azaldı mı?)
- [ ] **Kritik kontrol 3:** Animation, Horror, History F1 yükseldi mi? (gerçek görsel öğrenme)
- [ ] 3 model karşılaştırma tablosu: Scratch v1 / Baseline v1 / Fine-tuned v2
- [ ] Per-class F1 karşılaştırma bar chart (3 model yan yana)
- [ ] 12 film için görsel + tahmin + gerçek etiket göster

---

## Beklenen v2 Performans

| Model | Macro F1 | Ortalama Tahmin/Film | Not |
|---|---|---|---|
| Scratch CNN v1 | 0.3327 | ~5–6 | Veri dengesizliği + pos_weight |
| Baseline v1 (frozen) | 0.3832 | ~3–4 | Referans |
| Fine-tuned v2 (hedef) | **0.48–0.55** | **1.5–2.5** | Dengeli veri + açık backbone |

---
---

## [Tamamlandı] Phase 0 — Kurulum

- [x] `git init`, `.gitignore` oluştur (`posters/`, `checkpoints/`, `*.pt`, `__pycache__/`)
- [x] `requirements.txt` yaz: `scrapy`, `torch`, `torchvision`, `albumentations`, `scikit-learn`, `scikit-multilearn`, `iterative-stratification`, `pandas`, `tqdm`
- [x] Sanal ortam kur, bağımlılıkları yükle, CUDA varlığını doğrula

> `git commit -m "chore: project scaffold"` ✅

---

## [Tamamlandı] Phase 1 — Web Scraping

**Kaynak:** `themoviedb.org` — TMDB günlük export (1.19M ID) → detay sayfaları.
**Sonuç:** ~12.170 film, ~12.090 geçerli poster + labels.csv

- [x] Scrapy projesi, `settings.py` ayarları (DOWNLOAD_DELAY=2, CONCURRENT_REQUESTS=4)
- [x] Spider: `tmdb_id_spider.py` — export ID'lerinden detay crawl
- [x] Posterler `{tmdb_id}.jpg` olarak kaydediliyor (`curl_cffi` ile, redirect sorunu nedeniyle)
- [x] Filtre: genres boşsa atla, poster yoksa atla, 300×400px altındaysa atla
- [x] `01_scraper.ipynb` yazıldı
- [x] Tam çekim tamamlandı — ~12.170 film ✅

> **Not:** `CurlCffiMiddleware` (Chrome124 impersonation) + VPN + `ExponentialBackoffMiddleware` (429→2s/4s/8s/16s backoff).
> **Not:** Listing spider ban'landı (~600-700'de 429). `tmdb_id` spider export'tan okuyarak devam etti.
> **Not:** `PosterImagesPipeline` hata alırsa raise etmez — label yine de CSV'ye yazılır.

> `git commit -m "feat: scrapy spider and poster pipeline"` ✅

---

## [Tamamlandı] Phase 2 — Veri Ön İşleme

**Notebook:** `02_preprocessing.ipynb`

- [x] Eksik poster satırlarını düşür, genres'i Python listesine parse et
- [x] `TARGET_GENRES` belirlendi (15 tür, min 500 örnek/tür)
- [x] `MultiLabelBinarizer` ile multi-hot matris, `mlb.pkl`
- [x] `iterative-stratification` ile 70/15/15 split → Train:8.466 / Val:1.818 / Test:1.806
- [x] `transforms.py`: train ve val/test pipeline'ları

> `git commit -m "feat: preprocessing and stratified split"` ✅

---

## [Tamamlandı] Phase 3 — Baseline Model (Pretrained)

**Notebook:** `03_train_baseline.ipynb`

- [x] MobileNetV3-Small, frozen backbone (15.375 / 1.533.231 parametre)
- [x] 10 epoch, BCEWithLogitsLoss + Adam
- [x] **Best val Macro F1: 0.3206** → **Test Macro F1: 0.3832**

> `git commit -m "feat: pretrained baseline"` ✅

---

## [Tamamlandı] Phase 4 — Scratch CNN

**Notebook:** `04_train_scratch.ipynb` | **Kaynak:** `src/model.py`, `src/loss.py`, `src/train.py`

- [x] 4 Conv blok (32→64→128→256), GlobalAvgPool, FC(512)→FC(256)→FC(N_CLASSES), Kaiming init
- [x] BCEWithLogitsLoss + pos_weight (max 5.0x)
- [x] AdamW (lr=5e-4) + CosineAnnealingLR + warmup (3 epoch) + early stopping (patience=10)
- [x] **Best val Macro F1: 0.2946** (epoch 42/50)
- [x] Continuation (CutMix=0.3, MixUp=0.1, CONT_LR=2e-4): iyileşme yok, 0.2946'da kaldı

> `git commit -m "feat: scratch CNN training pipeline"` ✅

---

## [Tamamlandı] Phase 5 — Değerlendirme

**Notebook:** `05_eval.ipynb`

- [x] Test seti inference, per-class threshold optimizasyonu (0.3–0.7 grid)
- [x] **Scratch CNN Test Macro F1: 0.3327** (Micro F1: 0.3900, Hamming: 0.3362)
- [x] **Baseline Test Macro F1: 0.3832** (Micro F1: 0.4737, Hamming: 0.1829)
- [x] Scratch / Baseline = **%86.8 — BAŞARILI** (hedef %60+)
- [x] Zayıf türler: History (0.10), Documentary (0.11), Mystery (0.18)
- [x] Güçlü türler: Drama (0.63), Comedy (0.62) — frekans biası

> **Sorun tespiti:** Model 5–7 tür/film tahmin ediyor (gerçek: ~1.8). Drama/Comedy frekans biası. Veri dengelenmeden ilerleme yok.

> `git commit -m "feat: evaluation and metrics"` ✅
