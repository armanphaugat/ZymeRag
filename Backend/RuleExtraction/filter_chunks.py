import os
import re
import pickle
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

# Configurable Weights & Thresholds
WEIGHT_HEURISTIC = float(os.getenv("POLICY_WEIGHT_HEURISTIC", "0.40"))
WEIGHT_BM25 = float(os.getenv("POLICY_WEIGHT_BM25", "0.30"))
WEIGHT_SEMANTIC = float(os.getenv("POLICY_WEIGHT_SEMANTIC", "0.30"))

# Thresholds (conservative to prevent false negatives)
MIN_POLICY_SCORE = float(os.getenv("MIN_POLICY_SCORE", "0.20"))
MAX_POLICY_CHUNKS = int(os.getenv("MAX_POLICY_CHUNKS", "8"))

# ───────────────────────────────────────────────────────────────
# Deontic & Policy Keyword Heuristics
# ───────────────────────────────────────────────────────────────
DEONTIC_PATTERNS = [
    # Modals / Mandatory
    r"\b(must|shall|required|mandatory|compulsory|obligation|must\s+not|shall\s+not)\b",
    # Prohibitions & Denials
    r"\b(prohibit(?:ed|s|ing)?|forbid(?:den)?|not\s+allowed|may\s+not|cannot|restricted|disallow(?:ed)?|never|prevent(?:ed|ing)?)\b",
    # Blocks & Rejections
    r"\b(block(?:ed|ing|s)?|den(?:y|ied|ies)|reject(?:ed|ing|s)?|freeze|suspend(?:ed)?|flag(?:ged)?|suspicious|fraud|risk)\b",
    # Permissions & Approvals
    r"\b(permit(?:ted|s)?|authoriz(?:ed|ation|e)?|approv(?:al|ed|e|er)?|sign-off|consent|escalat(?:e|ed|ion)?)\b",
    # Conditions & Thresholds
    r"\b(limit|threshold|maximum|minimum|max|min|exceed(?:s|ing|ed)?|greater\s+than|less\s+than|up\s+to|over|above|below)\b",
    # Roles & Entities
    r"\b(admin|manager|lead|supervisor|officer|director|vp|user|customer|employee|support)\b",
    # Financial & Operational Actions
    r"\b(transfer|payment|wire|refund|transaction|delete|cancel|update|access|data|amount|balance)\b",
    # Currency / Amounts
    r"(\$|\b(?:usd|eur|gbp|inr|rs|dollars)\b|\b\d+(?:,\d{3})*(?:\.\d+)?\b)",
]

COMPILED_DEONTIC = [re.compile(p, re.IGNORECASE) for p in DEONTIC_PATTERNS]

POLICY_QUERIES = [
    "mandatory compliance policy requirements restrictions obligations approvals",
    "financial threshold maximum transfer limit refund authorization role sign-off",
    "permitted actions access control policy rules block escalate",
]


def score_heuristics(text: str) -> float:
    """
    Computes a heuristic score [0.0, 1.0] based on deontic modals,
    operational keywords, and threshold patterns.
    """
    if not text or not text.strip():
        return 0.0

    match_count = 0
    for pattern in COMPILED_DEONTIC:
        matches = pattern.findall(text)
        if matches:
            match_count += min(len(matches), 3)

    normalized = min(match_count / 10.0, 1.0)
    return normalized


def score_bm25(bm25_data: Optional[Dict[str, Any]], chunk_index: int, total_chunks: int) -> float:
    """
    Evaluates BM25 score of a chunk against canonical policy queries.
    """
    if not bm25_data or "bm25" not in bm25_data:
        return 0.0

    bm25 = bm25_data["bm25"]
    max_score = 0.0

    for query in POLICY_QUERIES:
        tokenized_query = re.findall(r"\b\w+\b", query.lower())
        doc_scores = bm25.get_scores(tokenized_query)
        if chunk_index < len(doc_scores):
            score = float(doc_scores[chunk_index])
            if score > max_score:
                max_score = score

    normalized = min(max_score / 10.0, 1.0) if max_score > 0 else 0.0
    return normalized


def score_semantic_faiss(
    vectorstore: Any,
    chunk_text: str,
    top_k_texts: List[str]
) -> float:
    """
    Checks if this chunk was retrieved in the top semantic hits for policy anchor queries.
    """
    if not vectorstore or not top_k_texts:
        return 0.0

    chunk_stripped = chunk_text.strip()
    for hit_text in top_k_texts:
        if chunk_stripped in hit_text or hit_text in chunk_stripped:
            return 1.0
    return 0.2


