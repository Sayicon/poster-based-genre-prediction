from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import f1_score
from torch.utils.data import DataLoader, WeightedRandomSampler


def _macro_f1(model, loader, device, threshold=0.5):
    model.eval()
    all_preds, all_targets = [], []
    with torch.no_grad():
        for imgs, labels in loader:
            preds = (torch.sigmoid(model(imgs.to(device))) > threshold).cpu().numpy()
            all_preds.append(preds)
            all_targets.append(labels.numpy())
    return f1_score(np.vstack(all_targets), np.vstack(all_preds), average="macro", zero_division=0)


def _make_sampler(dataset):
    label_sums = dataset.labels.sum(axis=0)
    class_weights = 1.0 / (label_sums + 1e-6)
    sample_weights = (dataset.labels * class_weights).sum(axis=1)
    return WeightedRandomSampler(sample_weights.tolist(), len(sample_weights))


def train(model, train_ds, val_ds, cfg: dict):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)

    train_loader = DataLoader(
        train_ds, batch_size=cfg["batch_size"],
        sampler=_make_sampler(train_ds), num_workers=cfg.get("num_workers", 2),
    )
    val_loader = DataLoader(
        val_ds, batch_size=cfg["batch_size"],
        shuffle=False, num_workers=cfg.get("num_workers", 2),
    )

    optimizer = torch.optim.AdamW(
        model.parameters(), lr=cfg["lr"], weight_decay=cfg.get("weight_decay", 1e-4)
    )
    n_epochs = cfg["epochs"]
    warmup = cfg.get("warmup_epochs", 3)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=n_epochs - warmup)
    criterion = cfg["criterion"]

    ckpt_path = Path(cfg["checkpoint_dir"]) / "best.pt"
    ckpt_path.parent.mkdir(parents=True, exist_ok=True)

    best_f1, no_improve = 0.0, 0
    patience = cfg.get("patience", 10)

    for epoch in range(1, n_epochs + 1):
        if epoch <= warmup:
            for pg in optimizer.param_groups:
                pg["lr"] = cfg["lr"] * epoch / warmup

        model.train()
        total_loss = 0.0
        for imgs, labels in train_loader:
            imgs, labels = imgs.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(imgs), labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        if epoch > warmup:
            scheduler.step()

        val_f1 = _macro_f1(model, val_loader, device)
        print(f"Epoch {epoch}/{n_epochs}  loss={total_loss/len(train_loader):.4f}  val_macro_f1={val_f1:.4f}")

        if val_f1 > best_f1:
            best_f1, no_improve = val_f1, 0
            torch.save(model.state_dict(), ckpt_path)
        else:
            no_improve += 1
            if no_improve >= patience:
                print(f"Early stopping at epoch {epoch}")
                break

    print(f"Best val Macro F1: {best_f1:.4f}")
    return best_f1
