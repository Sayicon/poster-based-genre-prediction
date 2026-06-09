# BULGULAR — Film Afişinden Tür Tahmini Projesi

> **Bu dosyanın işlevi:** Projede yaptığımız işleri, karşılaştığımız sorunları, uyguladığımız
> çözümleri ve sayısal bulgularımızı kronolojik olarak kaydeden **rapor günlüğü**.
> Hem final IEEE raporunun, hem de vize için istenen **detaylı "veri toplama/temizleme" raporunun**
> ham kaynağıdır. Her fazın sonunda buraya ekleme yapılır (bkz. [AGENTS.md](AGENTS.md) Genel Kural).
>
> Başlıklar: **Bulgularımız · Yaptığımız İşler · Yaşadığımız Sorunlar · Uyguladığımız Çözümler**

---

## 1. Projenin Özeti

- **Görev:** Film afişi (poster görseli) → film türü tahmini. **Multi-label** (bir afiş birden çok türe ait olabilir).
- **Hedef tür sayısı:** 15 (Action, Adventure, Animation, Comedy, Crime, Documentary, Drama, Family, Fantasy, History, Horror, Mystery, Romance, Science Fiction, Thriller).
- **Final ürün:** Hocanın isterlerine göre **5 farklı transformer** modelinin (ViT/DeiT/BeiT/Swin/CvT) afişten tür sınıflandırması; her biri tam metrik seti + figürlerle değerlendirilir.
- **Veri modu:** Yalnızca görsel (poster). Başlık/metin **kullanılmıyor** → proje multimodal değil.

---

## 2. Yaptığımız İşler (kronolojik)

### v1 — İlk pipeline (Phase 0–5, tamamlandı)
- TMDB **web sitesi (HTML)** kazınarak ~16.300 film + poster toplandı (`labels.csv`).
- Ön işleme: postersiz satırlar düşürüldü, `MultiLabelBinarizer`, iterative-stratified 70/15/15 split.
- İki model eğitildi:
  - **Frozen MobileNetV3-Small baseline** (sadece classifier head eğitildi).
  - **Sıfırdan CNN** (4 conv blok, GlobalAvgPool, FC katmanlar).
- Değerlendirme yapıldı, dengesizlik analizi (Phase 6) ile boşluklar çıkarıldı.

### v2 — Yeniden yapılanma (devam ediyor)
- Hocanın final isterleri yayınlandı → **5 transformer zorunluluğu** ortaya çıktı; v1 modelleri (CNN/MobileNet) bu şartı karşılamıyor (transformer değil), ancak raporda **baseline karşılaştırması** olarak kullanılabilir.
- Veri toplama **HTML scraping → resmî TMDB API**'ye taşınmasına karar verildi (hoca onayladı).

---

## 3. Yaşadığımız Sorunlar

### 3.1 Scraping ban'ı (en büyük sorun)
TMDB **web sitesi** agresif rate-limit / bot koruması uyguluyor. curl_cffi (Chrome TLS taklidi) + VPN + exponential backoff'a rağmen sürekli **HTTP 429** alındı.

| Çalışma | Süre | HTTP 429 | Kalıcı kayıp (max retries exhausted) |
|---|---|---|---|
| `targeted` run | 2026-05-14 → 06-04 | **9.619** | **864 film** |
| `tmdb` (listing) | 2026-05-13 | 791 | — |
| `tmdb_id` run | 2026-05-13/14 | 381 | + bağlantı sıfırlama hataları |

- Pratik hız: **3 saatte ~400–500 film, sonra ban.** VPN açmak tam çözmedi.
- Kök neden: site düzeyinde IP/oran tabanlı bot tespiti.

### 3.2 Scraper kodundaki bug'lar (ban'ı ağırlaştıran)
- `CurlCffiMiddleware` isteği **senkron/bloklayıcı** atıyordu → Twisted reactor donuyor, eşzamanlılık fiilen yok, çok yavaş.
- Backoff `time.sleep()` ile → reactor'ı bloke ediyor.
- `targeted_spider` `custom_settings`'i ana ayardan **daha agresif** (DELAY 3 vs 8, CONCURRENT 2 vs 1) → daha çabuk ban.
- `targeted_spider` sıralı ID gezip **her sayfayı indirdikten sonra** tür filtresi uyguluyordu → isteklerin ~%90'ı çöp; az türleri (History vb.) doldurmak imkânsızlaştı. AGENTS'te planlanan "discover URL + genre ID" hiç uygulanmamıştı.