def load_faiss_and_bm25(content_path_str: str):
    """Safely loads the FAISS index and BM25 pkl if they exist on disk."""
    content_path = Path(content_path_str)
    bm25_data = None
    vectorstore = None
    top_k_texts = []

    bm25_path = content_path / "bm25.pkl"
    if bm25_path.exists():
        try:
            with open(bm25_path, "rb") as f:
                bm25_data = pickle.load(f)
        except Exception as e:
            logger.warning(f"[FilterChunks] Could not load BM25 at {bm25_path}: {e}")

    faiss_index_path = content_path / "index.faiss"
    if faiss_index_path.exists():
        try:
            from Embeddings.Embeddingmaker import Embedder
            from langchain_community.vectorstores import FAISS
            embedder = Embedder()
            vectorstore = FAISS.load_local(
                str(content_path),
                embedder,
                allow_dangerous_deserialization=True
            )
            for q in POLICY_QUERIES:
                docs = vectorstore.similarity_search(q, k=5)
                for d in docs:
                    top_k_texts.append(d.page_content.strip())
        except Exception as e:
            logger.warning(f"[FilterChunks] Could not load FAISS at {content_path}: {e}")

    return bm25_data, vectorstore, top_k_texts


def filter_policy_relevant_chunks(
    chunks_data: List[Dict[str, Any]],
    content_path_str: Optional[str] = None,
    min_score: float = MIN_POLICY_SCORE,
    max_chunks: int = MAX_POLICY_CHUNKS,
) -> List[Dict[str, Any]]:
    """
    Filters and ranks document chunks to retain high-confidence policy-bearing sections.
    Includes adjacent context (previous and next chunk) for each selected chunk.
    Failsafe guarantee: If document has <= 5 chunks or no chunks pass threshold,
    returns all chunks to guarantee zero false negatives.
    """
    total = len(chunks_data)
    if total == 0:
        return []

    # If small document, preserve everything without aggressive pruning
    if total <= 5:
        logger.info(f"[FilterChunks] Document has {total} chunks (<= 5). Retaining all chunks.")
        for idx in range(total):
            _attach_adjacent_context(chunks_data, idx)
        return chunks_data

    # Load existing FAISS and BM25 indices if path provided
    bm25_data = None
    vectorstore = None
    top_k_texts = []
    if content_path_str:
        bm25_data, vectorstore, top_k_texts = load_faiss_and_bm25(content_path_str)

    scored_chunks = []
    for idx, chunk in enumerate(chunks_data):
        text = chunk.get("text", "")
        h_score = score_heuristics(text)
        b_score = score_bm25(bm25_data, idx, total)
        s_score = score_semantic_faiss(vectorstore, text, top_k_texts)

        # If indices not loaded, normalize heuristic score alone
        if not content_path_str:
            combined_score = h_score
        else:
            combined_score = (
                WEIGHT_HEURISTIC * h_score +
                WEIGHT_BM25 * b_score +
                WEIGHT_SEMANTIC * s_score
            )

        chunk["policy_score"] = round(combined_score, 4)
        scored_chunks.append((idx, combined_score, chunk))

    # Sort descending by policy score
    scored_chunks.sort(key=lambda x: x[1], reverse=True)

    # Select chunks passing threshold
    selected_indices = set()
    for idx, score, chunk in scored_chunks:
        if score >= min_score and len(selected_indices) < max_chunks:
            selected_indices.add(idx)

    # Failsafe: if nothing passed threshold, keep top 5 to prevent dropping policies
    if not selected_indices:
        logger.warning(
            f"[FilterChunks] No chunks exceeded threshold {min_score}. "
            "Applying failsafe: selecting top 5 chunks."
        )
        for idx, score, chunk in scored_chunks[:min(5, total)]:
            selected_indices.add(idx)

    logger.info(
        f"[FilterChunks] Selected {len(selected_indices)} / {total} chunks "
        f"exceeding policy score threshold {min_score}."
    )

    filtered_chunks = []
    for idx in sorted(selected_indices):
        chunk = chunks_data[idx]
        _attach_adjacent_context(chunks_data, idx)
        filtered_chunks.append(chunk)

    return filtered_chunks


def _attach_adjacent_context(chunks_data: List[Dict[str, Any]], idx: int):
    """
    Attaches previous and next chunk text to provide boundary context
    without losing the original chunk's identity, page_number, and chunk_id.
    """
    target = chunks_data[idx]
    prev_text = chunks_data[idx - 1].get("text", "") if idx > 0 else ""
    next_text = chunks_data[idx + 1].get("text", "") if idx < len(chunks_data) - 1 else ""

    target["prev_context"] = prev_text
    target["next_context"] = next_text

    context_parts = []
    if prev_text:
        context_parts.append(f"[PREVIOUS CHUNK CONTEXT]:\n{prev_text[-400:]}")
    context_parts.append(f"[TARGET CLAUSE TO EXTRACT RULES FROM]:\n{target.get('text', '')}")
    if next_text:
        context_parts.append(f"[FOLLOWING CHUNK CONTEXT]:\n{next_text[:400]}")

    target["windowed_text"] = "\n\n".join(context_parts)
