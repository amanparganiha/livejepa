"""SONAR text encoder + decoder wrapper.

SONAR is chosen over EmbeddingGemma because it is *invertible*: it ships
both a text->embedding encoder and an embedding->text decoder, so the
predicted embeddings can be turned back into captions exactly.

Supports two backends (fairseq2 / transformers) and a stub fallback that
maps text<->vector with a fixed hashing scheme so the pipeline runs
end-to-end before SONAR is installed.
"""
from __future__ import annotations
import hashlib
import numpy as np


class SonarSpace:
    def __init__(self, cfg):
        self.cfg = cfg
        self.use_stubs = cfg["project"]["use_stubs"]
        sc = cfg["encoders"]["sonar"]
        self.dim = sc["embed_dim"]
        self.lang = sc["lang"]
        self.max_seq_len = sc["max_seq_len"]
        self.beam = sc["beam_size"]
        self.backend = sc["backend"]
        self._t2v = None
        self._v2t = None
        self._stub_vocab = {}  # text -> vector, for round-tripping in stub mode
        if not self.use_stubs:
            self._load_real()

    def _load_real(self):
        if self.backend == "fairseq2":
            from sonar.inference_pipelines.text import (
                TextToEmbeddingModelPipeline, EmbeddingToTextModelPipeline,
            )
            sc = self.cfg["encoders"]["sonar"]
            dev = self.cfg["project"]["device"]
            self._t2v = TextToEmbeddingModelPipeline(sc["encoder"], sc["encoder"], device=dev)
            self._v2t = EmbeddingToTextModelPipeline(sc["decoder"], sc["encoder"], device=dev)
        else:
            # transformers-format M2M100 ports (the Windows / no-fairseq2 path)
            import torch
            from transformers import AutoTokenizer, M2M100ForConditionalGeneration
            from transformers.models.m2m_100.modeling_m2m_100 import M2M100Encoder
            sc = self.cfg["encoders"]["sonar"]
            self._device = torch.device(self.cfg["project"]["device"]
                                        if torch.cuda.is_available() else "cpu")
            self._enc_tok = AutoTokenizer.from_pretrained(sc["hf_encoder"])
            self._enc_tok.src_lang = self.lang
            self._encoder = M2M100Encoder.from_pretrained(sc["hf_encoder"]).eval().to(self._device)
            self._dec_tok = None
            self._decoder = None  # ~2.6 GB — loaded lazily on first decode()

    def _ensure_decoder(self):
        if self._decoder is None:
            from transformers import AutoTokenizer, M2M100ForConditionalGeneration
            sc = self.cfg["encoders"]["sonar"]
            self._dec_tok = AutoTokenizer.from_pretrained(sc["hf_decoder"])
            self._decoder = M2M100ForConditionalGeneration.from_pretrained(
                sc["hf_decoder"]).eval().to(self._device)

    def _hf_encode(self, texts) -> np.ndarray:
        import torch
        with torch.inference_mode():
            batch = self._enc_tok(texts, return_tensors="pt", padding=True).to(self._device)
            seq = self._encoder(**batch).last_hidden_state
            mask = batch.attention_mask.unsqueeze(-1)
            mean = (seq * mask).sum(1) / mask.sum(1)
        return mean.float().cpu().numpy()

    def _hf_decode(self, embeddings: np.ndarray, chunk: int = 16) -> list[str]:
        import torch
        from transformers.modeling_outputs import BaseModelOutput
        self._ensure_decoder()
        texts = []
        with torch.inference_mode():
            for i in range(0, len(embeddings), chunk):  # chunk to fit small GPUs
                emb = torch.tensor(embeddings[i:i + chunk], dtype=torch.float32,
                                   device=self._device)
                enc_out = BaseModelOutput(last_hidden_state=emb.unsqueeze(1))
                ids = self._decoder.generate(
                    encoder_outputs=enc_out,
                    forced_bos_token_id=self._dec_tok.convert_tokens_to_ids(self.lang),
                    max_length=self.max_seq_len,
                    num_beams=self.beam,
                )
                texts.extend(self._dec_tok.batch_decode(ids, skip_special_tokens=True))
        return texts

    # ---------- encode ----------
    def encode(self, texts) -> np.ndarray:
        if isinstance(texts, str):
            texts = [texts]
        if self.use_stubs:
            vecs = np.stack([self._stub_encode(t) for t in texts])
            return vecs
        if self.backend != "fairseq2":
            return self._hf_encode(texts)
        emb = self._t2v.predict(texts, source_lang=self.lang)
        return np.asarray(emb)

    # ---------- decode ----------
    def decode(self, embeddings) -> list[str]:
        embeddings = np.atleast_2d(np.asarray(embeddings, dtype=np.float32))
        if self.use_stubs:
            return [self._stub_decode(e) for e in embeddings]
        if self.backend != "fairseq2":
            return self._hf_decode(embeddings)
        import torch
        emb_t = torch.tensor(embeddings, dtype=torch.float32)
        return list(self._v2t.predict(
            emb_t, target_lang=self.lang, max_seq_len=self.max_seq_len, beam_size=self.beam
        ))

    # ---------- stub round-trip ----------
    def _stub_encode(self, text: str) -> np.ndarray:
        h = hashlib.sha256(text.encode()).digest()
        seed = int.from_bytes(h[:8], "little")
        rng = np.random.default_rng(seed)
        v = rng.standard_normal(self.dim).astype(np.float32)
        v /= (np.linalg.norm(v) + 1e-8)
        self._stub_vocab[tuple(np.round(v, 4))] = text  # remember for decode
        return v

    def _stub_decode(self, vec: np.ndarray) -> str:
        if not self._stub_vocab:
            return "<stub: no captions encoded yet>"
        vec = vec / (np.linalg.norm(vec) + 1e-8)
        keys = np.array(list(self._stub_vocab.keys()), dtype=np.float32)
        sims = keys @ vec
        best = list(self._stub_vocab.values())[int(np.argmax(sims))]
        return best
