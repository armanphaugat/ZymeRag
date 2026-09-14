import logging
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)


def normalize_operator(operator: str) -> str:
    """Normalizes logical comparison operators into standard canonical representations."""
    op = (operator or "").strip().lower()
    op_map = {
        "=": "==",
        "==": "==",
        "eq": "==",
        "equals": "==",
        "!=": "!=",
        "neq": "!=",
        ">": ">",
        "gt": ">",
        ">=": ">=",
        "gte": ">=",
        "<": "<",
        "lt": "<",
        "<=": "<=",
        "lte": "<=",
        "in": "in",
        "not in": "not_in",
        "not_in": "not_in",
        "contains": "contains",
    }
    return op_map.get(op, op)


def normalize_value(value: Any) -> Any:
    """
    Normalizes condition comparison values so identical logical values
    (e.g., '5000' and 5000.0) compare equal, while preserving distinct values.
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        cleaned = value.strip()
        # Check if numeric string
        try:
            # Handle comma separated numbers like "10,000"
            num_str = cleaned.replace(",", "")
            return float(num_str)
        except ValueError:
            return cleaned.lower()

    if isinstance(value, list):
        return tuple(sorted(str(normalize_value(x)) for x in value))

    if isinstance(value, dict):
        return tuple(sorted((k.strip().lower(), str(normalize_value(v))) for k, v in value.items()))

    return str(value).strip().lower()


def compute_rule_signature(rule: Any) -> Tuple:
    """
    Computes a deterministic, normalized signature for an extracted rule.
    Guarantees:
    - Never merges genuinely different thresholds, scopes, operators, or roles.
    - Accurately deduplicates identical rules repeated across multiple document sections.
    """
    # Extract scope attributes
    scope = getattr(rule, "scope", {})
    if hasattr(scope, "model_dump"):
        scope = scope.model_dump()
    elif not isinstance(scope, dict):
        scope = {}

    tool = (scope.get("tool") or "").strip().lower()
    operation = (scope.get("operation") or "").strip().lower()
    flow_id = (scope.get("flow_id") or "").strip().lower() or None

    # Extract condition attributes
    condition = getattr(rule, "condition", {})
    if hasattr(condition, "model_dump"):
        condition = condition.model_dump()
    elif not isinstance(condition, dict):
        condition = {}

    field = (condition.get("field") or "").strip().lower()
    raw_operator = condition.get("operator") or "=="
    norm_operator = normalize_operator(raw_operator)
    raw_value = condition.get("value")
    norm_value = normalize_value(raw_value)

    # Extract effect and required role
    effect = getattr(rule, "effect", "BLOCK")
    if hasattr(effect, "value"):
        effect = effect.value
    norm_effect = str(effect).strip().upper()

    required_role = getattr(rule, "required_approval_role", None)
    norm_role = (required_role or "").strip().lower() or None

    return (
        tool,
        operation,
        flow_id,
        field,
        norm_operator,
        norm_value,
        norm_effect,
        norm_role,
    )


def deduplicate_extracted_rules(
    extracted_rules_with_meta: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Takes a list of dictionaries with {rule, chunk_id, doc_id, page_number, source_clause}
    and deduplicates them based on their normalized signature.
    Preserves the most complete source_clause and aggregates all contributing chunk_ids.
    """
    signature_map: Dict[Tuple, Dict[str, Any]] = {}

    for item in extracted_rules_with_meta:
        rule = item["rule"]
        sig = compute_rule_signature(rule)

        if sig not in signature_map:
            # First time seeing this normalized rule
            signature_map[sig] = {
                "rule": rule,
                "doc_id": item["doc_id"],
                "primary_chunk_id": item["chunk_id"],
                "all_chunk_ids": [item["chunk_id"]],
                "page_number": item.get("page_number", 1),
                "source_clause": item.get("source_clause") or "",
                "signature": sig,
            }
        else:
            # Duplicate rule instance found: update provenance and source clause
            existing = signature_map[sig]
            chunk_id = item["chunk_id"]
            if chunk_id not in existing["all_chunk_ids"]:
                existing["all_chunk_ids"].append(chunk_id)

            # Keep the longer, more descriptive source_clause
            new_clause = item.get("source_clause") or ""
            if len(new_clause) > len(existing["source_clause"]):
                existing["source_clause"] = new_clause
                existing["primary_chunk_id"] = chunk_id
                existing["page_number"] = item.get("page_number", existing["page_number"])

            logger.info(
                f"[RuleDeduplication] Merged duplicate rule signature {sig} "
                f"from chunk {chunk_id} into primary chunk {existing['primary_chunk_id']}."
            )

    return list(signature_map.values())
