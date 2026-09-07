import json
import unittest
import uuid
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from Backend.app import app
from Backend.Gateway.schemas import ToolAction, DecisionEnum, DecisionResponse
from Backend.Middleware.auth import GATEWAY_API_KEY


class TestExecutionAndRevalidation(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.auth_headers = {"Authorization": f"Bearer {GATEWAY_API_KEY}"}

    def test_execute_allow_flow(self):
        """Test execute endpoint when policy returns ALLOW."""
        with patch("Backend.Controller.gateway_controller.classify_flow", new_callable=AsyncMock) as mock_classify, \
             patch("Backend.Controller.gateway_controller.evaluate_action_policy", new_callable=AsyncMock) as mock_eval, \
             patch("Backend.Controller.gateway_controller.execute_action", new_callable=AsyncMock) as mock_exec, \
             patch("Backend.Controller.gateway_controller.log_audit_event", new_callable=AsyncMock) as mock_audit:

            action_id = uuid.uuid4()
            mock_classify.return_value = "payment_transfer"
            mock_eval.return_value = DecisionResponse(
                action_id=action_id,
                decision=DecisionEnum.ALLOW,
                flow_id="payment_transfer",
                matched_rule_id="rule_allow_1",
                reason="Transfer under limit is allowed.",
            )
            mock_exec.return_value = {
                "action_id": str(action_id),
                "status": "success",
                "decision": "ALLOW",
                "executed": True,
                "result": {"transaction_id": "txn_12345", "amount": 100},
            }
            mock_audit.return_value = str(uuid.uuid4())

            payload = {
                "action_id": str(action_id),
                "agent_id": "finance_agent",
                "user_id": "alice@company.com",
                "tool": "payment",
                "operation": "transfer_funds",
                "resource": "acc_100",
                "arguments": {"amount": 100, "recipient": "vendor_a"},
            }

            response = self.client.post("/actions/execute", json=payload, headers=self.auth_headers)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data["executed"])
            self.assertEqual(data["status"], "success")

    def test_execute_block_flow(self):
        """Test execute endpoint when policy returns BLOCK."""
        with patch("Backend.Controller.gateway_controller.classify_flow", new_callable=AsyncMock) as mock_classify, \
             patch("Backend.Controller.gateway_controller.evaluate_action_policy", new_callable=AsyncMock) as mock_eval, \
             patch("Backend.Controller.gateway_controller.log_audit_event", new_callable=AsyncMock) as mock_audit:

            action_id = uuid.uuid4()
            mock_classify.return_value = "unclassified"
            mock_eval.return_value = DecisionResponse(
                action_id=action_id,
                decision=DecisionEnum.BLOCK,
                flow_id="unclassified",
                matched_rule_id=None,
                reason="Deny by default: No rule permits this action.",
            )
            mock_audit.return_value = str(uuid.uuid4())

            payload = {
                "action_id": str(action_id),
                "agent_id": "rogue_agent",
                "user_id": "attacker@evil.com",
                "tool": "crm",
                "operation": "purge_database",
                "resource": "all",
            }

            response = self.client.post("/actions/execute", json=payload, headers=self.auth_headers)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertFalse(data["executed"])
            self.assertEqual(data["decision"], "BLOCK")
            self.assertEqual(data["status"], "blocked")

    def test_pre_execution_revalidation_failure(self):
        """
        CRITICAL TEST: If a human approves an escalated action, but policy has changed
        to BLOCK while it was waiting, execution must be aborted with HTTP 403!
        """
        approval_id = str(uuid.uuid4())
        action_id = uuid.uuid4()
        stored_action = {
            "action_id": str(action_id),
            "agent_id": "payment_agent",
            "user_id": "bob",
            "tool": "payment",
            "operation": "transfer_funds",
            "resource": "acc_555",
            "arguments": {"amount": 50000},
            "context": {},
            "timestamp": "2026-09-04T12:00:00Z",
        }

        with patch("Backend.Controller.gateway_controller.get_approval_by_id", new_callable=AsyncMock) as mock_get_appr, \
             patch("Backend.Controller.gateway_controller.classify_flow", new_callable=AsyncMock) as mock_classify, \
             patch("Backend.Controller.gateway_controller.evaluate_action_policy", new_callable=AsyncMock) as mock_eval, \
             patch("Backend.Controller.gateway_controller.update_approval_status", new_callable=AsyncMock) as mock_update, \
             patch("Backend.Controller.gateway_controller.log_audit_event", new_callable=AsyncMock) as mock_audit:

            mock_get_appr.return_value = {
                "approval_id": approval_id,
                "action_id": str(action_id),
                "status": "PENDING",
                "action_payload": json.dumps(stored_action),
                "required_role": "finance_director",
            }
            mock_classify.return_value = "payment_transfer"
            # REVALIDATION RETURNS BLOCK (New compliance rule was approved while waiting!)
            mock_eval.return_value = DecisionResponse(
                action_id=action_id,
                decision=DecisionEnum.BLOCK,
                flow_id="payment_transfer",
                matched_rule_id="new_embargo_rule",
                reason="All transfers over $20,000 are now embargoed.",
            )
            mock_update.return_value = True
            mock_audit.return_value = str(uuid.uuid4())

            decision_payload = {
                "decision": "APPROVED",
                "decided_by": "manager_alice",
            }

            response = self.client.post(
                f"/actions/approvals/{approval_id}/decision",
                json=decision_payload,
                headers=self.auth_headers,
            )
            # Must reject with 403 Forbidden
            self.assertEqual(response.status_code, 403)
            self.assertIn("Pre-execution revalidation failed", response.json()["detail"])
            # Approval must be marked REJECTED in database
            mock_update.assert_called_with(approval_id, "REJECTED", "manager_alice")


if __name__ == "__main__":
    unittest.main()