### 3.3 Veri dengesizliği (modeli bozan sorun)
15 hedef tür içinde dağılım (toplam **16.307 film**, ort. **2.29 tür/film**):

| Tür | Film | Tür | Film |
|---|---|---|---|
| History | **858** (min) | Crime | 2.128 |
| Mystery | 1.168 | Romance | 2.269 |
| Animation | 1.266 | Action | 2.615 |
| Fantasy | 1.334 | Thriller | 2.948 |
| Science Fiction | 1.466 | **Comedy** | **5.116** |
| Family | 1.698 | **Drama** | **6.381** (max) |
| Horror | 2.004 | | |
| Adventure | 2.017 | | |
| Documentary | 2.017 | | |

- Max/min oranı 15 tür içinde **~7.4x** (Drama/History).
- Hedef dışı türler de var: Western 302, War 492, TV Movie 575, Music 732.
- Multi-label dağılımı (kaç türlü kaç film): 1→4463, 2→5205, 3→4639, 4→1507, 5→405, 6→74, 7→13, 8→1.

### 3.4 v1 model bulguları (dengesizliğin sonucu)
| Model | Test Macro F1 | Micro F1 | Hamming | Not |
|---|---|---|---|---|
| Frozen MobileNetV3 (baseline) | **0.3832** | 0.4737 | 0.1829 | en iyi v1 |
| Sıfırdan CNN | 0.3327 | 0.3900 | 0.3362 | pos_weight 5x |

- Model film başına **5–7 tür** tahmin ediyordu (gerçek ort. ~2.3) → **aşırı tahmin (over-prediction)**.
- Güçlü türler **Drama 0.63, Comedy 0.62** — frekans biası (en sık türler).
- Zayıf türler **History 0.10, Documentary 0.11, Mystery 0.18** — az veri.
- **Kök neden:** veri dengesizliği + bunu telafi için kullanılan `pos_weight≈5x`, modeli false-positive'e (aşırı tahmin) zorladı. Yani ağırlıklandırmanın *fikri* değil, *bu uygulanış biçimi* başarısız oldu.

### 3.5 "co-occurrence cheat" riski (kavramsal)
Çok yan yana gelen türlerde (örn. Comedy↔Romance) model, romance'in kendi görsel sinyalini öğrenmeden "comedy gördüm, romance da vardır" diyerek skor şişirebilir. Bu **engellenemez ama azaltılabilir**.
- **Aldığımız önlem:** veri setini kurarken kombinasyon (ikili tür) dengesine dikkat; baskın eşleşmeleri kısmak.
- Raporda: "önlem aldık, ancak bu cheat riski tamamen ortadan kalkmaz" notu düşülecek. (Ayrı bir cheat-testi kurmuyoruz.)

---

## 4. Uyguladığımız Çözümler

