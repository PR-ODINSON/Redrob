"""
semantic_scorer.py — Sentence-transformer semantic similarity scoring.

Architecture:
  1. Pre-download / cache the model offline (run download_model() once).
  2. Embed the JD text once.
  3. Batch-embed candidate texts (top PRESCREEN_CUTOFF only).
  4. Return cosine similarities as semantic_scores ∈ [-1, 1], clipped to [0, 1].

Model: sentence-transformers/all-MiniLM-L6-v2
  - 80MB on disk, fast on CPU, strong for English professional text
  - Max sequence length: 384 tokens (long texts are truncated)

OFFLINE OPERATION:
  Run `python semantic_scorer.py` once (with network) to download and cache the model.
  Afterwards, the model loads from the local HuggingFace cache without any network calls.
  Set TRANSFORMERS_OFFLINE=1 in the environment during ranking for extra safety.
"""

from __future__ import annotations

import os
import sys
import time
from typing import List

import numpy as np

from config import EMBEDDING_BATCH_SIZE, EMBEDDING_MODEL, EMBEDDING_MAX_SEQ_LEN
from data_loader import build_candidate_text


def download_model() -> None:
    """
    Download and cache the sentence-transformer model.
    Run this once before the ranking step.
    Subsequent loads are fully offline from the HuggingFace local cache.
    """
    print(f"Downloading model: {EMBEDDING_MODEL}")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMBEDDING_MODEL)
    # Trigger a dummy encode to fully materialise weights in cache
    model.encode(["test"], show_progress_bar=False)
    cache_dir = os.path.expanduser("~/.cache/huggingface")
    print(f"Model cached at: {cache_dir}")
    print("Model download complete. You can now run the ranking step offline.")


def load_model():
    """Load the sentence-transformer model from local cache (no network needed)."""
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMBEDDING_MODEL)
    model.max_seq_length = EMBEDDING_MAX_SEQ_LEN
    return model


def embed_texts(model, texts: List[str], show_progress: bool = False) -> np.ndarray:
    """
    Batch-embed a list of texts.
    Returns a 2D numpy array of shape (len(texts), embedding_dim).
    Normalised to unit vectors for efficient cosine similarity via dot product.
    """
    embeddings = model.encode(
        texts,
        batch_size=EMBEDDING_BATCH_SIZE,
        show_progress_bar=show_progress,
        normalize_embeddings=True,   # L2 norm → cosine sim = dot product
        convert_to_numpy=True,
    )
    return embeddings


def embed_jd(model, jd_data: dict) -> np.ndarray:
    """Embed the job description text. Returns shape (1, dim)."""
    jd_text = jd_data["embedding_text"]
    return embed_texts(model, [jd_text], show_progress=False)


def score_semantic_batch(
    model,
    jd_embedding: np.ndarray,
    candidates: list[dict],
    show_progress: bool = False,
) -> np.ndarray:
    """
    Compute semantic similarity scores for a list of candidates.

    Returns a 1D numpy array of cosine similarities ∈ [0, 1].
    Negative similarities (anti-correlated) are clipped to 0.

    Timing note: ~10–15 seconds for 3000 candidates on CPU with MiniLM.
    """
    texts = [build_candidate_text(c) for c in candidates]

    t0 = time.time()
    candidate_embeddings = embed_texts(model, texts, show_progress=show_progress)
    elapsed = time.time() - t0

    if show_progress:
        print(f"  Embedded {len(candidates)} candidates in {elapsed:.1f}s "
              f"({len(candidates)/elapsed:.0f} cands/sec)")

    # Cosine similarity: since embeddings are unit-normalised, this is just a dot product
    # jd_embedding shape: (1, dim), candidate_embeddings: (N, dim)
    similarities = (candidate_embeddings @ jd_embedding.T).squeeze()  # shape (N,)

    # Clip to [0, 1] — negative cosine similarity is meaningless here
    return np.clip(similarities, 0.0, 1.0)


# ─────────────────────────────────────────────────────────────
# CLI entry point: download model for offline use
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    download_model()
