import json
import re
from typing import Dict, Any, List, Optional, Tuple
from Backend.Gateway.schemas import ToolAction, DecisionEnum, DecisionResponse
from Dbhelper.rules_db_helper import get_approved_rules_for_action


def resolve_dot_path(data: Dict[str, Any], path: str) -> Tuple[bool, Any]:
    """
    Extracts nested value using dot notation, e.g. 'recipient.email' or 'transaction.amount'.
    Returns (found: bool, value: Any).
    """
    if not path:
        return False, None

    keys = path.split(".")
    curr = data
    for k in keys:
        if isinstance(curr, dict) and k in curr:
            curr = curr[k]
        elif isinstance(curr, (list, tuple)) and k.isdigit() and int(k) < len(curr):
            curr = curr[int(k)]
        else:
            return False, None
    return True, curr


def evaluate_condition(condition: Any, arguments: Dict[str, Any]) -> bool:
    """
    Deterministically evaluates a rule condition against action arguments.
    Supports single conditions, lists of conditions (AND), and logical operators ("all", "and", "any", "or").
    """
    if not condition:
        return True

    # If condition is a list of sub-conditions, ALL must be True (AND logic)
    if isinstance(condition, list):
        return all(evaluate_condition(c, arguments) for c in condition)

    if isinstance(condition, dict):
        if "all" in condition and isinstance(condition["all"], list):
            return all(evaluate_condition(c, arguments) for c in condition["all"])
        if "and" in condition and isinstance(condition["and"], list):
            return all(evaluate_condition(c, arguments) for c in condition["and"])
        if "any" in condition and isinstance(condition["any"], list):
            return any(evaluate_condition(c, arguments) for c in condition["any"])
        if "or" in condition and isinstance(condition["or"], list):
            return any(evaluate_condition(c, arguments) for c in condition["or"])

        field = condition.get("field")
        operator = condition.get("operator", "==").strip().lower()
        target_value = condition.get("value")

        if not field:
            return True

        found, actual_value = resolve_dot_path(arguments, field)
        if not found:
            return False

        try:
            if operator in ("==", "eq"):
                if isinstance(target_value, bool) or isinstance(actual_value, bool):
                    return bool(actual_value) == bool(target_value)
                return actual_value == target_value
            elif operator in ("!=", "neq"):
                if isinstance(target_value, bool) or isinstance(actual_value, bool):
                    return bool(actual_value) != bool(target_value)
                return actual_value != target_value
            elif operator in (">", "gt"):
                return float(actual_value) > float(target_value)
            elif operator in (">=", "gte"):
                return float(actual_value) >= float(target_value)
            elif operator in ("<", "lt"):
                return float(actual_value) < float(target_value)
            elif operator in ("<=", "lte"):
                return float(actual_value) <= float(target_value)
            elif operator in ("in", "between"):
                if isinstance(target_value, (list, tuple)) and len(target_value) == 2 and all(isinstance(x, (int, float)) for x in target_value):
                    try:
                        val = float(actual_value)
                        low, high = sorted([float(target_value[0]), float(target_value[1])])
                        return low <= val <= high
                    except (ValueError, TypeError):
                        pass
                if isinstance(target_value, (list, tuple, set, str)):
                    return actual_value in target_value
                return False
            elif operator in ("not_in",):
                if isinstance(target_value, (list, tuple, set, str)):
                    return actual_value not in target_value
                return False
            elif operator in ("contains",):
                if isinstance(actual_value, (list, tuple, set, str)):
                    return target_value in actual_value
                return False
            elif operator in ("regex",):
                return bool(re.search(str(target_value), str(actual_value)))
            else:
                print(f"[PolicyEngine] Unsupported operator '{operator}' in condition.")
                return False
        except (ValueError, TypeError) as e:
            print(f"[PolicyEngine] Type conversion error in condition evaluation: {e}")
            return False

    return False


async def evaluate_action_policy(action: ToolAction, flow_id: str) -> DecisionResponse:
    """
    Evaluates an incoming ToolAction against active APPROVED rules.
    - Zero runtime LLM.
    - Deny by default: If no rule matches -> BLOCK.
    - Conflict resolution: BLOCK > ESCALATE > ALLOW.
    """
    tool = action.tool.strip().lower()
    operation = action.operation.strip().lower()

    # Retrieve all APPROVED rules for this scope
    candidate_rules = await get_approved_rules_for_action(flow_id, tool, operation)

    matched_rules = []
    for rule in candidate_rules:
        cond = rule.get("condition")
        if isinstance(cond, str):
            try:
                cond = json.loads(cond)
            except Exception:
                cond = {}
        if evaluate_condition(cond, action.arguments):
            matched_rules.append(rule)

    # 1. Deny by default: if no rule matched
    if not matched_rules:
        return DecisionResponse(
            action_id=action.action_id,
            decision=DecisionEnum.BLOCK,
            flow_id=flow_id,
            matched_rule_id=None,
            reason=f"Deny by default: No approved policy rule permits {tool}:{operation} in flow '{flow_id}'.",
            source_clause=None,
            required_approval_role=None,
        )

    # 2. Conflict resolution: Most restrictive wins (BLOCK > ESCALATE > ALLOW)
    block_rules = [r for r in matched_rules if r.get("effect", "").upper() == "BLOCK"]
    if block_rules:
        r = block_rules[0]
        return DecisionResponse(
            action_id=action.action_id,
            decision=DecisionEnum.BLOCK,
            flow_id=flow_id,
            matched_rule_id=str(r.get("rule_id")),
            reason=f"Action blocked by policy rule {r.get('rule_id')}.",
            source_clause=r.get("source_clause"),
            required_approval_role=None,
        )

    escalate_rules = [r for r in matched_rules if r.get("effect", "").upper() == "ESCALATE"]
    if escalate_rules:
        r = escalate_rules[0]
        return DecisionResponse(
            action_id=action.action_id,
            decision=DecisionEnum.ESCALATE,
            flow_id=flow_id,
            matched_rule_id=str(r.get("rule_id")),
            reason=f"Action requires human approval by role '{r.get('required_approval_role', 'admin')}'.",
            source_clause=r.get("source_clause"),
            required_approval_role=r.get("required_approval_role", "admin"),
        )

    allow_rules = [r for r in matched_rules if r.get("effect", "").upper() == "ALLOW"]
    if allow_rules:
        r = allow_rules[0]
        return DecisionResponse(
            action_id=action.action_id,
            decision=DecisionEnum.ALLOW,
            flow_id=flow_id,
            matched_rule_id=str(r.get("rule_id")),
            reason=f"Action permitted by policy rule {r.get('rule_id')}.",
            source_clause=r.get("source_clause"),
            required_approval_role=None,
        )

    # Fallback to BLOCK if effects are unexpected
    return DecisionResponse(
        action_id=action.action_id,
        decision=DecisionEnum.BLOCK,
        flow_id=flow_id,
        matched_rule_id=None,
        reason="Deny by default: Ambiguous or invalid policy effect.",
        source_clause=None,
        required_approval_role=None,
    )
