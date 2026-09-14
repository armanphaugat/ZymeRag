import asyncio
import json
import os
import re
import random
import logging
from typing import Optional, List, Dict, Any, Literal, Tuple
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
from groq import AsyncGroq, RateLimitError, APIStatusError

from Dbhelper.rules_db_helper import save_rule
from Backend.RuleExtraction.filter_chunks import filter_policy_relevant_chunks
from Backend.RuleExtraction.deduplicate_rules import deduplicate_extracted_rules

load_dotenv()
logger = logging.getLogger(__name__)

# Primary and Fallback Models
GROQ_MODEL = os.getenv("GROQ_EXTRACTION_MODEL", "groq/compound-mini")
FALLBACK_MODELS = [
    "groq/compound-mini",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "groq/compound",
]

# Configurable concurrency and timeouts
MAX_CONCURRENT_EXTRACTIONS = int(os.getenv("RULE_EXTRACTION_CONCURRENCY", "2"))
MAX_BACKOFF_SECONDS = float(os.getenv("GROQ_MAX_BACKOFF", "15.0"))
GROQ_CALL_TIMEOUT = float(os.getenv("GROQ_CALL_TIMEOUT", "20.0"))
CHUNK_EXTRACTION_TIMEOUT = float(os.getenv("CHUNK_EXTRACTION_TIMEOUT", "30.0"))


class RuleScope(BaseModel):
    tool: Optional[str] = Field(None, description="Target tool name, e.g. 'crm', 'payment', 'email', 'order'")
    operation: Optional[str] = Field(None, description="Target operation, e.g. 'transfer_funds', 'delete_customer', 'issue_refund'")
    flow_id: Optional[str] = Field(None, description="Flow classification ID, e.g. 'payment_transfer'")


class RuleCondition(BaseModel):
    field: Optional[str] = Field(None, description="Path to argument being evaluated, e.g. 'amount', 'recipient.domain'")
    operator: Optional[Literal["==", "!=", ">", ">=", "<", "<=", "in", "not_in", "contains"]] = Field(
        "==", description="Evaluation operator"
    )
    value: Optional[Any] = Field(None, description="Threshold value or operand")


class ExtractedRule(BaseModel):
    scope: RuleScope
    condition: RuleCondition
    effect: Literal["ALLOW", "BLOCK", "ESCALATE"]
    required_approval_role: Optional[str] = None
    source_clause: Optional[str] = None


class ExtractionResult(BaseModel):
    has_enforceable_rules: bool
    rules: List[ExtractedRule] = Field(default_factory=list)


EXTRACTION_SYSTEM_PROMPT = """You are a strict Policy Rule Extraction Engine for an enterprise AI Action Gateway.
Your task is to analyze a policy clause and extract ALL deterministic, enforceable rules it contains.

CRITICAL: A single clause often encodes multiple tiers or thresholds.
Example: "Under Rs 2,000 auto-approved; Rs 2,000-15,000 require support-lead review; above Rs 15,000 require fraud-team sign-off"
-> This MUST produce 3 separate rule objects, one per tier. Never merge or drop tiers.

For EACH enforceable rule found:
  - Identify the target tool (e.g., 'payment', 'crm', 'email', 'refund', 'order').
  - Identify the operation (e.g., 'transfer_funds', 'issue_refund', 'cancel_order', 'delete_customer').
  - Identify the condition: argument field (e.g. 'amount', 'recipient.domain'), operator, and comparison value.
  - Set the effect: 'ALLOW' (auto-permitted), 'BLOCK' (forbidden), or 'ESCALATE' (requires human approval).
  - If effect is 'ESCALATE', set required_approval_role (e.g., 'finance_manager', 'compliance_officer', 'lead').
  - Quote the exact source_clause verbatim from the text.

Output STRICT JSON - no markdown fences, no commentary:
{
  "has_enforceable_rules": boolean,
  "rules": [
    {
      "scope": {"tool": "string", "operation": "string", "flow_id": "string or null"},
      "condition": {"field": "string", "operator": "== | != | > | >= | < | <= | in | not_in | contains", "value": any},
      "effect": "ALLOW | BLOCK | ESCALATE",
      "required_approval_role": "string or null",
      "source_clause": "string"
    }
  ]
}
If no enforceable rule exists: {"has_enforceable_rules": false, "rules": []}"""


_api_keys: List[str] = []
_api_key_index: int = 0
_clients: Dict[str, AsyncGroq] = {}


def _init_api_keys():
    global _api_keys
    raw_keys = os.getenv("GROQ_API_KEYS", "") or os.getenv("GROQ_API_KEY", "")
    _api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]


def _get_next_client() -> Optional[Tuple[AsyncGroq, str]]:
    """Returns the next AsyncGroq client using round-robin API key rotation."""
    global _api_key_index
    if not _api_keys:
        _init_api_keys()
    if not _api_keys:
        return None

    key = _api_keys[_api_key_index % len(_api_keys)]
    if key not in _clients:
        _clients[key] = AsyncGroq(api_key=key)

    masked_key = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "***"
    return _clients[key], masked_key


