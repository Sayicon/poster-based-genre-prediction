import torch
import torch.nn as nn
import torch.nn.functional as F


class FocalLoss(nn.Module):
    def __init__(self, gamma: float = 2.0, pos_weight=None):
        super().__init__()
        self.gamma = gamma
        self.pos_weight = pos_weight

    def forward(self, logits, targets):
        bce = F.binary_cross_entropy_with_logits(
            logits, targets, pos_weight=self.pos_weight, reduction="none"
        )
        p = torch.sigmoid(logits)
        pt = targets * p + (1 - targets) * (1 - p)
        return ((1 - pt) ** self.gamma * bce).mean()


def build_loss(pos_weight=None, focal: bool = False, gamma: float = 2.0) -> nn.Module:
    if focal:
        return FocalLoss(gamma=gamma, pos_weight=pos_weight)
    return nn.BCEWithLogitsLoss(pos_weight=pos_weight)
