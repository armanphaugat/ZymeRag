import asyncio
from dotenv import load_dotenv
load_dotenv()
import json
import os
import re
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, ValidationError
from groq import AsyncGroq, RateLimitError, APIStatusError

from Dbhelper.rules_db_helper import save_rule

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_EXTRACTION_MODEL", "qwen/qwen3.6-27b")
FALLBACK_MODELS = [
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-20b",
    "groq/compound-mini",
    "qwen/qwen3.8-27b"
]


MAX_CONCURRENT_EXTRACTIONS = int(os.getenv("RULE_EXTRACTION_CONCURRENCY", "5"))


class RuleScope(BaseModel):
    tool: Optional[str] = Field(None, description="Target tool name, e.g. 'crm', 'payment', 'email'")
    operation: Optional[str] = Field(None, description="Target operation, e.g. 'transfer_funds', 'delete_customer'")
    flow_id: Optional[str] = Field(None, description="Flow classification ID, e.g. 'payment_transfer'")


class RuleCondition(BaseModel):
    field: Optional[str] = Field(None, description="Target field path in action arguments, e.g. 'amount', 'recipient.domain'")
    operator: Optional[str] = Field(None, description="Comparison operator: '==', '!=', '>', '>=', '<', '<=', 'in', 'not_in', 'contains'")
    value: Optional[Any] = Field(None, description="Target value for evaluation")


class ExtractedRule(BaseModel):
    scope: RuleScope
    condition: RuleCondition
    effect: Literal["ALLOW", "BLOCK", "ESCALATE"]
    required_approval_role: Optional[str] = None
    source_clause: Optional[str] = None


class ExtractionResult(BaseModel):
    has_enforceable_rules: bool
    rules: List[ExtractedRule] = Field(default_factory=list)


_SKIP_PATTERNS = [
    r"^#{1,4}\s*$",
    r"^(page\s*\d+|pg\.?\s*\d+)$",
    r"^table\s+of\s+contents",
    r"^(figure|table|appendix)\s+\d+",
    r"^[©®]|copyright|all rights reserved",
    r"^\s*[-–—]+\s*$",
]


def _should_skip_chunk(text: str) -> bool:
    stripped = text.strip()
    if len(stripped.split()) < 40:
        return True
    t_lower = stripped.lower()
    for pattern in _SKIP_PATTERNS:
        if re.search(pattern, t_lower, re.IGNORECASE | re.MULTILINE):
            return True
    return False


