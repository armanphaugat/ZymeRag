import unittest
import uuid
import hashlib
from datetime import datetime, timezone

from Backend.Gateway.schemas import ToolAction, DecisionEnum, DecisionResponse
from Backend.Gateway.policy_engine import resolve_dot_path, evaluate_condition
from Backend.Gateway.audit import compute_event_hash, GENESIS_HASH
from MockServices.app import verify_gateway_auth, GATEWAY_SECRET
from fastapi import HTTPException


class TestGatewayCore(unittest.TestCase):

    def test_tool_action_schema_validation(self):
        """Test valid and invalid ToolAction payload parsing."""
        valid_payload = {
            "action_id": str(uuid.uuid4()),
            "agent_id": "sales_agent_01",
            "user_id": "alice@example.com",
            "tool": "payment",
            "operation": "transfer_funds",
            "resource": "account_12345",
            "arguments": {"amount": 500, "currency": "USD"},
            "context": {"department": "Finance"},
        }
        action = ToolAction.model_validate(valid_payload)
        self.assertEqual(action.tool, "payment")
        self.assertEqual(action.arguments["amount"], 500)

        # Invalid payload missing required 'tool'
        invalid_payload = {
            "agent_id": "agent_01",
            "user_id": "alice",
            "operation": "transfer",
            "resource": "res_1",
        }
        with self.assertRaises(Exception):
            ToolAction.model_validate(invalid_payload)

    def test_dot_path_resolution(self):
        """Test nested dot notation extraction from action arguments."""
        data = {
            "amount": 2500,
            "recipient": {
                "name": "Acme Corp",
                "email": "billing@acme.com",
                "address": {"country": "US", "zip": "94103"}
            },
            "tags": ["urgent", "contractor"]
        }
        found, val = resolve_dot_path(data, "amount")
        self.assertTrue(found)
        self.assertEqual(val, 2500)

        found, val = resolve_dot_path(data, "recipient.email")
        self.assertTrue(found)
        self.assertEqual(val, "billing@acme.com")

        found, val = resolve_dot_path(data, "recipient.address.country")
        self.assertTrue(found)
        self.assertEqual(val, "US")

        found, val = resolve_dot_path(data, "tags.0")
        self.assertTrue(found)
        self.assertEqual(val, "urgent")

        found, val = resolve_dot_path(data, "non_existent.field")
        self.assertFalse(found)

    def test_condition_evaluation_operators(self):
        """Test operators: ==, !=, >, >=, <, <=, in, not_in, contains, regex."""
        args = {
            "amount": 10000,
            "currency": "EUR",
            "country": "IR",
            "recipient_email": "vendor@sanctioned-entity.org",
            "categories": ["electronics", "defense"],
        }

        # Numeric >
        self.assertTrue(evaluate_condition({"field": "amount", "operator": ">", "value": 5000}, args))
        self.assertFalse(evaluate_condition({"field": "amount", "operator": ">", "value": 15000}, args))

        # Numeric <=
        self.assertTrue(evaluate_condition({"field": "amount", "operator": "<=", "value": 10000}, args))

        # Equality ==
        self.assertTrue(evaluate_condition({"field": "currency", "operator": "==", "value": "EUR"}, args))
        self.assertFalse(evaluate_condition({"field": "currency", "operator": "==", "value": "USD"}, args))

        # in list
        self.assertTrue(evaluate_condition({"field": "country", "operator": "in", "value": ["IR", "KP", "SY"]}, args))
        self.assertFalse(evaluate_condition({"field": "country", "operator": "not_in", "value": ["IR", "KP", "SY"]}, args))

        # contains
        self.assertTrue(evaluate_condition({"field": "recipient_email", "operator": "contains", "value": "sanctioned"}, args))

        # regex
        self.assertTrue(evaluate_condition({"field": "recipient_email", "operator": "regex", "value": r"@sanctioned-entity\.(org|com)"}, args))

    def test_audit_hash_chaining_and_tamper_detection(self):
        """Test SHA-256 cryptographic chain generation and verification."""
        prev_hash = GENESIS_HASH
        event1 = {
            "event_id": str(uuid.uuid4()),
            "action_id": str(uuid.uuid4()),
            "tool": "payment",
            "operation": "transfer",
            "decision": "ALLOW",
        }
        curr_hash1 = compute_event_hash(prev_hash, event1)
        self.assertEqual(len(curr_hash1), 64)

        event2 = {
            "event_id": str(uuid.uuid4()),
            "action_id": str(uuid.uuid4()),
            "tool": "crm",
            "operation": "delete_customer",
            "decision": "BLOCK",
        }
        curr_hash2 = compute_event_hash(curr_hash1, event2)
        self.assertNotEqual(curr_hash1, curr_hash2)

        # Simulate tampering with event1 payload
        tampered_event1 = dict(event1)
        tampered_event1["decision"] = "BLOCK"  # Attacker modified decision in database
        recomputed_hash1 = compute_event_hash(prev_hash, tampered_event1)
        self.assertNotEqual(curr_hash1, recomputed_hash1, "Tampering must break the computed hash")

    def test_mock_services_direct_bypass_prevention(self):
        """Verify mock enterprise services reject calls without Gateway secret."""
        # 1. No header -> Should raise HTTP 401
        with self.assertRaises(HTTPException) as ctx:
            verify_gateway_auth(None)
        self.assertEqual(ctx.exception.status_code, 401)

        # 2. Invalid secret -> Should raise HTTP 401
        with self.assertRaises(HTTPException) as ctx:
            verify_gateway_auth("invalid_intruder_key")
        self.assertEqual(ctx.exception.status_code, 401)

        # 3. Correct gateway secret -> Passes
        try:
            verify_gateway_auth(GATEWAY_SECRET)
        except HTTPException:
            self.fail("Valid gateway secret unexpectedly raised HTTPException")


if __name__ == "__main__":
    unittest.main()
