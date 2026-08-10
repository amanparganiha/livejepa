"""The Predictor — the only trained component.

Maps a sequence of frozen V-JEPA 2 visual tokens (optionally conditioned on
a text query) to a single predicted target embedding in the SONAR space.

A learned query token pools the visual sequence (Perceiver-style), then a
projection maps to the SONAR dimension. Bi-directional attention (no causal
mask) lets visual and query tokens attend jointly, as in VL-JEPA.
"""
from __future__ import annotations
import torch
import torch.nn as nn


class Predictor(nn.Module):
    def __init__(self, vis_dim=1024, hidden_dim=768, out_dim=1024,
                 depth=4, heads=8, dropout=0.1):
        super().__init__()
        self.in_proj = nn.Linear(vis_dim, hidden_dim)
        enc_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim, nhead=heads, dim_feedforward=4 * hidden_dim,
            dropout=dropout, activation="gelu", batch_first=True, norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(enc_layer, num_layers=depth)
        self.query = nn.Parameter(torch.randn(1, 1, hidden_dim) * 0.02)
        self.norm = nn.LayerNorm(hidden_dim)
        self.out_proj = nn.Linear(hidden_dim, out_dim)

    def forward(self, vis_tokens, query_emb=None, vis_mask=None):
        """vis_tokens: (B, N, vis_dim)
           query_emb:  (B, Q, hidden_dim) optional text-query embeddings
           vis_mask:   (B, N) optional bool padding mask (True = keep)
           returns:    (B, out_dim) predicted SONAR embedding."""
        x = self.in_proj(vis_tokens)                     # (B, N, H)
        B = x.size(0)
        q = self.query.expand(B, -1, -1)                 # (B, 1, H)
        parts = [q, x]
        keep = [torch.ones(B, 1, dtype=torch.bool, device=x.device),
                vis_mask if vis_mask is not None
                else torch.ones(B, x.size(1), dtype=torch.bool, device=x.device)]
        if query_emb is not None:
            parts.append(query_emb)
            keep.append(torch.ones(B, query_emb.size(1), dtype=torch.bool,
                                   device=x.device))
        h = torch.cat(parts, dim=1)                      # (B, 1+N(+Q), H)
        h = self.encoder(h, src_key_padding_mask=~torch.cat(keep, dim=1))
        pooled = self.norm(h[:, 0])                      # take the learned query slot
        return self.out_proj(pooled)                     # (B, out_dim)
