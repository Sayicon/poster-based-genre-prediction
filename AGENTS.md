# AGENTS.md — Film Afişinden Tür Tahmini Projesi

Multi-label film türü sınıflandırması (poster → tür). TMDB **resmî API** ile veri → **5 farklı
transformer** fine-tune (PyTorch / HuggingFace). Google Colab (A100) eğitim. Notebook-first.

## Referanslar
- **`ProjeFinalİsterleri.pdf`** — hocanın final isterleri. **Bağlayıcı kaynak budur.** Aşağıdaki "İsterler Özeti"ne bak.
- **[BULGULAR.md](BULGULAR.md)** — rapor günlüğü. Yaptığımız işler / sorunlar / çözümler / sayısal bulgular burada birikir; final IEEE raporunun ve vize "veri toplama/temizleme" raporunun ham kaynağıdır.

## Genel Kural
Her fazın sonunda: (1) AGENTS.md'yi oku, tamamlanan maddeleri işaretle/güncelle; (2) **[BULGULAR.md](BULGULAR.md)'ye o fazda ne yaptık / ne bulduk / hangi sorunu nasıl çözdük bilgilerini ekle.**

**Git kuralı:** Commit mesajlarına `Co-Authored-By` / "Generated with Claude" gibi hiçbir trailer/imza **eklenmez.**

---

## İsterler Özeti (PDF'ten — her madde puanlamaya tabi)
- [x] **5 farklı transformer modeli**, hepsi çalışır (ViT, DeiT, BeiT, Swin, CvT) — hepsi v1 baseline'ı geçti.
- [x] Her model için metrikler: Accuracy, Recall, Precision, Sensitivity, Specificity, F-Score, AUC (per-class + macro/micro).
- [x] Her model için **confusion matrix** + **ROC eğrisi** (notebook 10 → `figures/`).
- [x] **Cross-validation** (5-cv) — her fold'un train/val loss eğrisi aynı grafikte (`loss_curves.png`).
- [x] Her model için **training time** + **inference time**.
- [x] Veri öncesi/sonrası görselleştirme + tablolar (`dist_before_after.png`, `cooccurrence_v2.png`, BULGULAR). _(Vize detay raporu → Phase E.)_
- [ ] **Google Colab** + **Drive paylaşımı** (urhanh@gmail.com'a) — link rapora konacak.
- [ ] Rapor: **IEEE şablonu (.docx)**, sonuçlar tablo halinde + yorum.
- Not: Proje **multimodal değil** (sadece poster görseli) → hocayla ayrı görüşme gerekmez.

---

## Klasör Yapısı

**Kod (git):**
```
film-genre-project/
├── src/
│   ├── data/
│   │   └── tmdb_api.py        ← Phase A: TMDB API istemcisi (discover + poster indirme)
│   ├── dataset.py             ← reusable (transformer'lar için uyarlanacak)
│   ├── transforms.py
│   ├── train.py / eval.py     ← reusable yardımcılar
│   └── (model.py, loss.py)    ← v1 scratch CNN (tarihsel; baseline)
├── legacy/                    ← terk edilen HTML scraper'lar (rapor kanıtı)
├── notebooks/
│   ├── 01–05 ...              ← v1 (tamamlandı, tarihsel)
│   ├── 06_data_analysis.ipynb ← dengesizlik analizi (tamamlandı)
│   ├── 07_api_collect.ipynb   ← Phase A: API ile dengeli çekim
│   ├── 08_preprocess_cv.ipynb ← Phase B: temizleme + 5-fold CV split
│   ├── 09_train_transformer.ipynb ← Phase C: tek notebook, model seçimiyle 5 modeli eğitir
│   └── 10_evaluate.ipynb      ← Phase D: tüm metrikler/figürler + model karşılaştırma
├── AGENTS.md / BULGULAR.md / requirements.txt
└── ProjeFinalİsterleri.pdf
```

**Veri (Google Drive — `MyDrive/film-genre-project-data/`):**
```
├── posters/              ← {tmdb_id}.jpg
├── labels.csv            ← v1 ham çekim (~16.3k)
├── labels_v2.csv         ← API çekimi sonrası dengeli set
├── folds/                ← fold_{0..4}_{train,val}.csv (5-fold CV)
└── mlb.pkl
```
Tüm path'ler `pathlib.Path`. Her notebook'ta `CODE_ROOT` / `DATA_ROOT` ayrı.

---

## Neden Yeniden Yapılanıyoruz? (özet)
1. **Hoca isterleri:** 5 transformer zorunlu + CV + tam metrik/figür seti. v1'in CNN/MobileNet'i bunu karşılamıyor.
2. **Scraping çöktü:** HTML sitesi ban'lıyor (targeted run'da 9.619×429, 864 film kaybı). → **resmî TMDB API**'ye geçiyoruz (hoca onayladı, ücretsiz, günlük limit yok).
3. **Veri dengesizliği:** Drama 6.381 ↔ History 858 (~7.4x). v1 modeli frekans ezberleyip aşırı tahmin yaptı. → API ile **dengeli + kombinasyon-farkında** çekim.

