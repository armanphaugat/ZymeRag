import unittest
import uuid
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from Backend.app import app
from Backend.Gateway.schemas import ToolAction, DecisionEnum
from Backend.Gateway.policy_engine import evaluate_action_policy
from Backend.RuleExtraction.filter_chunks import (
    score_heuristics,
    filter_policy_relevant_chunks,
)
from Backend.RuleExtraction.deduplicate_rules import (
    compute_rule_signature,
    deduplicate_extracted_rules,
)
from Backend.Middleware.auth import GATEWAY_API_KEY, ACCESS_TOKEN_SECRET
import jwt
from datetime import datetime, timedelta, timezone


class TestPolicyIngestionAndGovernance(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.admin_headers = {"Authorization": f"Bearer {GATEWAY_API_KEY}"}

        # Generate a normal unprivileged user token (role="user")
        now = datetime.now(timezone.utc)
        user_payload = {
            "user_id": "normal_user_123",
            "role": "user",
            "type": "access",
            "iat": now,
            "exp": now + timedelta(hours=1),
        }
        normal_token = jwt.encode(user_payload, ACCESS_TOKEN_SECRET, algorithm="HS256")
        self.user_headers = {"Authorization": f"Bearer {normal_token}"}

    # ───────────────────────────────────────────────────────────
    # 1. Chunk Pre-Filtering & Boundary Context Tests
    # ───────────────────────────────────────────────────────────
    def test_heuristics_scoring_separates_policy_from_noise(self):
        """Verifies deontic heuristics accurately score policy clauses higher than noise."""
        policy_clause = "All international wires exceeding $25,000 must be authorized by a compliance officer."
        boilerplate = "Copyright 2026 Acme Corp. Table of contents and general index. Page 12."

        policy_score = score_heuristics(policy_clause)
        boiler_score = score_heuristics(boilerplate)

        self.assertGreater(policy_score, boiler_score)
        self.assertGreater(policy_score, 0.30)

    def test_filter_policy_relevant_chunks_with_adjacent_context(self):
        """Verifies high-confidence policy chunks are selected and boundary context is attached."""
        chunks = [
            {"chunk_id": "c1", "page_number": 1, "text": "Document overview and introductory notes."},
            {"chunk_id": "c2", "page_number": 1, "text": "Refunds greater than $1,000 must require approval from support lead."},
            {"chunk_id": "c3", "page_number": 2, "text": "Additional notes on customer communication."},
            {"chunk_id": "c4", "page_number": 2, "text": "Accounts with suspicious flags shall be blocked from any fund transfer."},
            {"chunk_id": "c5", "page_number": 3, "text": "Index and bibliography references."},
            {"chunk_id": "c6", "page_number": 3, "text": "Contact details and helpdesk numbers."},
        ]

        filtered = filter_policy_relevant_chunks(chunks, min_score=0.10)
        filtered_ids = [c["chunk_id"] for c in filtered]

        self.assertIn("c2", filtered_ids)
        self.assertIn("c4", filtered_ids)

        # Check boundary context preservation
        c2_selected = next(c for c in filtered if c["chunk_id"] == "c2")
        self.assertIn("prev_context", c2_selected)
        self.assertIn("next_context", c2_selected)
        self.assertIn("windowed_text", c2_selected)
        self.assertEqual(c2_selected["page_number"], 1)

    def test_filter_failsafe_retains_all_for_small_documents(self):
        """Small documents (<= 5 chunks) must retain all chunks to avoid false negatives."""
        small_chunks = [
            {"chunk_id": f"chunk_{i}", "page_number": 1, "text": f"Policy sentence number {i}."}
            for i in range(4)
        ]
        result = filter_policy_relevant_chunks(small_chunks)
        self.assertEqual(len(result), 4)

    # ───────────────────────────────────────────────────────────
    # 2. Normalization & Deduplication Tests
    # ───────────────────────────────────────────────────────────
    def test_deduplication_merges_identical_and_preserves_provenance(self):
        """Verifies duplicate mentions merge into a single rule while preserving provenance."""
        class DummyRule:
            def __init__(self, tool, op, field, operator, value, effect, role=None):
                self.scope = {"tool": tool, "operation": op, "flow_id": None}
                self.condition = {"field": field, "operator": operator, "value": value}
                self.effect = effect
                self.required_approval_role = role

        rule_v1 = DummyRule("payment", "transfer_funds", "amount", ">=", 5000, "ESCALATE", "manager")
        rule_v2 = DummyRule("Payment", "transfer_funds", "Amount", "gte", "5,000", "ESCALATE", "Manager")

        items = [
            {"rule": rule_v1, "doc_id": "doc_x", "chunk_id": "chk_1", "source_clause": "Short mention", "page_number": 2},
            {"rule": rule_v2, "doc_id": "doc_x", "chunk_id": "chk_2", "source_clause": "Comprehensive detailed policy clause", "page_number": 4},
        ]

        deduped = deduplicate_extracted_rules(items)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["primary_chunk_id"], "chk_2")
        self.assertIn("chk_1", deduped[0]["all_chunk_ids"])
        self.assertIn("chk_2", deduped[0]["all_chunk_ids"])
        self.assertEqual(deduped[0]["source_clause"], "Comprehensive detailed policy clause")

    def test_deduplication_does_not_merge_distinct_thresholds_or_roles(self):
        """Verifies genuinely different thresholds, effects, or approval roles are NEVER merged."""
        class DummyRule:
            def __init__(self, tool, op, field, operator, value, effect, role=None):
                self.scope = {"tool": tool, "operation": op}
                self.condition = {"field": field, "operator": operator, "value": value}
                self.effect = effect
                self.required_approval_role = role

        tier1 = DummyRule("payment", "transfer_funds", "amount", "<=", 2000, "ALLOW")
        tier2 = DummyRule("payment", "transfer_funds", "amount", ">", 2000, "ESCALATE", "lead")
        tier3 = DummyRule("payment", "transfer_funds", "amount", ">", 15000, "ESCALATE", "director")

        items = [
            {"rule": tier1, "doc_id": "doc_x", "chunk_id": "c1"},
            {"rule": tier2, "doc_id": "doc_x", "chunk_id": "c2"},
            {"rule": tier3, "doc_id": "doc_x", "chunk_id": "c3"},
        ]

        deduped = deduplicate_extracted_rules(items)
        self.assertEqual(len(deduped), 3)

    # ───────────────────────────────────────────────────────────
    # 3. Critical Guarantee: DRAFT Rules are NEVER Enforced
    # ───────────────────────────────────────────────────────────
    def test_draft_rules_are_never_enforced_at_runtime(self):
        """
        CRITICAL ARCHITECTURAL GUARANTEE:
        Runtime policy evaluation MUST ignore DRAFT rules.
        Only APPROVED rules can permit or escalate actions.
        """
        import asyncio

        test_action = ToolAction(
            action_id=uuid.uuid4(),
            agent_id="test_agent",
            user_id="test_user",
            tool="payment",
            operation="transfer_funds",
            resource="account_123",
            arguments={"amount": 500.0, "currency": "USD"},
        )

        # Mock database returning NO approved rules (because rule is in DRAFT status)
        with patch("Backend.Gateway.policy_engine.get_approved_rules_for_action", new_callable=AsyncMock) as mock_get_rules:
            mock_get_rules.return_value = []

            loop = asyncio.get_event_loop()
            decision = loop.run_until_complete(
                evaluate_action_policy(test_action, flow_id="payment_transfer")
            )

            # Deny by default must block the action
            self.assertEqual(decision.decision, DecisionEnum.BLOCK)
            self.assertIn("Deny by default", decision.reason)
            self.assertIsNone(decision.matched_rule_id)

    def test_approved_rule_is_enforced_at_runtime(self):
        """Verifies that once a rule is APPROVED, the runtime engine enforces it."""
        import asyncio

        test_action = ToolAction(
            action_id=uuid.uuid4(),
            agent_id="test_agent",
            user_id="test_user",
            tool="payment",
            operation="transfer_funds",
            resource="account_123",
            arguments={"amount": 500.0, "currency": "USD"},
        )

        approved_rule = {
            "rule_id": str(uuid.uuid4()),
            "status": "APPROVED",
            "scope": {"tool": "payment", "operation": "transfer_funds"},
            "condition": {"field": "amount", "operator": "<=", "value": 1000},
            "effect": "ALLOW",
            "source_clause": "Transfers under $1000 auto-approved.",
        }

        with patch("Backend.Gateway.policy_engine.get_approved_rules_for_action", new_callable=AsyncMock) as mock_get_rules:
            mock_get_rules.return_value = [approved_rule]

            loop = asyncio.get_event_loop()
            decision = loop.run_until_complete(
                evaluate_action_policy(test_action, flow_id="payment_transfer")
            )

            self.assertEqual(decision.decision, DecisionEnum.ALLOW)
            self.assertEqual(decision.matched_rule_id, approved_rule["rule_id"])

    # ───────────────────────────────────────────────────────────
    # 4. Authorization Protection on Rule Lifecycle
    # ───────────────────────────────────────────────────────────
    def test_unprivileged_user_cannot_approve_rules(self):
        """A normal user (role='user') must receive 403 Forbidden when attempting to approve rules."""
        rule_id = str(uuid.uuid4())
        response = self.client.post(
            f"/rules/{rule_id}/approve",
            json={"approved_by": "normal_user_123"},
            headers=self.user_headers,
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden", response.json().get("detail", ""))

    def test_unprivileged_user_cannot_reject_rules(self):
        """A normal user (role='user') must receive 403 Forbidden when attempting to reject rules."""
        rule_id = str(uuid.uuid4())
        response = self.client.post(
            f"/rules/{rule_id}/reject",
            headers=self.user_headers,
        )
        self.assertEqual(response.status_code, 403)

    def test_authorized_admin_can_approve_draft_rule(self):
        """An authorized administrator successfully transitions a DRAFT rule to APPROVED."""
        rule_id = str(uuid.uuid4())
        mock_rule = {
            "rule_id": rule_id,
            "status": "DRAFT",
            "name": "Test Rule",
            "version": 1,
        }
        with patch("Backend.Controller.rules_controller.get_rule_by_id", new_callable=AsyncMock) as mock_get,              patch("Backend.Controller.rules_controller.approve_rule", new_callable=AsyncMock) as mock_approve,              patch("Backend.Controller.rules_controller.log_audit_event", new_callable=AsyncMock):

            mock_get.return_value = mock_rule
            mock_approve.return_value = (True, "Rule approved successfully")

            response = self.client.post(
                f"/rules/{rule_id}/approve",
                headers=self.admin_headers,
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("approved successfully", response.json().get("message", ""))

    # ───────────────────────────────────────────────────────────
    # 5. Status Transition Safety Guarantees
    # ───────────────────────────────────────────────────────────
    def test_cannot_approve_rejected_rule(self):
        """A REJECTED rule cannot be approved, preventing accidental activation."""
        rule_id = str(uuid.uuid4())
        mock_rule = {
            "rule_id": rule_id,
            "status": "REJECTED",
            "version": 1,
        }
        with patch("Backend.Controller.rules_controller.get_rule_by_id", new_callable=AsyncMock) as mock_get,              patch("Backend.Controller.rules_controller.approve_rule", new_callable=AsyncMock) as mock_approve:

            mock_get.return_value = mock_rule
            mock_approve.return_value = (False, "Cannot approve a REJECTED rule. Rejected rules cannot become active.")

            response = self.client.post(
                f"/rules/{rule_id}/approve",
                headers=self.admin_headers,
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn("Cannot approve a REJECTED rule", response.json().get("detail", ""))


if __name__ == "__main__":
    unittest.main()