### 4.1 Veri toplama: HTML → resmî TMDB API
Resmî [TMDB API](https://developer.themoviedb.org/docs/rate-limiting) araştırması:
- **Ücretsiz** (kâr amacı gütmeyen / akademik kullanım). Ticari değil → ücret yok.
- **Günlük limit YOK** (eski "10 sn'de 40 istek" limiti 16 Aralık 2019'da kaldırıldı).
- **~40–50 istek/saniye**, IP başına ~20 bağlantı.
- `/discover/movie` endpoint'i `with_genres` ile **türe göre filtre** + sayfalama (20/sayfa) veriyor; `poster_path` döndürüyor. Posterler `image.tmdb.org` CDN'inden (key gerekmez).
- **Sonuç:** binlerce filmi ban almadan, dakikalar içinde, dengeli ve kombinasyon-farkında çekebiliriz.

### 4.2 Model stratejisi
- v1'in CNN'i yerine **5 pretrained transformer fine-tune** (ViT/DeiT/BeiT/Swin/CvT).
- Dengeli veri → `pos_weight` gerekmez; gerekirse örnek düzeyinde weighted sampler / focal loss (loss'a ağır pos_weight basmak yerine), böylece aşırı tahmin tekrar oluşmaz.

---

## 5. Phase A — TMDB API ile Dengeli Çekim (tamamlandı)

**Yöntem:** İki fazlı toplama — (1) tür bazlı aday havuzu (`/discover/movie?with_genres`), (2) eksiklik-güdümlü greedy seçim: her adımda en eksik tür, en az-türlü filmle doldurulur; baskın türler (Drama/Comedy) "yolcu" olarak en sona atılır (overshoot azaltma). Ayarlar: `PER_GENRE=3000`, `MIN_VOTES=10`, `POOL_FACTOR=1.5`. Aday havuzu ~37k film.

**`vote_count` eşiği neden 10?** `vote_count` bir kalite skoru değil, **popülerlik/bilinirlik** ölçüsüdür. Ama filtresiz (`≥0`) çekim çöp doludur (örn. Documentary `≥0` = 220.948 girdi: kısa film / TV / postersiz / amatör). `≥30` ise rare türleri kısıyordu (History 2.149). Türlerin oy eşiğine göre mevcut film sayısı (TMDB `total_results`):

| Tür | ≥0 | ≥5 | ≥10 | ≥30 |
|---|---|---|---|---|
| History | 21.910 | 5.712 | 3.850 | 2.149 |
| Documentary | 220.948 | 17.450 | 8.485 | 2.621 |
| Animation | 70.028 | 11.364 | 7.663 | 4.021 |
| Mystery | 26.302 | 8.670 | 6.359 | 3.572 |
| Fantasy | 29.489 | 8.569 | 6.377 | 3.858 |

→ `≥10` açık çöpü eler **ve** History dahil tüm rare türleri ≥3.850'ye çıkarır → 3.000 hedefi ulaşılabilir, kalite makul.

**Sonuç (`labels_v2.csv`): 23.640 film, ort. 2.18 tür/film, %100 poster kapsamı.**

| Tür | v2 | | Tür | v2 |
|---|---|---|---|---|
| Romance, Mystery, Horror, History, | **3.000** | | Adventure | 3.006 |
| Family, Documentary, Crime, Animation | (her biri) | | Action | 3.762 |
| Science Fiction, Fantasy | 3.001 | | Thriller | 3.852 |
| | | | Comedy | 4.178 |
| | | | **Drama** | **6.658** |

- **Dengesizlik: v1 7.4x → v2 2.22x.** Rare/orta türler **tam 3.000'de**; History 858 → 3.000.
- Kalan baskınlık (Drama 6.658) kaçınılmaz multi-label "yolcu" etkisi; eğitimde **class-weight / weighted sampler** ile telafi edilecek — v1'deki gibi ağır `pos_weight` (aşırı tahmine yol açan) DEĞİL.
- Çoklu-etiket dağılımı: 1 tür → 4.575, 2 → 10.632, 3 → 8.113, 4 → 320 film (v1'de max 8 idi, daha temiz).
- Figür: `dist_before_after.png` (çekim öncesi v1 vs sonrası v2).
- **Ban almadan** tamamlandı (HTML scraping'de 3 saatte ~500 film + ban idi; API ile tamamı tek oturumda).

## 6. Phase B — Ön İşleme + 5-Fold CV (tamamlandı)

`labels_v2.csv` (23.640 film) yüklendi, 15 hedef türe filtrelendi, poster varlık+boyut kontrolü (**0 satır düştü, %100 sağlam**). `MultiLabelBinarizer` (15 sınıf) → `mlb.pkl`.

**5-fold CV** (`MultilabelStratifiedKFold`, seed=42): her fold ~18.900 train / ~4.730 val.
- **CV bütünlüğü:** train∩val overlap = 0; her film **tam 1** val fold'unda (tüm val birleşimi = 23.640 benzersiz).
- **Stratifikasyon mükemmel:** her türün val oranı 5 fold'da neredeyse özdeş (Drama %28.1–28.3, Action %15.9–16.0, History %12.7–12.8). Multi-label dağılımı korunuyor.
- Değerlendirme Phase D'de **OOF** (out-of-fold) ile yapılacak; ayrı hold-out yok.
- Çıktılar: `folds/fold_{0..4}_{train,val}.csv`, `mlb.pkl`, `cooccurrence_v2.png` (15×15 birlikte-geçiş matrisi).

## 7. Phase C — Pilot Bulgusu (ViT × fold 0, T4)

İlk fine-tune pilotu (ViT-base, fold 0, 6 epoch, Colab T4):
- **Val Macro F1 = 0.471** (en iyi, epoch 5). Karşılaştırma: v1 Scratch CNN 0.333, Frozen baseline 0.383 → **transformer fine-tune belirgin sıçrama (+0.09)**, üstelik en hafif modelle.
- **Aşırı öğrenme ep5 sonrası:** train loss 0.064'e inerken val loss yükseliyor (0.33→0.35); val F1 ep5 tepe, ep6 düşüş → **EPOCHS=5** yeterli (best-by-F1 checkpoint en iyi epoch'u saklar).
- **Süre:** T4'te 32 dk/koşu → 25 koşu ≈ **13.5 saat** (T4 için fazla) → **A100'e geçildi** (BATCH 32→64, tahmini ~2-4 saat).
- Inference ~9.6 ms/görsel. (mlb sürüm uyarısı zararsız — sınıflar doğru yüklendi.)
- Full koşu **resumable**: kopmada tamamlanmış (model, fold) atlanır.

## 8. Phase C — Tam Koşu Sonuçları (25 model, A100)

5 model × 5 fold = 25 koşu A100'de tamamlandı (toplam ~113 dk eğitim).
**Verimlilik notu:** posterler Drive FUSE'tan okununca A100 veri-bound kalıyordu (epoch ~5 dk, ekranda ilerleme yok gibi); posterler `/content` (lokal SSD)'ye açılıp `num_workers=8 + persistent_workers + AMP` ile **~30 sn/epoch (~10x T4)** → tüm koşu ~1 saat. (Rapor için iyi bir "veri pipeline" notu.)

**Val Macro F1 (5-fold ortalaması, 0.5 eşiği — Phase D'de per-sınıf threshold ile daha yüksek olacak):**

| Model | Val Macro F1 | Not |
|---|---|---|
| **Swin** | **0.530** | en iyi 🥇 |
| BeiT | 0.492 | |
| DeiT | 0.477 | |
| ViT | 0.472 | |
| CvT | 0.381 | en zayıf (küçük/eski arch) |
| _v1 Frozen baseline_ | _0.383_ | referans |
| _v1 Scratch CNN_ | _0.333_ | referans |

- **Swin, v1 baseline'ı (0.383) ezici geçti: +0.147 (~%38 görece).** CvT hariç tüm transformerlar baseline'ı net aştı.
- Fold'lar arası varyans düşük → sonuçlar tutarlı/sağlam.
- CvT baseline seviyesinde kaldı; "çalışan" model (şartı karşılar) + mimari karşılaştırması için iyi veri noktası.
- Inference ~1.6 ms/görsel. Eğitim/fold: ViT/DeiT/BeiT ~4 dk, Swin ~5-8 dk, CvT ~4.5 dk.

## 9. Phase D — Değerlendirme Sonuçları

OOF (5-fold birleşik, 23.640 film), per-sınıf threshold-optimize. **En iyi: Swin.**

| Model | Macro F1 | Micro F1 | Macro AUC |
|---|---|---|---|
| **Swin** | **0.562** | 0.566 | 0.862 |
| BeiT | 0.534 | 0.539 | 0.844 |
| ViT | 0.527 | 0.535 | 0.841 |
| DeiT | 0.524 | 0.530 | 0.836 |
| CvT | 0.501 | 0.509 | 0.823 |
| _v1 Frozen baseline_ | _0.383_ | | |
| _v1 Scratch CNN_ | _0.333_ | | |

- **Swin 0.562 vs v1 0.383 → +0.179 (~%47 görece).** 5 transformer da v1'i geçti (CvT bile 0.501; threshold tuning CvT'yi 0.381→0.501 toparladı).
- ✅ **Over-prediction çözüldü:** ortalama tahmin **~2.3-2.5 tür/film** (gerçek 2.18); v1'de 5-7 idi.
- ✅ **Frekans biası gitti:** en iyi tür artık **Animation 0.863** (AUC 0.98); **History 0.10→0.47, Documentary 0.11→0.59**; Drama 0.61 / Comedy 0.64 artık zirvede değil → gerçek görsel öğrenme.
- En zayıf türler: Fantasy 0.42, Mystery 0.43, Crime 0.44 (görsel olarak en belirsiz). Specificity 0.78–0.99.
- **Cheat riski:** kombinasyon-dengeli veri + rare türlerdeki büyük iyileşme co-occurrence cheat'in baskın olmadığını gösteriyor; raporda "tamamen elenmedi" notu düşülecek (ayrı test kurulmadı — karar gereği).
- Figürler: `figures/` (per_class_f1_models, confusion_swin, roc_swin, loss_curves, samples_swin).

## 10. Açık Sorular / Sonraki Adımlar
- [x] Phase A, B, C, D tamam — proje teknik olarak bitti, hedef bandı (0.48-0.55) aşıldı.
- [ ] **Notebook 09 temizliği** + notebook 10 outputs'lu commit.
- [ ] **IEEE .docx rapor** (tüm bölümler + figürler/tablolar) + vize veri toplama/temizleme raporu.
- [ ] **Drive paylaşımı** urhanh@gmail.com'a (kod + veri + figürler).

> _Bu dosya her fazda güncellenecek._