Detaylı bulgular ve sayılar: [BULGULAR.md](BULGULAR.md).

---

## Phase A — Veri Toplama (TMDB API)

**Notebook:** `07_api_collect.ipynb` | **Kaynak:** `src/data/tmdb_api.py`

- [x] TMDB API key (v3) / read token (v4) alındı (kullanıcı), `.env`'e konuldu.
- [x] `/discover/movie?with_genres=<id>` ile **tür bazlı** çekim; her tür için bol aday havuzu, `vote_count.gte=10` ile çöp filtresi (eşik kararı: BULGULAR.md §5).
- [x] `poster_path` olanları al; `image.tmdb.org/t/p/w500/...` ile poster indir; dedupe (tmdb_id) — **%100 poster kapsamı**.
- [x] **Kombinasyon-farkındalık:** eksiklik-güdümlü greedy seçim baskın türleri "yolcu" olarak kısıtlayıp kombinasyonları doğal kapsadı — ayrı `with_genres=a,b` (AND) sorgusuna gerek kalmadı.
- [x] Dengeli set: her tür **3.000** (Drama/Comedy yolcu etkisiyle yüksek; dengesizlik 7.4x → 2.22x). → `labels_v2.csv` (**23.640 film**).
- [x] Çekim öncesi/sonrası dağılım grafiği (`dist_before_after.png`). → BULGULAR.md §5 güncellendi.

**TMDB Genre ID'leri:** Action=28, Adventure=12, Animation=16, Comedy=35, Crime=80, Documentary=99, Drama=18, Family=10751, Fantasy=14, History=36, Horror=27, Mystery=9648, Romance=10749, SciFi=878, Thriller=53.

---

## Phase B — Ön İşleme + CV Split

**Notebook:** `08_preprocess_cv.ipynb`

- [x] `labels_v2.csv` yükle; postersiz/bozuk satırları düşür; genres parse. (23.640 film, 0 düşüldü)
- [x] `MultiLabelBinarizer` (15 tür) → `mlb.pkl`.
- [x] **5-fold CV** — `iterstrat.MultilabelStratifiedKFold` → `folds/fold_{i}_{train,val}.csv`. (~18.9k train / ~4.7k val, sıfır overlap, mükemmel stratifikasyon)
- [x] Temizleme öncesi/sonrası tür dağılımı + co-occurrence heatmap. → `cooccurrence_v2.png`, BULGULAR.md §6.
- [x] _(Phase C)_ Poster ön işleme: 2:3 portre → 224×224 resize (distort-to-square; rapora not). notebook 09.
- [x] _(Phase D)_ Değerlendirme **out-of-fold (OOF)** tahminlerle yapıldı (ayrı hold-out yok).

---

## Phase C — 5 Transformer Fine-tuning

**Notebook:** `09_train_transformer.ipynb` (tek notebook, `MODEL_NAME` değişkeniyle 5 modeli sırayla eğitir)

**Modeller (HuggingFace, multi-label fine-tune — `problem_type="multi_label_classification"`):**
1. **ViT** — `google/vit-base-patch16-224`
2. **DeiT** — `facebook/deit-base-distilled-patch16-224`
3. **BeiT** — `microsoft/beit-base-patch16-224-pt22k-ft22k`
4. **Swin** — `microsoft/swin-base-patch4-window7-224`
5. **CvT** — `microsoft/cvt-13` (alternatif: Swin-V2 `microsoft/swinv2-base-patch4-window8-256`)

