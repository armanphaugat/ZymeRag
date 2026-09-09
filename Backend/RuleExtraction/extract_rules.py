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
    has_enforceable_rule: bool
    scope: Optional[RuleScope] = None
    condition: Optional[RuleCondition] = None
    effect: Optional[Literal["ALLOW", "BLOCK", "ESCALATE"]] = None
    required_approval_role: Optional[str] = None
    source_clause: Optional[str] = None


EXTRACTION_SYSTEM_PROMPT = """You are a strict Policy Rule Extraction Engine for an enterprise AI Action Gateway.
Your task is to analyze policy text clauses and extract deterministic, enforceable rules for agent tool actions.

For the given policy clause, determine if an enforceable rule exists for tool operations (e.g. financial payments, CRM data alterations, email dispatches, database deletion).
- If an enforceable rule exists:
  - Identify the target tool (e.g., 'payment', 'crm', 'email').
  - Identify the operation (e.g., 'transfer_funds', 'update_customer', 'send_email').
  - Identify the condition: argument field (e.g. 'amount', 'destination', 'email.recipient'), operator, and comparison value.
  - Set the effect: 'ALLOW' (permitted), 'BLOCK' (forbidden), or 'ESCALATE' (requires human manager approval).
  - If effect is 'ESCALATE', specify required_approval_role (e.g., 'finance_manager', 'compliance_officer').
  - Quote the exact source_clause from the text.
- If no enforceable rule exists, set has_enforceable_rule to false and set all other fields to null.

Output must be STRICT JSON matching this schema:
{
  "has_enforceable_rule": boolean,
  "scope": {"tool": "string", "operation": "string", "flow_id": "string or null"},
  "condition": {"field": "string", "operator": "== | != | > | >= | < | <= | in | not_in | contains", "value": any},
  "effect": "ALLOW | BLOCK | ESCALATE | null",
  "required_approval_role": "string or null",
  "source_clause": "string or null"
}
Do NOT include markdown backticks or commentary. Return only the raw JSON object."""


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


def parse_and_validate_rule(raw_json_str: str) -> Optional[ExtractedRule]:
    """Parses and validates raw LLM output against the ExtractedRule Pydantic schema."""
    try:
        clean_str = raw_json_str.strip()
        # Strip markdown fence if present
        if clean_str.startswith("```"):
            clean_str = re.sub(r"^```(?:json)?\n?", "", clean_str)
            clean_str = re.sub(r"\n?```$", "", clean_str)
        data = json.loads(clean_str)
        rule = ExtractedRule.model_validate(data)
        return rule
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"[RuleExtraction] Schema validation error: {e}")
        return None


async def extract_rule_from_chunk(
    chunk_text: str,
    chunk_id: str,
    doc_id: str,
    max_retries: int = 1
) -> Optional[str]:
    """
    Offline extractor: analyzes a single clause chunk, calls Groq LLM,
    validates output against Pydantic schema with 1 retry on invalid JSON,
    and inserts valid rules into the rules table with status='DRAFT'.
    """
    if len(chunk_text.strip()) < 20:
        return None

    user_prompt = f"Policy Clause:\n\"\"\"{chunk_text}\"\"\"\n\nExtract the enforceable rule if one exists."

    for attempt in range(max_retries + 1):
        raw_output = _call_groq_api(user_prompt, EXTRACTION_SYSTEM_PROMPT)
        if not raw_output:
            continue

        rule = parse_and_validate_rule(raw_output)
        if rule is None:
            print(f"[RuleExtraction] Retry {attempt + 1} for chunk {chunk_id} due to invalid JSON.")
            continue

        if not rule.has_enforceable_rule or not rule.scope or not rule.condition or not rule.effect:
            # Valid parse, but no enforceable rule found in this clause
            return None

        # Insert extracted draft rule into database
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
            print(f"[RuleExtraction] Created DRAFT rule {rule_id} for chunk {chunk_id}")
            return rule_id

    print(f"[RuleExtraction] Failed to extract rule from chunk {chunk_id} after {max_retries + 1} attempts.")
    return None


async def extract_rules_from_document(doc_id: str, chunks_data: List[Dict[str, Any]]):
    """
    Triggers offline rule extraction over all chunks of an uploaded policy document.
    Runs asynchronously and logs all generated draft rules.
    """
    print(f"[RuleExtraction] Starting offline rule extraction for doc {doc_id} ({len(chunks_data)} chunks)...")
    created_rule_ids = []
    for chunk in chunks_data:
        chunk_text = chunk.get("text", "")
        chunk_id = chunk.get("chunk_id", "")
        rule_id = await extract_rule_from_chunk(chunk_text, chunk_id, doc_id)
        await asyncio.sleep(1.0)
        if rule_id:
            created_rule_ids.append(rule_id)

    print(f"[RuleExtraction] Completed extraction for doc {doc_id}. Total DRAFT rules created: {len(created_rule_ids)}")
    return created_rule_ids
