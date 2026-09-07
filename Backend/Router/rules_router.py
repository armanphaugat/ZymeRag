from fastapi import APIRouter
from Backend.Controller.rules_controller import (
    list_rules_handler,
    get_rule_handler,
    approve_rule_handler,
    reject_rule_handler,
    patch_rule_handler,
)

rules_router = APIRouter()
rules_router.add_api_route("", list_rules_handler, methods=["GET"])
rules_router.add_api_route("/{rule_id}", get_rule_handler, methods=["GET"])
rules_router.add_api_route("/{rule_id}/approve", approve_rule_handler, methods=["POST"])
rules_router.add_api_route("/{rule_id}/reject", reject_rule_handler, methods=["POST"])
rules_router.add_api_route("/{rule_id}", patch_rule_handler, methods=["PATCH"])
