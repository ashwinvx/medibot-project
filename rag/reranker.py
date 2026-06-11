"""
Module 3 — Cross-Encoder Reranker

Takes the top-10 candidate chunks from the hybrid retriever and re-scores
every (query, chunk) pair *jointly* through a cross-encoder — both texts
pass through the full attention stack together, unlike bi-encoders which
score them independently.

This catches cases where hybrid retrieval ranks a chunk highly because of
surface-level term overlap but the cross-encoder recognises it is not
actually answering the question.

Pipeline position:
  HybridRetriever (top-10)  →  Reranker (top-3)  →  LLM
"""

import logging
from typing import List

from sentence_transformers import CrossEncoder

log = logging.getLogger(__name__)

CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
DEFAULT_TOP_K = 3


class Reranker:
    """
    Loads the cross-encoder once at construction.
    Call rerank() for every query.
    """

    def __init__(self, model_name: str = CROSS_ENCODER_MODEL) -> None:
        log.info("Loading cross-encoder: %s", model_name)
        self.model = CrossEncoder(model_name)
        log.info("Reranker ready")

    def rerank(
        self,
        query: str,
        chunks: List[dict],
        top_k: int = DEFAULT_TOP_K,
    ) -> List[dict]:
        """
        Score each (query, chunk) pair jointly and return the top_k
        highest-scoring chunks with a 'rerank_score' field added.

        Parameters
        ----------
        query   The user's question.
        chunks  Candidate chunks from HybridRetriever (typically top-10).
        top_k   How many to keep for the LLM prompt (typically 3).
        """
        if not chunks:
            return []

        pairs = [(query, c["text"]) for c in chunks]
        scores = self.model.predict(pairs)

        # Attach score and sort descending
        scored = sorted(
            [
                {**chunk, "rerank_score": float(score)}
                for chunk, score in zip(chunks, scores)
            ],
            key=lambda x: x["rerank_score"],
            reverse=True,
        )

        self._log_ranking(query, chunks, scored, top_k)
        return scored[:top_k]

    # ------------------------------------------------------------------

    def _log_ranking(
        self,
        query: str,
        original: List[dict],
        scored: List[dict],
        top_k: int,
    ) -> None:
        """Log before/after ranking so reranker impact is visible."""
        original_order = {c["text"]: i for i, c in enumerate(original)}

        log.info("Reranker results for: '%.70s'", query)
        log.info("  %-4s %-6s %-6s  %s", "rank", "re_sc", "hy_pos", "source | section")
        for new_rank, chunk in enumerate(scored):
            old_pos = original_order.get(chunk["text"], -1)
            kept = "✓" if new_rank < top_k else " "
            log.info(
                "  %s%-2d  %+6.2f  [%-2d→%-2d]  %s | %s",
                kept,
                new_rank + 1,
                chunk["rerank_score"],
                old_pos + 1,
                new_rank + 1,
                chunk["source_document"],
                chunk["section_title"][:45],
            )
