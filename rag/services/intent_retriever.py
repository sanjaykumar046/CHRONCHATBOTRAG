import hashlib
import json
from pathlib import Path

import numpy as np
import requests

from rag.config import EMBEDDING_BASE_URL, EMBEDDING_MODEL, SIMILARITY_SCORE


class IntentRetriever:
    """
    Narrows the API Registry down to the top-K most relevant intents for
    a given question, using embedding similarity.

    Embeddings are computed once and cached to disk (registry/intent_cache.json).
    On future runs, if the registry hasn't changed, the cache is loaded
    instantly instead of re-calling the embedding model 163 times.

    Responsibilities
    -----------------
    - Embed each registry entry (once, cached)
    - Embed the incoming question
    - Rank registry entries by cosine similarity
    - Return the top-K candidates for the LLM to do final selection on

    Does NOT:
    - Call the classification LLM
    - Make the final intent decision - it only narrows candidates
    """

    def __init__(self, registry: list, cache_path: str = None):
        self.registry = registry

        project_root = Path(__file__).resolve().parents[2]
        self.cache_path = Path(cache_path) if cache_path else (
            project_root / "registry" / "intent_cache_v2.json"
        )

        self.registry_hash = self._hash_registry(registry)
        self.entry_vectors = self._load_or_build_cache()

    # ------------------------------------------------------------
    # Cache handling
    # ------------------------------------------------------------

    def _hash_registry(self, registry: list) -> str:
        """
        Fingerprint of the registry contents. If the registry changes
        (entries added/edited), the hash changes and the cache rebuilds
        automatically.
        """
        raw = json.dumps(registry, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _load_or_build_cache(self) -> np.ndarray:
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)

                if cached.get("registry_hash") == self.registry_hash:
                    print(f"[IntentRetriever] Loaded cached embeddings ({len(cached['vectors'])} entries)")
                    return np.array(cached["vectors"], dtype=np.float32)
                else:
                    print("[IntentRetriever] Registry changed - rebuilding embedding cache...")
            except (json.JSONDecodeError, KeyError):
                print("[IntentRetriever] Cache file corrupt - rebuilding...")

        return self._build_and_cache()

    def _build_and_cache(self) -> np.ndarray:
        print(f"[IntentRetriever] Embedding {len(self.registry)} registry entries "
              f"(one-time setup, this may take a minute)...")

        vectors = []
        for i, entry in enumerate(self.registry):
            text = self._entry_to_text(entry)
            vectors.append(self._embed_text(text))
            if (i + 1) % 20 == 0:
                print(f"[IntentRetriever]   {i + 1}/{len(self.registry)} embedded...")

        matrix = np.vstack(vectors)

        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump({
                "registry_hash": self.registry_hash,
                "vectors": matrix.tolist()
            }, f)

        print(f"[IntentRetriever] Embedding cache saved to {self.cache_path}")
        return matrix

    # ------------------------------------------------------------
    # Embedding helpers
    # ------------------------------------------------------------

    def _embed_text(self, text: str) -> np.ndarray:
        response = requests.post(
            f"{EMBEDDING_BASE_URL}/api/embeddings",
            json={
                "model": EMBEDDING_MODEL,
                "prompt": text
            },
            timeout=60
        )
        # Ollama's current embedding endpoint is /api/embed (input plus an
        # embeddings array); retain support for older Ollama servers too.
        if response.status_code == 404:
            response = requests.post(
                f"{EMBEDDING_BASE_URL}/api/embed",
                json={"model": EMBEDDING_MODEL, "input": text},
                timeout=60
            )
        response.raise_for_status()
        data = response.json()
        embedding = data.get("embedding")
        if embedding is None:
            embeddings = data.get("embeddings")
            if not embeddings:
                raise ValueError("Embedding response did not contain an embedding vector.")
            embedding = embeddings[0]
        return np.array(embedding, dtype=np.float32)

    def _entry_to_text(self, entry: dict) -> str:
        # Description carries core signal. Example Questions (hand-written,
        # real phrasing - NOT the templated "User Questions" column) adds
        # vocabulary diversity so retrieval matches how users actually ask.
        return (
            f"{entry.get('Intent Name', '').replace('_', ' ')}. "
            f"{entry.get('Description', '')} "
            f"{entry.get('Example questions', '')}"
        )

    # ------------------------------------------------------------
    # Similarity search
    # ------------------------------------------------------------

    def _cosine_similarity(self, query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
        matrix_norm = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10)
        return matrix_norm @ query_norm

    def get_top_candidates(self, question: str, k: int = 10, min_score: float = None) -> list:
        """
        Return the top-K registry entries most similar to the question,
        ranked highest similarity first. Entries below the similarity
        threshold are excluded - if nothing clears the bar, returns [].
        """
        threshold = min_score if min_score is not None else SIMILARITY_SCORE

        query_vec = self._embed_text(question)
        scores = self._cosine_similarity(query_vec, self.entry_vectors)

        top_indices = np.argsort(scores)[::-1][:k]

        filtered_indices = [i for i in top_indices if scores[i] >= threshold]

        print(f"[IntentRetriever] {len(filtered_indices)}/{len(top_indices)} candidates "
              f"cleared similarity threshold ({threshold})")

        return [self.registry[i] for i in filtered_indices]

    def get_top_candidates_with_scores(self, question: str, k: int = 10) -> list:
        """
        Same as get_top_candidates but also returns similarity scores -
        useful for debugging/tuning.
        """
        query_vec = self._embed_text(question)
        scores = self._cosine_similarity(query_vec, self.entry_vectors)

        top_indices = np.argsort(scores)[::-1][:k]

        return [
            (self.registry[i], float(scores[i]))
            for i in top_indices
        ]
