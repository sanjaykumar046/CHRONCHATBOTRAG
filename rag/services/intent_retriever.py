import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class IntentRetriever:
    """Rank registry entries locally without making an embedding-model call."""

    _SEARCH_FIELDS = (
        "Intent Name",
        "Description",
        "User Questions",
        "Example questions",
    )

    def __init__(self, registry: list, cache_path: str = None):
        # `cache_path` stays accepted for compatibility with existing callers;
        # local TF-IDF vectors are built in memory and do not use an AI cache.
        self.registry = registry
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        self.entry_vectors = None

        if registry:
            texts = [self._entry_to_text(entry) for entry in registry]
            self.entry_vectors = self.vectorizer.fit_transform(texts)

    @classmethod
    def _entry_to_text(cls, entry: dict) -> str:
        parts = []
        for field in cls._SEARCH_FIELDS:
            value = entry.get(field, "")
            if isinstance(value, (list, tuple)):
                value = " ".join(str(item) for item in value)
            parts.append(str(value or ""))
        return " ".join(parts)

    def get_top_candidates(self, question: str, k: int = 10, min_score: float = None) -> list:
        """Return the highest lexical TF-IDF matches from registry content."""
        if not self.registry or self.entry_vectors is None or not question.strip():
            return []

        query_vector = self.vectorizer.transform([question])
        scores = cosine_similarity(query_vector, self.entry_vectors).ravel()
        top_indices = np.argsort(scores)[::-1][:max(0, k)]

        # Return no zero-overlap candidates. `min_score` remains available to
        # callers, while the default avoids an embedding-specific threshold.
        threshold = min_score if min_score is not None else 0.0
        return [
            self.registry[index]
            for index in top_indices
            if scores[index] > threshold
        ]

    def get_top_candidates_with_scores(self, question: str, k: int = 10) -> list:
        if not self.registry or self.entry_vectors is None or not question.strip():
            return []

        query_vector = self.vectorizer.transform([question])
        scores = cosine_similarity(query_vector, self.entry_vectors).ravel()
        top_indices = np.argsort(scores)[::-1][:max(0, k)]
        return [
            (self.registry[index], float(scores[index]))
            for index in top_indices
        ]