**Ortak ayarlar:**
- Loss: `BCEWithLogitsLoss` (multi-label). Veri dengeli → `pos_weight` yok; gerekirse focal/weighted sampler.
- AdamW, düşük LR (fine-tune: ~2e-5–5e-5), cosine schedule + warmup, early stopping.
- **5-fold CV:** her model × 5 fold = 25 koşu. Her fold için train/val loss kaydı (aynı grafikte çizilecek).
- Her model için **training time** ölç ve kaydet. Checkpoint'ler `checkpoints/<model>/fold{i}_best.pt`.
- [x] 5 modeli eğit; loss eğrileri + süreleri kaydet → BULGULAR.md. (A100, ~113 dk; en iyi **Swin val MacroF1=0.530**, v1 0.383'ten +0.147; CvT 0.381 en zayıf)

---

## Phase D — Değerlendirme

**Notebook:** `10_evaluate.ipynb`

- [x] Her model için OOF inference; per-class threshold optimizasyonu.
- [x] Metrikler (per-class + macro/micro): Accuracy, Precision, Recall/Sensitivity, Specificity, F-Score, AUC. (en iyi **Swin macro-F1 0.562**, macro-AUC 0.862)
- [x] **Confusion matrix** (per-class) + **ROC eğrisi** (one-vs-rest) → `figures/`.
- [x] **Inference time** ölç (her model) — ~1.6 ms/görsel.
- [x] 5 model + v1 baseline karşılaştırma tablosu; per-class F1 bar chart.
- [x] Kritik kontrol: ortalama tahmin **~2.4 tür/film** (v1: 5-7), frekans biası gitti (Animation 0.86 zirvede, History 0.10→0.47).
- [x] 12 film için görsel + tahmin + gerçek etiket → `figures/`.
- [x] Random/frekans-prior baseline: macro-F1 ~0.15 (şans) → Swin 0.562 **~3.8x** iyi; görüntü sinyalini + cheat-yokluğunu kanıtlar.

---

## Phase E — Rapor
- [x] IEEE rapor taslağı (LaTeX, Türkçe): `report/MustafaKeremCekici_231307121.tex` — tüm tablolar + figür referansları + yorum. (Overleaf'te derle + figürleri yükle, bkz. `report/README.md`.)
- [ ] Vize detaylı veri toplama/temizleme raporu (rapor §II + BULGULAR §1-6'dan genişlet).
- [ ] **Drive + Overleaf paylaşımı** urhanh@gmail.com'a (düzenleme yetkili); linkler rapora.

---
---

## [Tamamlandı / Tarihsel] v1 — Phase 0–6

> v1 modelleri (CNN/MobileNet) transformer **değil**, 5'lik şartı karşılamaz; raporda **baseline karşılaştırması** olarak kullanılır.

- **Phase 0 — Kurulum:** git, .gitignore, requirements, venv, CUDA. ✅
- **Phase 1 — HTML Scraping:** themoviedb.org export ID → detay crawl; ~16.3k film + poster. curl_cffi (Chrome124) + VPN + backoff. **Ban sorunu yaşandı** (bkz. BULGULAR.md §3.1). ✅ (terk edildi → API)
- **Phase 2 — Ön İşleme:** 15 tür, MultiLabelBinarizer, iterative-stratified 70/15/15. ✅
- **Phase 3 — Baseline:** Frozen MobileNetV3-Small. **Test Macro F1 0.3832.** ✅
- **Phase 4 — Scratch CNN:** 4 conv blok + pos_weight 5x. Best val 0.2946. ✅
- **Phase 5 — Değerlendirme:** Scratch Test Macro F1 0.3327. Aşırı tahmin (5–7 tür/film), frekans biası (Drama/Comedy yüksek, History/Documentary düşük). ✅
- **Phase 6 — Dengesizlik Analizi:** `06_data_analysis.ipynb`, dağılım + gap analizi. ✅
