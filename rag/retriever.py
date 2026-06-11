"""
Module 2 — Hybrid Retriever with RBAC enforcement

Single Qdrant query that:
  1. Prefetches candidates via dense (bge-small cosine) search
  2. Prefetches candidates via sparse BM25 search
  3. Fuses both ranked lists with Reciprocal Rank Fusion (RRF) inside Qdrant
  4. Applies an access_roles metadata filter *at the Qdrant query level*
     so restricted chunks are never returned regardless of prompt content.

The RBAC filter is applied server-side before results leave Qdrant — it is
not post-fetch Python filtering. An adversarial prompt cannot bypass it.
"""

import sys
import logging
from pathlib import Path
from typing import List

# Ensure project root is in path so ingest/rag are importable as packages
sys.path.insert(0, str(Path(__file__).parent.parent))

from sentence_transformers import SentenceTransformer
from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient
from qdrant_client import models as qmodels

from ingest.config import (
    QDRANT_URL,
    QDRANT_COLLECTION,
    DENSE_MODEL_NAME,
    SPARSE_MODEL_NAME,
)

log = logging.getLogger(__name__)

# Broader candidate set per vector type before RRF fusion.
# The reranker (Module 3) expects top-10 from this retriever.
PREFETCH_K = 20
RETRIEVE_K = 10


class HybridRetriever:
    """
    Loads embedding models once at construction and exposes a single
    retrieve() method used by the FastAPI /chat endpoint.
    """

    def __init__(self) -> None:
        log.info("Loading dense model: %s", DENSE_MODEL_NAME)
        self.dense_model = SentenceTransformer(DENSE_MODEL_NAME)

        log.info("Loading sparse model: %s", SPARSE_MODEL_NAME)
        self.sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)

        self.qdrant = QdrantClient(url=QDRANT_URL, check_compatibility=False)
        log.info("HybridRetriever ready (collection: %s)", QDRANT_COLLECTION)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        role: str,
        top_k: int = RETRIEVE_K,
    ) -> List[dict]:
        """
        Returns up to `top_k` chunks accessible to `role`, ranked by
        RRF-fused dense + BM25 relevance.

        Parameters
        ----------
        query   Natural language question from the user.
        role    Authenticated role (e.g. 'nurse', 'doctor').  The RBAC
                filter is derived from this — not from the query text.
        top_k   Number of candidates to return (fed to the reranker).
        """
        dense_vec, sparse_vec = self._encode(query)
        rbac_filter = self._build_rbac_filter(role)

        # Single Qdrant call: two prefetch branches → RRF fusion → RBAC filter
        response = self.qdrant.query_points(
            collection_name=QDRANT_COLLECTION,
            prefetch=[
                # Branch 1: semantic (dense) retrieval
                qmodels.Prefetch(
                    query=dense_vec,
                    using="dense",
                    limit=PREFETCH_K,
                ),
                # Branch 2: keyword (BM25 sparse) retrieval
                qmodels.Prefetch(
                    query=qmodels.SparseVector(
                        indices=sparse_vec.indices.tolist(),
                        values=sparse_vec.values.tolist(),
                    ),
                    using="sparse",
                    limit=PREFETCH_K,
                ),
            ],
            # RRF fuses and re-ranks the two candidate lists inside Qdrant
            query=qmodels.FusionQuery(fusion=qmodels.Fusion.RRF),
            limit=top_k,
            # RBAC filter applied at retrieval time — not post-fetch
            query_filter=rbac_filter,
            with_payload=True,
        )

        chunks = [self._to_dict(pt) for pt in response.points]
        log.debug(
            "Retrieved %d/%d chunks for role='%s' query='%.60s...'",
            len(chunks), top_k, role, query,
        )
        return chunks

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _encode(self, query: str):
        dense = self.dense_model.encode(query, normalize_embeddings=True).tolist()
        sparse = list(self.sparse_model.embed([query]))[0]
        return dense, sparse

    @staticmethod
    def _build_rbac_filter(role: str) -> qmodels.Filter:
        """
        Builds a Qdrant filter that matches only chunks whose
        access_roles list contains the given role.
        Qdrant's MatchValue on an array field performs a 'contains' check.
        """
        return qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="access_roles",
                    match=qmodels.MatchValue(value=role),
                )
            ]
        )

    @staticmethod
    def _to_dict(point) -> dict:
        p = point.payload
        return {
            "text": p.get("text", ""),
            "source_document": p.get("source_document", ""),
            "collection": p.get("collection", ""),
            "section_title": p.get("section_title", ""),
            "chunk_type": p.get("chunk_type", "text"),
            "score": point.score,
        }
