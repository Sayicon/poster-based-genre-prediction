import numpy as np
import torch
from sklearn.metrics import f1_score, hamming_loss


def _collect(model, loader, device):
    model.eval()
    probs, targets = [], []
    with torch.no_grad():
        for imgs, labels in loader:
            probs.append(torch.sigmoid(model(imgs.to(device))).cpu().numpy())
            targets.append(labels.numpy())
    return np.vstack(probs), np.vstack(targets)


def find_best_thresholds(model, loader, device, n_classes, grid=None):
    if grid is None:
        grid = np.arange(0.3, 0.71, 0.05)

    probs, targets = _collect(model, loader, device)
    thresholds = np.full(n_classes, 0.5)
    for c in range(n_classes):
        best_t, best_f1 = 0.5, 0.0
        for t in grid:
            f1 = f1_score(targets[:, c], (probs[:, c] > t).astype(int), zero_division=0)
            if f1 > best_f1:
                best_f1, best_t = f1, t
        thresholds[c] = best_t
    return thresholds


def evaluate(model, loader, device, thresholds):
    probs, targets = _collect(model, loader, device)
    preds = (probs > thresholds).astype(int)
    return {
        "macro_f1": f1_score(targets, preds, average="macro", zero_division=0),
        "micro_f1": f1_score(targets, preds, average="micro", zero_division=0),
        "hamming_loss": hamming_loss(targets, preds),
        "per_class_f1": f1_score(targets, preds, average=None, zero_division=0),
    }