def _rotate_api_key():
    """Advances key index on rate limit."""
    global _api_key_index
    if _api_keys and len(_api_keys) > 1:
        _api_key_index = (_api_key_index + 1) % len(_api_keys)
        logger.info(f"[RuleExtraction] Rotated to next Groq API key index {_api_key_index}.")


async def _call_groq_api(
    prompt: str,
    system_prompt: str,
    chunk_id: str
) -> Optional[str]:
    """
    Executes Groq completion with strict asyncio timeouts and guarded 429 backoff.
    Avoids multi-model storms on a single rate-limited key.
    """
    client_tuple = _get_next_client()
    if client_tuple is None:
        logger.error("[RuleExtraction] GROQ_API_KEY not configured. Cannot perform LLM extraction.")
        return None

    client, masked_key = client_tuple
    has_multiple_keys = len(_api_keys) > 1

    # If only 1 key, try primary model then at most 1 fallback
    models_to_try = [GROQ_MODEL] if not has_multiple_keys else [GROQ_MODEL] + [m for m in FALLBACK_MODELS if m != GROQ_MODEL]

    for model in models_to_try:
        max_rate_limit_attempts = 2
        for attempt in range(max_rate_limit_attempts):
            try:
                cur_client, masked_k = _get_next_client() or (client, masked_key)
                response = await asyncio.wait_for(
                    cur_client.chat.completions.create(
                        model=model,
                        temperature=0,
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=750,
                        timeout=int(GROQ_CALL_TIMEOUT),
                    ),
                    timeout=GROQ_CALL_TIMEOUT + 4.0,
                )
                return response.choices[0].message.content

            except asyncio.TimeoutError:
                logger.error(f"[RuleExtraction] Timeout ({GROQ_CALL_TIMEOUT}s) on model '{model}' for chunk {chunk_id}.")
                break

            except RateLimitError as rle:
                jitter = random.uniform(0.5, 1.5)
                backoff = min(MAX_BACKOFF_SECONDS, (2.0 ** attempt * 1.5) + jitter)
                logger.warning(
                    f"[RuleExtraction] Groq 429 on model '{model}' ({masked_k}) on chunk {chunk_id}. "
                    f"Backing off for {backoff:.2f}s (attempt {attempt + 1}/{max_rate_limit_attempts})."
                )
                if has_multiple_keys:
                    _rotate_api_key()
                await asyncio.sleep(backoff)
                if not has_multiple_keys and attempt >= 1:
                    # Single key exhausted quota, break to avoid hammering
                    return None
                continue

            except APIStatusError as e:
                if e.status_code == 400:
                    error_body = getattr(e, "body", str(e))
                    logger.error(
                        f"[RuleExtraction] Groq HTTP 400 on model '{model}' for chunk {chunk_id}: {error_body}. Switching model."
                    )
                    break
                elif e.status_code == 404:
                    break
                else:
                    logger.error(f"[RuleExtraction] Groq HTTP {e.status_code} on model '{model}' for chunk {chunk_id}: {e}")
                    break

            except Exception as e:
                logger.error(f"[RuleExtraction] Unexpected error on model '{model}' for chunk {chunk_id}: {e}")
                break

    return None


def parse_and_validate_rules(raw_json_str: str, chunk_id: str) -> List[ExtractedRule]:
    """Validates raw LLM JSON output against strict Pydantic models."""
    try:
        clean_str = raw_json_str.strip()
        if clean_str.startswith("```"):
            clean_str = re.sub(r"^```(?:json)?\n?", "", clean_str)
            clean_str = re.sub(r"\n?```$", "", clean_str)
        data = json.loads(clean_str)
        result = ExtractionResult.model_validate(data)
        return result.rules if result.has_enforceable_rules else []
    except (json.JSONDecodeError, ValidationError) as e:
        logger.error(f"[RuleExtraction] Schema validation failed for chunk {chunk_id}: {e}")
        return []


async def extract_rules_from_chunk(
    chunk_data: Dict[str, Any],
    doc_id: str,
    max_retries: int = 1
) -> List[Dict[str, Any]]:
    """
    Extracts policy rules from a single chunk utilizing windowed boundary context.
    Returns list of metadata dictionaries: {rule, chunk_id, doc_id, page_number, source_clause}.
    """
    chunk_id = chunk_data.get("chunk_id", "")
    chunk_text = chunk_data.get("text", "")
    page_number = chunk_data.get("page_number", 1)
    windowed_text = chunk_data.get("windowed_text") or chunk_text

    user_prompt = (
        f"Policy Context Window:\n\"\"\"{windowed_text}\"\"\"\n\n"
        f"TARGET CLAUSE TO EXTRACT RULES FROM:\n\"\"\"{chunk_text}\"\"\"\n\n"
        "Extract ALL deterministic, enforceable rules contained in the target clause. "
        "Use the preceding/following context window to resolve antecedents or multi-clause conditions. "
        "If the clause contains multiple thresholds or tiers, extract each as a separate rule."
    )

    for attempt in range(max_retries + 1):
        raw_output = await _call_groq_api(user_prompt, EXTRACTION_SYSTEM_PROMPT, chunk_id)
        if not raw_output:
            if attempt < max_retries:
                await asyncio.sleep(1.0)
            continue

        extracted = parse_and_validate_rules(raw_output, chunk_id)
        if not extracted:
            return []

        results = []
        for r in extracted:
            results.append({
                "rule": r,
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "page_number": page_number,
                "source_clause": r.source_clause or chunk_text[:500],
            })
        return results

    logger.warning(f"[RuleExtraction] No rules extracted from chunk {chunk_id}.")
    return []


