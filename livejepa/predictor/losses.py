"""Training losses for the predictor.

VL-JEPA uses InfoNCE (alignment + uniformity, which also prevents collapse).
We add a cosine-regression term for early-training stability.
"""
from __future__ import annotations
import torch
import torch.nn.functional as F


def info_nce(pred, target, temp=0.07):
    """Bi-directional InfoNCE between predicted and target embeddings.
    pred, target: (B, d)."""
    p = F.normalize(pred, dim=-1)
    t = F.normalize(target, dim=-1)
    logits = p @ t.t() / temp                    # (B, B)
    labels = torch.arange(p.size(0), device=p.device)
    loss_pt = F.cross_entropy(logits, labels)
    loss_tp = F.cross_entropy(logits.t(), labels)
    return 0.5 * (loss_pt + loss_tp)


def cosine_reg(pred, target):
    return (1.0 - F.cosine_similarity(pred, target, dim=-1)).mean()


def predictor_loss(pred, target, temp=0.07, cosine_weight=1.0):
    nce = info_nce(pred, target, temp)
    cos = cosine_reg(pred, target)
    total = nce + cosine_weight * cos
    return total, {"info_nce": nce.item(), "cosine": cos.item(), "total": total.item()}
