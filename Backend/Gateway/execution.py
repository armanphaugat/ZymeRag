import json
import os
import urllib.request
import urllib.error
from typing import Dict, Any, Optional
from Backend.Gateway.schemas import ToolAction, ExecutionResult, DecisionEnum
from Backend.Gateway.audit import log_audit_event

GATEWAY_SECRET = os.getenv("GATEWAY_INTERNAL_SECRET", "gateway_internal_secret")
MOCK_SERVICES_URL = os.getenv("MOCK_SERVICES_URL", "http://127.0.0.1:8001")


def _http_request(method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Helper to call Mock Enterprise Services carrying the Gateway-issued credential."""
    url = f"{MOCK_SERVICES_URL}{path}"
    headers = {
        "X-Gateway-Secret": GATEWAY_SECRET,
        "Content-Type": "application/json",
        "User-Agent": "AI-Action-Gateway/1.0",
    }
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Service returned HTTP {e.code}: {body}")
    except Exception as e:
        raise RuntimeError(f"Failed to connect to enterprise service at {url}: {e}")


async def enqueue_side_effect_action(action: ToolAction, flow_id: str) -> Dict[str, Any]:
    """
    Enqueues async side-effect actions (like email/notifications) using BullMQ/Redis if available,
    or falls back to direct execution if Redis is not running.
    """
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))

    try:
        from bullmq import Queue
        connection = {"host": redis_host, "port": redis_port}
        queue = Queue("ActionSideEffects", {"connection": connection})
        job = await queue.add(
            f"{action.tool}_{action.operation}",
            action.model_dump(),
            {"attempts": 3, "backoff": {"type": "exponential", "delay": 5000}},
        )
        return {"status": "enqueued", "job_id": job.id, "queue": "ActionSideEffects"}
    except Exception as e:
        print(f"[Execution] BullMQ enqueue unavailable ({e}). Executing side effect directly.")
        return await _execute_mock_service(action)


async def _execute_mock_service(action: ToolAction) -> Dict[str, Any]:
    """Routes an allowed ToolAction to the corresponding mock enterprise service."""
    tool = action.tool.strip().lower()
    op = action.operation.strip().lower()
    args = action.arguments

    if tool == "payment":
        if op == "transfer_funds":
            return _http_request("POST", "/payment/transfer", args)
        elif op == "refund_payment":
            return _http_request("POST", "/payment/refund", args)
        else:
            raise ValueError(f"Unknown payment operation '{op}'")

    elif tool == "crm":
        if op == "get_customer":
            cid = args.get("customer_id", action.resource)
            return _http_request("GET", f"/crm/customer/{cid}")
        elif op == "update_customer":
            cid = args.get("customer_id", action.resource)
            return _http_request("PUT", f"/crm/customer/{cid}", args)
        elif op == "delete_customer":
            cid = args.get("customer_id", action.resource)
            return _http_request("DELETE", f"/crm/customer/{cid}")
        else:
            raise ValueError(f"Unknown CRM operation '{op}'")

    elif tool == "email":
        if op == "send_email":
            return _http_request("POST", "/email/send", args)
        else:
            raise ValueError(f"Unknown email operation '{op}'")

    else:
        # Generic mock execution fallback for custom tools
        return {
            "status": "success",
            "message": f"Action {tool}:{op} executed successfully via Gateway.",
            "arguments": args,
        }


async def execute_action(action: ToolAction, flow_id: str = "generic") -> ExecutionResult:
    """
    Executes an action that has passed policy evaluation (ALLOW or approved ESCALATE).
    Logs the outcome to the audit log.
    """
    try:
        # If the action is an external side-effect (e.g. email notification), enqueue
        if action.tool.strip().lower() in ("email", "notification"):
            res = await enqueue_side_effect_action(action, flow_id)
        else:
            res = await _execute_mock_service(action)

        # Log successful execution in audit trail
        await log_audit_event(
            action_id=str(action.action_id),
            tool=action.tool,
            operation=action.operation,
            flow_id=flow_id,
            decision="EXECUTED",
            agent_id=action.agent_id,
            user_id=action.user_id,
            details={"result": res},
        )

        return ExecutionResult(
            action_id=action.action_id,
            status="success",
            decision=DecisionEnum.ALLOW,
            executed=True,
            result=res,
            error=None,
        )

    except Exception as e:
        error_msg = str(e)
        print(f"[Execution] Execution failed for action {action.action_id}: {error_msg}")

        # Log execution failure in audit trail
        await log_audit_event(
            action_id=str(action.action_id),
            tool=action.tool,
            operation=action.operation,
            flow_id=flow_id,
            decision="EXECUTION_FAILED",
            agent_id=action.agent_id,
            user_id=action.user_id,
            details={"error": error_msg},
        )

        return ExecutionResult(
            action_id=action.action_id,
            status="error",
            decision=DecisionEnum.ALLOW,
            executed=False,
            result=None,
            error=error_msg,
        )
