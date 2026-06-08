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

## 5. Açık Sorular / Sonraki Adımlar
- [ ] TMDB API key alınacak (kullanıcı; ücretsiz hesap) → Colab secret olarak verilecek.
- [ ] API ile dengeli + kombinasyon-farkında çekim.
- [ ] CV split, 5 transformer fine-tune, tam metrik/figür üretimi.

> _Bu dosya her fazda güncellenecek._
