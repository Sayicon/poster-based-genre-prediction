<img src="https://capsule-render.vercel.app/api?type=waving&color=0:16213e,100:0f3460&height=180&section=header&text=Poster%20Genre%20AI&fontSize=52&fontColor=fff&animation=fadeIn&fontAlignY=36&desc=Multi-Label%20Vision%20Transformer%20%7C%20Kocaeli%20%C3%9Cniversitesi&descSize=16&descColor=ccc&descAlignY=58" width="100%"/>

# 🎬 Poster-Based Multi-Label Genre Prediction

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.x-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![HuggingFace](https://img.shields.io/badge/🤗_Transformers-4.x-FFD21E)](https://huggingface.co/docs/transformers)
[![Colab](https://img.shields.io/badge/Training-Colab_A100-F9AB00?logo=googlecolab&logoColor=white)](https://colab.research.google.com/github/Sayicon/poster-based-genre-prediction/blob/main/notebooks/09_train_transformer.ipynb)

> **Kocaeli Üniversitesi — Bilişim Sistemleri Mühendisliği — Final Projesi**  
> Mustafa Kerem Çekici · 231307121

Given only a movie poster image, predict all of its genres simultaneously — a **multi-label image classification** problem with 15 target genres. Five vision transformers (ViT, DeiT, BeiT, Swin, CvT) are fine-tuned from ImageNet weights and evaluated with 5-fold cross-validation.

> **Note on posters:** Movie posters are copyrighted by their respective rights holders and are **not** included in this repository. The provided TMDB API client (`src/data/tmdb_api.py`) collects metadata and poster URLs via the [TMDB API](https://developer.themoviedb.org/). Posters are downloaded at runtime for research purposes only and must not be redistributed. *This product uses the TMDB API but is not endorsed or certified by TMDB.*

---

## 📊 Results

| Model | Macro F1 | Micro F1 | Macro AUC | Macro Acc | Macro Spec |
|:------|:--------:|:--------:|:---------:|:---------:|:----------:|
| **Swin** ⭐ | **0.562** | **0.566** | **0.862** | **0.867** | **0.912** |
| BeiT | 0.534 | 0.539 | 0.844 | 0.860 | 0.908 |
| ViT | 0.527 | 0.535 | 0.841 | 0.860 | 0.909 |
| DeiT | 0.524 | 0.530 | 0.836 | 0.860 | 0.912 |
| CvT | 0.501 | 0.509 | 0.823 | 0.846 | 0.895 |
| *Frozen MobileNetV3 (v1 baseline)* | *0.383* | — | — | — | — |
| *Random (~2.4 genres/film)* | *0.149* | — | — | — | — |

Swin achieves **~3.8× random baseline** and **+47% relative improvement** over the v1 CNN baseline.  
All five transformers beat v1. Per-class thresholds optimized over [0.3, 0.7] to maximize F1. Full per-class breakdown in the [report](report/MustafaKeremCekici_231307121.tex).

---

## 🗂️ Dataset

| Property | Value |
|:---------|:------|
| Source | TMDB Official API (`/discover/movie`) |
| Size | 23,640 films · 100% poster coverage |
| Genres | 15 target genres |
| Avg genres/film | 2.18 |
| Imbalance ratio | 7.4× (v1) → **2.22×** (v2, after balancing) |
| Split | 5-fold `MultilabelStratifiedKFold` · ~18,900 train / ~4,730 val per fold |

**Two-phase balanced sampling:** per-genre candidate pool → deficit-driven greedy selection with dominant-genre penalty. Rare genres (History, Mystery, Animation, …) all reach ~3,000 samples.

---

## 🏗️ Models

All models are `base`-scale HuggingFace `AutoModelForImageClassification` fine-tuned for multi-label classification (`BCEWithLogitsLoss`, no `pos_weight` since data is balanced).

| Model | HuggingFace ID | Notes |
|:------|:---------------|:------|
| ViT | `google/vit-base-patch16-224` | Pure self-attention |
| DeiT | `facebook/deit-base-distilled-patch16-224` | Knowledge distillation |
| BeiT | `microsoft/beit-base-patch16-224-pt22k-ft22k` | Masked image modeling |
| Swin | `microsoft/swin-base-patch4-window7-224` | Hierarchical shifted windows |
| CvT | `microsoft/cvt-13` | Conv-enhanced, smaller capacity |

**Training:** AdamW · LR 5e-5 · cosine warmup · AMP · batch 64 · 5 epochs · Google Colab A100  
**Evaluation:** Out-of-fold (OOF) — every sample is in exactly one validation fold

---

## 📁 Repository Structure

```
poster-based-genre-prediction/
├── src/
│   ├── data/
│   │   └── tmdb_api.py          # TMDB API client: pool + balanced sampler + poster downloader
│   ├── dataset.py               # PosterDataset (multi-label, transforms)
│   ├── transforms.py
│   ├── train.py / eval.py       # Training & evaluation helpers
│   └── model.py / loss.py       # v1 scratch CNN (baseline reference)
│
├── notebooks/
│   ├── 07_api_collect.ipynb     # Phase A: TMDB API balanced data collection
│   ├── 08_preprocess_cv.ipynb   # Phase B: cleaning + 5-fold CV split
│   ├── 09_train_transformer.ipynb  # Phase C: fine-tune 5 transformers (Colab A100)
│   └── 10_evaluate.ipynb        # Phase D: OOF evaluation, metrics, figures
│
├── legacy/                      # Archived v1 HTML scrapers
├── report/
│   └── MustafaKeremCekici_231307121.tex   # IEEE conference report (Turkish)
├── requirements.txt
└── .env.example                 # TMDB_API_KEY, TMDB_BEARER placeholders
```

---

## 🚀 Quick Start

```bash
git clone https://github.com/Sayicon/poster-based-genre-prediction.git
cd poster-based-genre-prediction
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your [TMDB API key](https://developer.themoviedb.org/). Posters are fetched at runtime and must not be redistributed.

```bash
# Collect balanced dataset (~23k films + posters)
python -c "from src.data.tmdb_api import collect_balanced; collect_balanced()"
```

Training and evaluation are designed for **Google Colab** (GPU required):

| Notebook | Purpose | Open |
|:---------|:--------|:----:|
| `08_preprocess_cv.ipynb` | 5-fold split | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Sayicon/poster-based-genre-prediction/blob/main/notebooks/08_preprocess_cv.ipynb) |
| `09_train_transformer.ipynb` | Fine-tune 5 models | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Sayicon/poster-based-genre-prediction/blob/main/notebooks/09_train_transformer.ipynb) |
| `10_evaluate.ipynb` | OOF metrics + figures | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Sayicon/poster-based-genre-prediction/blob/main/notebooks/10_evaluate.ipynb) |

---

## 📋 Key Findings

- **Over-prediction fixed:** all models predict 2.3–2.5 genres/film (true mean 2.18); v1 predicted 5–7.
- **Frequency bias eliminated:** best genre is now **Animation (F1=0.863, AUC=0.980)**, not Drama/Comedy. History improved 0.10 → 0.47; Documentary 0.11 → 0.59.
- **No co-occurrence cheat:** improvement in rare genres proves genuine visual learning over label correlation.
- **Swin is best:** hierarchical local attention outperforms pure ViT — consistent with literature on inductive bias in small-to-medium datasets.
- **Drive I/O was the bottleneck on A100:** copying posters to local SSD (`/content`) gave ~10× speedup (30 s/epoch vs 5+ min).

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0f3460,100:16213e&height=120&section=footer" width="100%"/>
