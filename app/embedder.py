"""Local embedding backend — multilingual-e5-base, off the Gemini API.

Why local (decision 2026-06-18): ~10x faster round trip (52ms vs 524ms), no
free-tier quota wall, data stays on-prem (DPDPA), and it's Hinglish-robust where
English-only models collapsed (see scripts/eval_embedding_accuracy.py).

e5 specifics: needs a 'query:' prefix on queries and 'passage:' on documents,
MEAN pooling over tokens, then L2-normalize. 768-dim → matches the Pinecone index
(no recreate). Model is lazy-loaded once per process and cached (≈3.8s load).
"""
from __future__ import annotations

import threading

from app.config import settings

_lock = threading.Lock()
_tok = None
_model = None
_device = "cpu"


def _resolve_device() -> str:
    """Pick the compute device. EMBEDDING_DEVICE = auto|cuda|cpu (default auto).
    'auto'/'cuda' use the GPU only if a CUDA-enabled torch + GPU are present;
    otherwise fall back to CPU — so this is a no-op until CUDA torch is installed."""
    import torch

    pref = getattr(settings, "EMBEDDING_DEVICE", "auto").lower()
    if pref == "cpu":
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _load() -> None:
    """Lazy, thread-safe one-time load of the tokenizer + model (onto the device)."""
    global _tok, _model, _device
    if _model is not None:
        return
    with _lock:
        if _model is not None:
            return
        from transformers import AutoModel, AutoTokenizer

        name = settings.LOCAL_EMBEDDING_MODEL
        dev = _resolve_device()
        tok = AutoTokenizer.from_pretrained(name)
        model = AutoModel.from_pretrained(name)
        model.eval().to(dev)
        _tok, _model, _device = tok, model, dev
        print(f"[embedder] {name} loaded on {dev}")


def _mean_pool(last_hidden, mask):
    m = mask.unsqueeze(-1).float()
    return (last_hidden * m).sum(1) / m.sum(1).clamp(min=1e-9)


def embed_texts(texts: list[str], is_query: bool) -> list[list[float]]:
    """Embed a list of texts. Applies the e5 prefix, batches, returns plain
    Python lists (Pinecone-ready). `is_query` picks 'query:' vs 'passage:'."""
    import torch
    import torch.nn.functional as F

    _load()
    prefix = "query: " if is_query else "passage: "
    out: list[list[float]] = []
    bs = max(1, settings.LOCAL_EMBEDDING_BATCH)
    for i in range(0, len(texts), bs):
        batch = [prefix + (t or "") for t in texts[i : i + bs]]
        enc = _tok(batch, padding=True, truncation=True, max_length=512, return_tensors="pt")
        enc = {k: v.to(_device) for k, v in enc.items()}  # inputs → GPU/CPU
        with torch.no_grad():
            o = _model(**enc)
        v = _mean_pool(o.last_hidden_state, enc["attention_mask"])
        v = F.normalize(v, p=2, dim=1)
        out.extend(v.cpu().tolist())  # back to CPU for plain-list output
    return out


def embed_one(text: str, is_query: bool) -> list[float]:
    return embed_texts([text], is_query)[0]
