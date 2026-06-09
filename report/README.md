# Rapor — Overleaf kullanımı

Dosya: `MustafaKeremCekici_231307121.tex` (IEEEtran conference, Türkçe).

## Adımlar
1. **Overleaf**'te yeni proje aç (Blank Project). `main.tex` içeriğini bu `.tex` dosyasının
   içeriğiyle değiştir. Derleyici **pdfLaTeX** olmalı (Türkçe karakterler için
   `inputenc utf8` + `fontenc T1` zaten ekli).
2. **Şu PNG'leri Overleaf proje köküne yükle** (Drive'da `film-genre-project-data/`
   altında: `figures/` klasöründen + DATA_ROOT'tan):
   - `dist_before_after.png`
   - `cooccurrence_v2.png`
   - `per_class_f1_models.png`
   - `confusion_swin.png`
   - `roc_swin.png`
   - `loss_curves.png`
   - `samples_swin.png`
3. Başlık bloğundaki **`[Üniversite Adı]`** ve şehir alanlarını doldur.
4. **Derle** → PDF.
5. Teslim: **urhanh@gmail.com**'a Overleaf'ten *düzenleme yetkili* paylaşım ver; ayrıca
   Drive (kod + veri + figürler) paylaşım linkini ve PDF'i rapora/teslime ekle.

## Notlar
- Rapor LaTeX rotasıyla yazıldı (PDF isterleri buna izin veriyor: "Dileyenler overleaf
  üzerinden latex olarak yazabilir... urhanh@gmail.com'a düzenleme yetkili paylaşım").
- §II (Veri Toplama ve Temizleme) aynı zamanda **vize veri raporu**nun çekirdeğidir;
  vize için bu bölüm + BULGULAR.md §1-6 genişletilerek ayrı dosya yapılabilir.
- Tüm sayılar `notebooks/10_evaluate.ipynb` çıktılarından ve BULGULAR.md §8-9'dan gelir.
