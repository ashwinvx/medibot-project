"""
Module 1 — Document Ingestion
Parses all PDFs and Markdown files with Docling's structural-aware converter,
chunks them with HybridChunker (hierarchical → token-size cap), generates
dense (bge-small) + sparse (BM25) vectors, and upserts to Qdrant with the
full RBAC metadata schema required by the assignment.
"""

import sys
import uuid
import logging
from pathlib import Path
from typing import List

# Make config importable whether the script is run from project root or ingest/
sys.path.insert(0, str(Path(__file__).parent.parent))

from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from docling_core.types.doc import DocItemLabel
from sentence_transformers import SentenceTransformer
from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient
from qdrant_client import models as qmodels

from ingest.config import (
    DATA_DIR,
    QDRANT_URL,
    QDRANT_COLLECTION,
    DENSE_MODEL_NAME,
    DENSE_DIM,
    SPARSE_MODEL_NAME,
    CHUNK_MAX_TOKENS,
    COLLECTION_CONFIG,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

UPSERT_BATCH = 32


# ---------------------------------------------------------------------------
# Qdrant setup
# ---------------------------------------------------------------------------

def setup_qdrant(client: QdrantClient) -> None:
    """Drop and recreate the collection with dense + sparse vector configs."""
    if client.collection_exists(QDRANT_COLLECTION):
        log.info("Dropping existing collection '%s'", QDRANT_COLLECTION)
        client.delete_collection(QDRANT_COLLECTION)

    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config={
            "dense": qmodels.VectorParams(
                size=DENSE_DIM,
                distance=qmodels.Distance.COSINE,
            )
        },
        sparse_vectors_config={
            "sparse": qmodels.SparseVectorParams(
                index=qmodels.SparseIndexParams(on_disk=False)
            )
        },
    )
    log.info("Created Qdrant collection '%s' (dense=%d-dim + BM25 sparse)", QDRANT_COLLECTION, DENSE_DIM)


# ---------------------------------------------------------------------------
# Chunk helpers
# ---------------------------------------------------------------------------

def get_chunk_type(chunk) -> str:
    labels = {item.label for item in chunk.meta.doc_items}
    if DocItemLabel.TABLE in labels:
        return "table"
    if DocItemLabel.CODE in labels:
        return "code"
    if DocItemLabel.SECTION_HEADER in labels:
        return "heading"
    return "text"


# ---------------------------------------------------------------------------
# Per-collection ingestion
# ---------------------------------------------------------------------------

def ingest_collection(
    collection_name: str,
    file_paths: List[Path],
    access_roles: List[str],
    converter: DocumentConverter,
    chunker: HybridChunker,
    dense_model: SentenceTransformer,
    sparse_model: SparseTextEmbedding,
    qdrant: QdrantClient,
) -> int:
    total = 0

    for file_path in file_paths:
        if not file_path.exists():
            log.warning("File not found, skipping: %s", file_path)
            continue

        log.info("[%s] Parsing: %s", collection_name, file_path.name)
        try:
            result = converter.convert(source=str(file_path))
            doc = result.document
        except Exception as exc:
            log.error("Failed to parse %s: %s", file_path.name, exc)
            continue

        chunks = list(chunker.chunk(dl_doc=doc))
        log.info("  → %d chunks produced", len(chunks))

        for batch_start in range(0, len(chunks), UPSERT_BATCH):
            batch = chunks[batch_start : batch_start + UPSERT_BATCH]

            # contextualize() prepends the heading hierarchy to each chunk's text
            # so the embedding carries section context, not just the bare passage.
            texts_for_embedding = [chunker.contextualize(chunk=c) for c in batch]

            dense_vecs = dense_model.encode(
                texts_for_embedding,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            sparse_vecs = list(sparse_model.embed(texts_for_embedding))

            points = []
            for chunk, text, d_vec, s_vec in zip(
                batch, texts_for_embedding, dense_vecs, sparse_vecs
            ):
                section_title = chunk.meta.headings[-1] if chunk.meta.headings else ""

                points.append(
                    qmodels.PointStruct(
                        id=str(uuid.uuid4()),
                        vector={
                            "dense": d_vec.tolist(),
                            "sparse": qmodels.SparseVector(
                                indices=s_vec.indices.tolist(),
                                values=s_vec.values.tolist(),
                            ),
                        },
                        payload={
                            "text": chunk.text,
                            "source_document": file_path.name,
                            "collection": collection_name,
                            "access_roles": access_roles,
                            "section_title": section_title,
                            "chunk_type": get_chunk_type(chunk),
                        },
                    )
                )

            qdrant.upsert(collection_name=QDRANT_COLLECTION, points=points)
            total += len(points)

    return total


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("Loading models...")
    dense_model = SentenceTransformer(DENSE_MODEL_NAME)
    sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)

    log.info("Connecting to Qdrant at %s", QDRANT_URL)
    qdrant = QdrantClient(url=QDRANT_URL)
    setup_qdrant(qdrant)

    converter = DocumentConverter()
    chunker = HybridChunker(tokenizer=DENSE_MODEL_NAME, max_tokens=CHUNK_MAX_TOKENS)

    grand_total = 0
    for collection_name, cfg in COLLECTION_CONFIG.items():
        log.info("=== Collection: %s ===", collection_name)
        file_paths = [DATA_DIR / f for f in cfg["files"]]
        count = ingest_collection(
            collection_name=collection_name,
            file_paths=file_paths,
            access_roles=cfg["access_roles"],
            converter=converter,
            chunker=chunker,
            dense_model=dense_model,
            sparse_model=sparse_model,
            qdrant=qdrant,
        )
        log.info("  → %d chunks upserted for '%s'", count, collection_name)
        grand_total += count

    log.info("Done. Total chunks in Qdrant: %d", grand_total)

    # Quick sanity check
    info = qdrant.get_collection(QDRANT_COLLECTION)
    log.info("Collection point count: %d", info.points_count)


if __name__ == "__main__":
    main()
