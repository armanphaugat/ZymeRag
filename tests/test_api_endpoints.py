import unittest
import uuid
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from Backend.app import app
from Backend.Middleware.auth import GATEWAY_API_KEY
from MockServices.app import app as mock_app, GATEWAY_SECRET


class TestApiEndpoints(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.mock_client = TestClient(mock_app)
        self.auth_headers = {"Authorization": f"Bearer {GATEWAY_API_KEY}"}

    def test_health_endpoint_is_public(self):
        """Verify health check is public and returns 200 without auth."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn(data["service"], ["Axiom Gateway", "AI Action Gateway"])

    def test_unauthenticated_request_returns_401(self):
        """Verify endpoints without auth token are rejected by auth middleware."""
        response = self.client.get("/rules")
        self.assertEqual(response.status_code, 401)
        self.assertIn("Missing Bearer Token", response.json().get("detail", ""))

    def test_authenticated_rules_listing(self):
        """Verify authenticated request to /rules passes auth middleware."""
        with patch("Backend.Controller.rules_controller.get_rules", new_callable=AsyncMock) as mock_get_rules:
            mock_get_rules.return_value = [
                {
                    "rule_id": str(uuid.uuid4()),
                    "version": 1,
                    "scope": {"tool": "payment", "operation": "transfer_funds"},
                    "condition": {"field": "amount", "operator": "<=", "value": 5000},
                    "effect": "ALLOW",
                    "status": "APPROVED",
                }
            ]
            response = self.client.get("/rules", headers=self.auth_headers)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["total"], 1)
            self.assertEqual(data["rules"][0]["effect"], "ALLOW")

    def test_action_evaluation_deny_by_default(self):
        """Verify an unregistered/unapproved tool action is BLOCKED by default."""
        with patch("Backend.Controller.gateway_controller.classify_flow", new_callable=AsyncMock) as mock_classify, \
             patch("Backend.Gateway.policy_engine.get_approved_rules_for_action", new_callable=AsyncMock) as mock_rules, \
             patch("Backend.Controller.gateway_controller.log_audit_event", new_callable=AsyncMock) as mock_audit:

            mock_classify.return_value = "unclassified"
            mock_rules.return_value = []  # No approved rules match
            mock_audit.return_value = str(uuid.uuid4())

            payload = {
                "action_id": str(uuid.uuid4()),
                "agent_id": "rogue_agent",
                "user_id": "bob@example.com",
                "tool": "database",
                "operation": "drop_table",
                "resource": "users",
                "arguments": {"table": "users"},
            }

            response = self.client.post("/actions/evaluate", json=payload, headers=self.auth_headers)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["decision"], "BLOCK")
            self.assertIn("Deny by default", data["reason"])

    def test_action_evaluation_escalation_flow(self):
        """Verify an action matching an ESCALATE rule creates an approval record."""
        rule_id = str(uuid.uuid4())
        with patch("Backend.Controller.gateway_controller.classify_flow", new_callable=AsyncMock) as mock_classify, \
             patch("Backend.Gateway.policy_engine.get_approved_rules_for_action", new_callable=AsyncMock) as mock_rules, \
             patch("Backend.Controller.gateway_controller.create_pending_approval", new_callable=AsyncMock) as mock_approval, \
             patch("Backend.Controller.gateway_controller.log_audit_event", new_callable=AsyncMock) as mock_audit:

            mock_classify.return_value = "payment_transfer"
            mock_rules.return_value = [
                {
                    "rule_id": rule_id,
                    "scope": {"tool": "payment", "operation": "transfer_funds", "flow_id": "payment_transfer"},
                    "condition": {"field": "amount", "operator": ">", "value": 10000},
                    "effect": "ESCALATE",
                    "required_approval_role": "finance_director",
                    "source_clause": "Transfers exceeding $10,000 require Finance Director escalation.",
                }
            ]
            mock_approval.return_value = "appr_12345"
            mock_audit.return_value = str(uuid.uuid4())

            payload = {
                "action_id": str(uuid.uuid4()),
                "agent_id": "payment_agent",
                "user_id": "finance_user",
                "tool": "payment",
                "operation": "transfer_funds",
                "resource": "account_999",
                "arguments": {"amount": 25000, "currency": "USD"},
            }

            response = self.client.post("/actions/evaluate", json=payload, headers=self.auth_headers)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["decision"], "ESCALATE")
            self.assertEqual(data["required_approval_role"], "finance_director")
            self.assertEqual(data["approval_id"], "appr_12345")
            self.assertIn("Finance Director", data["source_clause"])

    def test_mock_services_isolated_bypass_prevention(self):
        """Verify Mock Services reject direct bypass without X-Gateway-Secret."""
        # 1. Direct call without secret
        res = self.mock_client.post("/payment/transfer", json={"account_id": "1", "recipient": "bob", "amount": 100})
        self.assertEqual(res.status_code, 401)
        self.assertIn("Direct bypass attempt blocked", res.json()["detail"])

        # 2. Call with Gateway secret
        res = self.mock_client.post(
            "/payment/transfer",
            json={"account_id": "1", "recipient": "bob", "amount": 100},
            headers={"X-Gateway-Secret": GATEWAY_SECRET},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "success")
        self.assertEqual(res.json()["amount"], 100)

    def test_audit_verify_endpoint(self):
        """Verify audit chain verification endpoint returns valid status."""
        with patch("Backend.Controller.gateway_controller.verify_audit_chain_integrity", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = (True, ["Chain is intact"])
            response = self.client.get("/actions/audit/verify", headers=self.auth_headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "TAMPER_FREE")
            self.assertTrue(response.json()["is_valid"])


if __name__ == "__main__":
    unittest.main()
