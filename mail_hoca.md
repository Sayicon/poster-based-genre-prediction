**Konu:** Pipeline, Model Mimarisi ve Veriye Yaklaşım Hakkında

Sayın Zeynep Hocam,

İyi günler. Bugünkü proje sunumu sırasındaki mimari tartışmasından sonra multi-label sınıflandırma problemine nasıl yaklaşacağımı araştırdım ve literatürdeki standart yöntemi inceledim. Düşüncelerimi sizinle paylaşmak istedim.

---

## Multi-label Binary Classification

Sunum sırasında konuştuğumuz "her türe unique sayı atama" fikri matematiksel olarak sağlam (Gödel numaralandırması ile örtüşüyor) ancak ML bağlamında uygulanabilir değil; çünkü 15 tür için 2^15 = 32.768 olası kombinasyon ortaya çıkıyor ve loss fonksiyonu bu sayılar arasındaki ilişkiyi öğrenemiyor.

Literatürdeki standart yaklaşım her tür için bağımsız bir nöron kullanmak:

```
Model çıktısı (N_CLASSES nöron):

  Action    → 0.87  > 0.5 → Tahmin: Evet
  Adventure → 0.76  > 0.5 → Tahmin: Evet
  Horror    → 0.12  < 0.5 → Tahmin: Hayır
  Comedy    → 0.03  < 0.5 → Tahmin: Hayır
```

Hem Aksiyon hem Macera olan bir film için hedef vektör:

```
[1, 1, 0, 0, 0, ...]
```

Model bunu tek geçişte tahmin eder. N türlü tek büyük bir soru sormak yerine N tane bağımsız "evet/hayır" sorusu sorulur.

---

## Pipeline'da Uygulama

Eğitimde her nöron için ayrı Binary Cross Entropy hesaplanır, ortalaması alınır:

```python
# Hedef : [1, 1, 0, 0, ...]
# Çıktı : [0.87, 0.76, 0.12, 0.03, ...]
loss = BCEWithLogitsLoss(output, target)   # her pozisyon bağımsız
```

Inference aşamasında her nöron için ayrı threshold uygulanır:

```python
preds = (sigmoid(logits) > thresholds)
```

MultiLabelBinarizer string etiketleri otomatik olarak vektöre dönüştürür:

```python
["Action", "Adventure"]  →  [1, 1, 0, 0, 0, ...]
```

Threshold değerleri per-class olarak optimize edilebildiğinden azınlık türler için hassasiyeti ayrıca artırmak mümkün.

---

Görüşlerinizi almak isterim.

İyi çalışmalar,
Kerem Çekici