async def extract_rules_from_document(
    doc_id: str,
    chunks_data: List[Dict[str, Any]],
    content_path_str: Optional[str] = None
) -> List[str]:
    """
    Orchestrates full offline document rule extraction using an explicit worker queue:
    1. Pre-filters chunks using hybrid keyword + BM25 + FAISS scoring.
    2. Attaches adjacent boundary context.
    3. Concurrently calls Groq LLM with a worker pool (no indefinite acquire hangs).
    4. Normalizes and deduplicates rules across the document.
    5. Stores all valid rules into database with status = 'DRAFT'.
    """
    total_chunks = len(chunks_data)
    logger.info(
        f"[RuleExtraction] Starting offline rule extraction for doc {doc_id} "
        f"({total_chunks} total chunks, concurrency limit {MAX_CONCURRENT_EXTRACTIONS})..."
    )

    # Step 1: Pre-filter policy-relevant chunks
    filtered_chunks = filter_policy_relevant_chunks(
        chunks_data=chunks_data,
        content_path_str=content_path_str
    )
    logger.info(
        f"[RuleExtraction] Filtered {total_chunks} chunks down to {len(filtered_chunks)} policy-dense chunks."
    )

    # Step 2: Worker queue extraction (guarantees no indefinite semaphore hangs)
    queue = asyncio.Queue()
    for item in filtered_chunks:
        queue.put_nowait(item)

    extracted_items_with_meta: List[Dict[str, Any]] = []
    lock = asyncio.Lock()

    async def worker(worker_id: int):
        while not queue.empty():
            try:
                chunk = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            chunk_id = chunk.get("chunk_id", "unknown")
            logger.info(f"[RuleExtraction-W{worker_id}] Processing chunk {chunk_id}...")

            try:
                chunk_results = await asyncio.wait_for(
                    extract_rules_from_chunk(chunk, doc_id),
                    timeout=CHUNK_EXTRACTION_TIMEOUT
                )
                if chunk_results:
                    async with lock:
                        extracted_items_with_meta.extend(chunk_results)
            except asyncio.TimeoutError:
                logger.error(f"[RuleExtraction-W{worker_id}] Chunk {chunk_id} timed out ({CHUNK_EXTRACTION_TIMEOUT}s). Skipping.")
            except Exception as e:
                logger.error(f"[RuleExtraction-W{worker_id}] Error on chunk {chunk_id}: {e}")
            finally:
                queue.task_done()

    num_workers = min(MAX_CONCURRENT_EXTRACTIONS, len(filtered_chunks)) or 1
    worker_tasks = [asyncio.create_task(worker(i)) for i in range(num_workers)]
    await asyncio.gather(*worker_tasks, return_exceptions=True)

    # Step 3: Deduplication across document
    deduplicated = deduplicate_extracted_rules(extracted_items_with_meta)
    logger.info(
        f"[RuleExtraction] Extracted {len(extracted_items_with_meta)} raw rules; "
        f"deduplicated down to {len(deduplicated)} unique rules."
    )

    # Step 4: Persist to DB as DRAFT with per-rule timeout
    created_rule_ids: List[str] = []
    for item in deduplicated:
        r = item["rule"]
        scope_data = r.scope.model_dump() if hasattr(r.scope, "model_dump") else r.scope
        cond_data = r.condition.model_dump() if hasattr(r.condition, "model_dump") else r.condition

        try:
            rule_id = await asyncio.wait_for(
                save_rule(
                    scope=scope_data,
                    condition=cond_data,
                    effect=r.effect,
                    required_approval_role=r.required_approval_role,
                    source_document=item["doc_id"],
                    source_chunk=item["primary_chunk_id"],
                    source_clause=item["source_clause"],
                    status="DRAFT",
                ),
                timeout=10.0
            )
            if rule_id:
                created_rule_ids.append(rule_id)
                logger.info(
                    f"[RuleExtraction] Saved DRAFT rule {rule_id} "
                    f"({r.effect}) for chunk {item['primary_chunk_id']}"
                )
        except asyncio.TimeoutError:
            logger.error(f"[RuleExtraction] Timeout saving rule to DB for chunk {item['primary_chunk_id']}.")

    print(
        f"[RuleExtraction] Completed extraction for doc {doc_id}. "
        f"Total DRAFT rules created: {len(created_rule_ids)}"
    )
    return created_rule_ids
