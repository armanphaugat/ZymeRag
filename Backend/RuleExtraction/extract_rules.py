import asyncio
from dotenv import load_dotenv
load_dotenv()
import json
import os
import re
import urllib.request
import urllib.error
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, ValidationError

from Dbhelper.rules_db_helper import save_rule

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_EXTRACTION_MODEL", "qwen/qwen3.6-27b")
FALLBACK_MODELS = [
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-20b",
    "groq/compound-mini",
    "qwen/qwen3.8-27b"
]
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class RuleScope(BaseModel):
    tool: Optional[str] = Field(None, description="Target tool name, e.g. 'crm', 'payment', 'email'")
    operation: Optional[str] = Field(None, description="Target operation, e.g. 'transfer_funds', 'delete_customer'")
    flow_id: Optional[str] = Field(None, description="Flow classification ID, e.g. 'payment_transfer'")


class RuleCondition(BaseModel):
    field: Optional[str] = Field(None, description="Target field path in action arguments, e.g. 'amount', 'recipient.domain'")
    operator: Optional[str] = Field(None, description="Comparison operator: '==', '!=', '>', '>=', '<', '<=', 'in', 'not_in', 'contains'")
    value: Optional[Any] = Field(None, description="Target value for evaluation")


class ExtractedRule(BaseModel):
    """A single enforceable rule extracted from a policy clause."""
    scope: RuleScope
    condition: RuleCondition
    effect: Literal["ALLOW", "BLOCK", "ESCALATE"]
    required_approval_role: Optional[str] = None
    source_clause: Optional[str] = None


class ExtractionResult(BaseModel):
    """
    Wrapper returned by the LLM per clause chunk.
    A single clause (e.g. Section 3.1 with three refund tiers) may produce
    multiple enforceable rules — they are all captured here, not silently dropped.
    """
    has_enforceable_rules: bool
    rules: List[ExtractedRule] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Chunk pre-filter — skip chunks that cannot contain a policy rule
# ---------------------------------------------------------------------------
_SKIP_PATTERNS = [
    r"^#{1,4}\s*$",
    r"^(page\s*\d+|pg\.?\s*\d+)$",
    r"^table\s+of\s+contents",
    r"^(figure|table|appendix)\s+\d+",
    r"^[©®]|copyright|all rights reserved",
    r"^\s*[-–—]+\s*$",
]


def _should_skip_chunk(text: str) -> bool:
    """Return True for chunks structurally unable to contain a policy rule."""
    stripped = text.strip()
    # Fewer than 40 words is almost certainly a heading, caption, or fragment
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


def _call_groq_api(prompt: str, system_prompt: str) -> Optional[str]:
    """Invokes the Groq chat completions API with temperature 0."""
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        print("[RuleExtraction] GROQ_API_KEY not configured. Skipping LLM call.")
        return None

    payload = {
        "model": GROQ_MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    }

    models_to_try = [GROQ_MODEL] + [m for m in FALLBACK_MODELS if m != GROQ_MODEL]

    for model in models_to_try:
        payload["model"] = model
        req = urllib.request.Request(
            GROQ_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            if e.code in (404, 400, 429):
                print(f"[RuleExtraction] Groq model '{model}' hit HTTP {e.code}, trying fallback...")
                continue
            print(f"[RuleExtraction] Groq API HTTP {e.code} error: {body}")
            return None
        except Exception as e:
            print(f"[RuleExtraction] Groq API error for model {model}: {e}")
            continue
    return None


def parse_and_validate_rules(raw_json_str: str) -> List[ExtractedRule]:
    """
    Parses and validates raw LLM output against the ExtractionResult schema.
    Returns a list of valid ExtractedRule objects (empty list on any parse error).
    """
    try:
        clean_str = raw_json_str.strip()
        # Strip markdown fence if present
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
    """
    Offline extractor: analyzes a single clause chunk, calls Groq LLM,
    validates output against ExtractionResult schema (wraps a LIST of rules),
    and inserts ALL valid rules into the rules table with status='DRAFT'.

    A multi-tier clause (e.g. Section 3.1 with three refund tiers) produces
    multiple DRAFT rule rows — one per tier — instead of silently dropping all
    but the first.

    Returns a list of saved rule_ids (may be empty if nothing was extracted).
    """
    # --- Pre-filter: skip chunks structurally unable to contain a policy rule ---
    if _should_skip_chunk(chunk_text):
        print(f"[RuleExtraction] Skipping chunk {chunk_id} (short or non-policy content).")
        return []

    user_prompt = (
        f'Policy Clause:\n\"\"\"{chunk_text}\"\"\"\n\n'
        "Extract ALL enforceable rules. "
        "If the clause encodes multiple tiers or thresholds, return each as a separate rule object."
    )

    for attempt in range(max_retries + 1):
        raw_output = _call_groq_api(user_prompt, EXTRACTION_SYSTEM_PROMPT)
        if not raw_output:
            # Exponential backoff before retry on network/API failure
            await asyncio.sleep(2.0 ** attempt * 3)
            continue

        extracted = parse_and_validate_rules(raw_output)
        if not extracted:
            print(f"[RuleExtraction] Retry {attempt + 1} for chunk {chunk_id}: no valid rules parsed.")
            await asyncio.sleep(2.0 ** attempt * 2)
            continue

        # Save every rule extracted from this clause
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
    """
    Triggers offline rule extraction over all chunks of an uploaded policy document.
    Runs asynchronously as a background task after PDF ingestion.

    Rate-limit strategy:
      - Chunks shorter than 40 words or matching non-policy patterns are skipped
        before any API call is made (saves ~60% of Groq calls on typical policy docs).
      - A fixed 5-second pause between chunks keeps throughput well within
        Groq free-tier limits (~30 req/min, ~6k tokens/min).
      - On LLM failure, extract_rules_from_chunk applies exponential backoff
        per retry before giving up on that chunk.
    """
    print(
        f"[RuleExtraction] Starting offline rule extraction for doc {doc_id} "
        f"({len(chunks_data)} chunks)..."
    )
    created_rule_ids: List[str] = []

    for chunk in chunks_data:
        chunk_text = chunk.get("text", "")
        chunk_id = chunk.get("chunk_id", "")

        # Returns a list — one entry per rule/tier found in this clause
        rule_ids = await extract_rules_from_chunk(chunk_text, chunk_id, doc_id)
        created_rule_ids.extend(rule_ids)

        # 5-second inter-chunk pause to stay within Groq free-tier rate limits
        await asyncio.sleep(5.0)

    print(
        f"[RuleExtraction] Completed extraction for doc {doc_id}. "
        f"Total DRAFT rules created: {len(created_rule_ids)}"
    )
    return created_rule_ids