EXTRACTION_SYSTEM_PROMPT = """You are a strict Policy Rule Extraction Engine for an enterprise AI Action Gateway.
Your task is to analyze a policy clause and extract ALL deterministic, enforceable rules it contains.

CRITICAL: A single clause often encodes multiple tiers or thresholds.
Example: "Under Rs 2,000 auto-approved; Rs 2,000-15,000 require support-lead review; above Rs 15,000 require fraud-team sign-off"
→ This MUST produce 3 separate rule objects, one per tier. Never merge or drop tiers.

For EACH enforceable rule found:
  - Identify the target tool (e.g., 'payment', 'crm', 'email', 'refund', 'order').
  - Identify the operation (e.g., 'transfer_funds', 'issue_refund', 'cancel_order', 'delete_customer').
  - Identify the condition: argument field (e.g. 'amount', 'recipient.domain'), operator, and comparison value.
  - Set the effect: 'ALLOW' (auto-permitted), 'BLOCK' (forbidden), or 'ESCALATE' (requires human approval).
  - If effect is 'ESCALATE', set required_approval_role (e.g., 'finance_manager', 'compliance_officer').
  - Quote the exact source_clause verbatim from the text.

Output STRICT JSON — no markdown fences, no commentary:
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


_groq_client: Optional[AsyncGroq] = None


def _get_client() -> Optional[AsyncGroq]:
    global _groq_client
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return None
    if _groq_client is None:
        _groq_client = AsyncGroq(api_key=api_key)
    return _groq_client


async def _call_groq_api(prompt: str, system_prompt: str) -> Optional[str]:
    client = _get_client()
    if client is None:
        print("[RuleExtraction] GROQ_API_KEY not configured. Skipping LLM call.")
        return None

    models_to_try = [GROQ_MODEL] + [m for m in FALLBACK_MODELS if m != GROQ_MODEL]

    for model in models_to_try:
        for rate_limit_attempt in range(2):
            try:
                response = await client.chat.completions.create(
                    model=model,
                    temperature=0,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    timeout=30,
                )
                return response.choices[0].message.content
            except RateLimitError:
                print(f"[RuleExtraction] Groq model '{model}' rate-limited, backing off...")
                await asyncio.sleep(2.0 ** rate_limit_attempt * 3)
                continue
            except APIStatusError as e:
                if e.status_code in (404, 400):
                    print(f"[RuleExtraction] Groq model '{model}' hit HTTP {e.status_code}, trying fallback...")
                    break
                print(f"[RuleExtraction] Groq API HTTP {e.status_code} error: {e}")
                return None
            except Exception as e:
                print(f"[RuleExtraction] Groq API error for model {model}: {e}")
                break
    return None


def parse_and_validate_rules(raw_json_str: str) -> List[ExtractedRule]:
    try:
        clean_str = raw_json_str.strip()
        if clean_str.startswith("```"):
            clean_str = re.sub(r"^```(?:json)?\n?", "", clean_str)
            clean_str = re.sub(r"\n?```$", "", clean_str)
        data = json.loads(clean_str)
        result = ExtractionResult.model_validate(data)
        return result.rules if result.has_enforceable_rules else []
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"[RuleExtraction] Schema validation error: {e}")
        return []


async def extract_rules_from_chunk(
    chunk_text: str,
    chunk_id: str,
    doc_id: str,
    max_retries: int = 1
) -> List[str]:
    if _should_skip_chunk(chunk_text):
        print(f"[RuleExtraction] Skipping chunk {chunk_id} (short or non-policy content).")
        return []

    user_prompt = (
        f'Policy Clause:\n\"\"\"{chunk_text}\"\"\"\n\n'
        "Extract ALL enforceable rules. "
        "If the clause encodes multiple tiers or thresholds, return each as a separate rule object."
    )

    for attempt in range(max_retries + 1):
        raw_output = await _call_groq_api(user_prompt, EXTRACTION_SYSTEM_PROMPT)
        if not raw_output:
            await asyncio.sleep(2.0 ** attempt * 3)
            continue
        extracted = parse_and_validate_rules(raw_output)
        if not extracted:
            print(f"[RuleExtraction] Retry {attempt + 1} for chunk {chunk_id}: no valid rules parsed.")
            await asyncio.sleep(2.0 ** attempt * 2)
            continue
        saved_ids = []
        for rule in extracted:
            rule_id = await save_rule(
                scope=rule.scope.model_dump(),
                condition=rule.condition.model_dump(),
                effect=rule.effect,
                required_approval_role=rule.required_approval_role,
                source_document=doc_id,
                source_chunk=chunk_id,
                source_clause=rule.source_clause or chunk_text[:500],
                status="DRAFT",
            )
            if rule_id:
                print(
                    f"[RuleExtraction] DRAFT rule {rule_id} "
                    f"(effect={rule.effect}) saved for chunk {chunk_id}"
                )
                saved_ids.append(rule_id)

        return saved_ids

    print(f"[RuleExtraction] Failed to extract rules from chunk {chunk_id} after {max_retries + 1} attempts.")
    return []


async def extract_rules_from_document(doc_id: str, chunks_data: List[Dict[str, Any]]):
    print(
        f"[RuleExtraction] Starting offline rule extraction for doc {doc_id} "
        f"({len(chunks_data)} chunks, max {MAX_CONCURRENT_EXTRACTIONS} concurrent)..."
    )
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_EXTRACTIONS)
    async def _bounded_extract(chunk: Dict[str, Any]) -> List[str]:
        chunk_text = chunk.get("text", "")
        chunk_id = chunk.get("chunk_id", "")
        async with semaphore:
            return await extract_rules_from_chunk(chunk_text, chunk_id, doc_id)
    results = await asyncio.gather(
        *[_bounded_extract(chunk) for chunk in chunks_data],
        return_exceptions=True,
    )

    created_rule_ids: List[str] = []
    for chunk, result in zip(chunks_data, results):
        if isinstance(result, Exception):
            print(f"[RuleExtraction] Chunk {chunk.get('chunk_id', '?')} raised {result!r}, skipping.")
            continue
        created_rule_ids.extend(result)

    print(
        f"[RuleExtraction] Completed extraction for doc {doc_id}. "
        f"Total DRAFT rules created: {len(created_rule_ids)}"
    )
    return created_rule_ids