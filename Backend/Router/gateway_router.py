from fastapi import APIRouter
from Backend.Controller.gateway_controller import (
    evaluate_action_handler,
    execute_action_handler,
    list_approvals_handler,
    decide_approval_handler,
    get_audit_trail_handler,
    verify_audit_integrity_handler,
    list_flows_handler,
    register_flow_handler,
)

gateway_router = APIRouter()

# Actions (Evaluation & Execution)
gateway_router.add_api_route("/evaluate", evaluate_action_handler, methods=["POST"])
gateway_router.add_api_route("/execute", execute_action_handler, methods=["POST"])

# Approvals Workflow (Human-in-the-loop with Pre-Execution Revalidation)
gateway_router.add_api_route("/approvals", list_approvals_handler, methods=["GET"])
gateway_router.add_api_route("/approvals/{approval_id}/decision", decide_approval_handler, methods=["POST"])

# Audit Trail (Cryptographic Hash-Chained with Explainability)
gateway_router.add_api_route("/audit", get_audit_trail_handler, methods=["GET"])
gateway_router.add_api_route("/audit/verify", verify_audit_integrity_handler, methods=["GET"])

# Flow Registry Management
gateway_router.add_api_route("/flows", list_flows_handler, methods=["GET"])
gateway_router.add_api_route("/flows", register_flow_handler, methods=["POST"])
