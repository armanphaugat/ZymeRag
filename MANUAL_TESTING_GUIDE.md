# Comprehensive Manual Testing & Verification Guide
**ZymeRag Axiom Zero-LLM Runtime Enforcement Gateway & Multi-Modal Policy Governance**

---

## 1. System Architecture & Component Overview

ZymeRag is an enterprise-grade AI Action Gateway combining **Multi-Modal Policy Extraction**, a **Deterministic Zero-LLM Fast-Path Policy Engine**, a **Two-Phase Human-in-the-Loop Governance Framework**, and an **Immutable SHA-256 Cryptographic Audit Ledger**.

```mermaid
flowchart TD
    subgraph UI ["Frontend Portal (Port 5173)"]
        U1[Upload & Ingestion]
        U2[Phase 1: Rule Review]
        U3[Phase 2: Escalation Approvals]
        U4[Audit Log & Integrity]
    end

    subgraph GW ["Axiom Gateway (Port 8000)"]
        Auth[JWT & Argon2 Auth]
        Ingest[Multi-Modal Ingestion Engine]
        RAG[FAISS Vector & BM25 Hybrid Search]
        RuleExt[Multi-Rule LLM Extraction]
        FlowReg[Deterministic Flow Registry]
        Eval[Zero-LLM Policy Engine]
        Reval[Pre-Execution Revalidation]
        Audit[SHA-256 Chained Audit Trail]
    end

    subgraph Downstream ["Mock Enterprise Services (Port 8001)"]
        MockPay[Payment Service: /transfer, /refund]
        MockCRM[CRM Service: /customer]
        MockEmail[Email Notification Service]
    end

    UI -->|JWT Bearer Token| GW
    GW -->|X-Gateway-Secret| Downstream
```

### 1.1 Running Services & Port Map

| Component | Technology | Default Port / URL | Health Endpoint |
| :--- | :--- | :--- | :--- |
| **Backend Core & Gateway** | FastAPI, PyTorch, FAISS | `http://localhost:8000` | `GET http://localhost:8000/health` |
| **Mock Downstream API** | FastAPI (Isolated) | `http://localhost:8001` | `GET http://localhost:8001/health` |
| **Frontend Web Portal** | Vite, React 19, Deloitte CSS | `http://localhost:5173` | Browser probe (`http://localhost:5173`) |
| **Relational Database** | PostgreSQL | `localhost:5432` | Standard Postgres connection |

### 1.2 Default Credentials & Security Tokens

| Identifier | Type | Value | Role / Permissions |
| :--- | :--- | :--- | :--- |
| **Officer Account** | Username / Password | `compliance_officer_1` / `SecurePassword123!` | Compliance Lead (Rule approval, Escalation review, Audit verification) |
| **Agent Secret** | Static Bearer Key | `gateway_internal_secret` | Internal Service / Automated Agent API bypass |
| **Downstream Secret** | Header Token | `X-Gateway-Secret: gateway_internal_secret` | Direct call protection for MockServices on port 8001 |

---

## 2. Environment Verification & Startup

Before executing any tests, verify all three core services are online:

```bash
# 1. Check Gateway
curl -s http://localhost:8000/health
# Expected: {"status":"healthy","service":"ZymeRag Axiom Gateway","version":"2.0.0"}

# 2. Check Mock Downstream
curl -s http://localhost:8001/health
# Expected: {"status":"ok","service":"Mock Enterprise Services"}

# 3. Check Frontend UI
curl -s http://localhost:5173 > /dev/null && echo "Frontend: UP" || echo "Frontend: DOWN"
# Expected: Frontend: UP
```

If any service is stopped, start it in a separate terminal:
```bash
# Terminal 1: Backend Gateway
cd "/Users/kushagragupta/Deloitte Capstone/ZymeRag"
./.venv/bin/uvicorn Backend.app:app --port 8000

# Terminal 2: Mock Downstream Services
cd "/Users/kushagragupta/Deloitte Capstone/ZymeRag"
./.venv/bin/uvicorn MockServices.app:app --reload --port 8001

# Terminal 3: Frontend Dev Server
cd "/Users/kushagragupta/Deloitte Capstone/ZymeRag/frontend"
npm run dev -- --port 5173 --host
```

---

## 3. Section A: Authentication & JWT Validation

### TC-01: Public Health Probe (Unauthenticated)
- **Method**: `GET`
- **URL**: `http://localhost:8000/health`
- **Command**:
```bash
curl -i -X GET "http://localhost:8000/health"
```
- **Expected Status**: `200 OK`
- **Expected Response**:
```json
{
  "status": "healthy",
  "service": "ZymeRag Axiom Gateway",
  "version": "2.0.0"
}
```

---

### TC-02: Protected Route Rejection (Missing Token)
- **Method**: `GET`
- **URL**: `http://localhost:8000/rules`
- **Command**:
```bash
curl -i -X GET "http://localhost:8000/rules"
```
- **Expected Status**: `401 Unauthorized`
- **Expected Response**:
```json
{
  "detail": "Unauthorized: Missing Bearer Token"
}
```

---

### TC-03: Protected Route Rejection (Malformed / Expired Token)
- **Method**: `GET`
- **URL**: `http://localhost:8000/rules`
- **Command**:
```bash
curl -i -X GET "http://localhost:8000/rules"   -H "Authorization: Bearer invalid_or_expired_jwt_token"
```
- **Expected Status**: `403 Forbidden`
- **Expected Response**:
```json
{
  "detail": "Forbidden: Invalid or expired token"
}
```

---

### TC-04: Compliance Officer Sign-In (`POST /user/login`)
- **Method**: `POST`
- **URL**: `http://localhost:8000/user/login`
- **Command**:
```bash
curl -i -X POST "http://localhost:8000/user/login"   -H "Content-Type: application/json"   -d '{
    "username": "compliance_officer_1",
    "password": "SecurePassword123!"
  }'
```
- **Expected Status**: `200 OK`
- **Expected Response**:
```json
{
  "message": "Login successful",
  "user_id": "<UUID>",
  "username": "compliance_officer_1",
  "access_token": "<HS256_JWT_TOKEN>",
  "token_type": "bearer"
}
```
> **Tip**: Save the token in a shell variable for subsequent tests:
> ```bash
> export TOKEN=$(curl -s -X POST http://localhost:8000/user/login >   -H "Content-Type: application/json" >   -d '{"username":"compliance_officer_1","password":"SecurePassword123!"}' >   | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
> echo "Acquired Token: ${TOKEN:0:20}..."
> ```

---

### TC-05: User Registration (`POST /user/create_user`)
- **Method**: `POST`
- **URL**: `http://localhost:8000/user/create_user`
- **Command**:
```bash
TEST_USER="test_officer_$(date +%s)"
curl -i -X POST "http://localhost:8000/user/create_user"   -H "Content-Type: application/json"   -d "{
    "username": "$TEST_USER",
    "password": "SecurePass456!"
  }"
```
- **Expected Status**: `200 OK`
- **Expected Response**:
```json
{
  "message": "User created successfully",
  "user_id": "<UUID>",
  "username": "<TEST_USER>"
}
```

---

### TC-06: Frontend Web Portal Sign-In
1. Open browser to **`http://localhost:5173`**.
2. Observe the Deloitte-branded Sign-In screen (Deloitte Navy `#002B49`, Deloitte Green `#86BC25` logo, sharp non-rounded corners).
3. Enter:
   - **Username**: `compliance_officer_1`
   - **Password**: `SecurePassword123!`
4. Click **Sign In**.
5. **Expected Result**: Successfully redirects to the Ingestion Dashboard. Top-left displays `"DELOITTE | ZymeRag Gateway"`. Bottom of the sidebar displays `"compliance_officer_1 (COMPLIANCE)"`.

---

## 4. Section B: Document Ingestion & Multi-Rule Extraction (Component 1)

### TC-07: Policy PDF Ingestion & Semantic Chunking
- **Method**: `POST`
- **URL**: `http://localhost:8000/upload/upload_pdf`
- **Headers**: `Authorization: Bearer $TOKEN`
- **Command**:
```bash
# Upload sample policy PDF
curl -i -X POST "http://localhost:8000/upload/upload_pdf"   -H "Authorization: Bearer $TOKEN"   -F "file=@Testing/northfield_refund_policy.pdf"
```
- **Expected Status**: `200 OK`
- **Expected Response**:
```json
{
  "message": "PDF uploaded and processed successfully",
  "content_id": "<CONTENT_UUID>",
  "filename": "northfield_refund_policy.pdf",
  "chunks_indexed": 8,
  "faiss_status": "synced",
  "bm25_status": "synced"
}
```

---

### TC-08: Multi-Rule Clause Extraction Verification
**Context**: In real enterprise policies, a single clause often defines multiple tiered thresholds. For example, Northfield Section 3.1 states:
> *"Refunds under Rs 2,000 are automatically approved. Refunds between Rs 2,000 and Rs 15,000 require Support Lead sign-off. Refunds exceeding Rs 15,000 require Fraud Team approval."*

Prior engines extracted only 1 rule and discarded tiers. ZymeRag extracts **all distinct rules** into structured records.

- **Command**:
```bash
curl -s "http://localhost:8000/rules?status=DRAFT"   -H "Authorization: Bearer $TOKEN"   | python3 -c '
import sys, json
d = json.load(sys.stdin)
rules = d.get("rules", [])
print(f"Total DRAFT rules: {len(rules)}")
for r in rules[:5]:
    print(f"ID: {r["rule_id"][:8]} | Effect: {r["effect"]} | Scope: {r["scope"]} | Cond: {r["condition"]}")
'
```
- **Expected Result**: Multiple rules are present for the same policy document, covering `ALLOW` (<2,000), `ESCALATE` (2,000-15,000), and `ESCALATE` (>15,000).

---

### TC-09: Hybrid Search Retrieval (Semantic Vector + BM25)
- **Method**: `POST`
- **URL**: `http://localhost:8000/query/semantic`
- **Command**:
```bash
curl -i -X POST "http://localhost:8000/query/semantic"   -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   -d '{
    "query": "What is the refund limit for automatic customer approval?",
    "top_k": 3
  }'
```
- **Expected Status**: `200 OK`
- **Expected Response**: Top 3 ranked chunks containing Section 3.1 threshold text with vector cosine similarity scores.

---

### TC-10: Frontend UI Upload & Document Processing
1. Navigate to **Document Ingestion** in the sidebar (`http://localhost:5173`).
2. Drag and drop `Testing/northfield_refund_policy.pdf` (or any PDF/Text document).
3. Observe live extraction progress:
   - File status card indicates chunking completed.
   - Vector store (FAISS) and lexical store (BM25) indicators turn green.
   - Extracted draft rule count badge increments.

---

## 5. Section C: Phase 1 Human-in-the-Loop — Rule Review & Governance (Component 2)

### TC-11: Retrieve Rules by Status Filter
- **Method**: `GET`
- **URL**: `http://localhost:8000/rules?status=DRAFT`
- **Command**:
```bash
curl -s "http://localhost:8000/rules?status=DRAFT"   -H "Authorization: Bearer $TOKEN"   | python3 -c 'import sys, json; res = json.load(sys.stdin); print(f"Found {res["total"]} draft rules")'
```
- **Expected Status**: `200 OK`

---

### TC-12: Modify Draft Rule Scope / Condition (`PATCH /rules/{rule_id}`)
- **Method**: `PATCH`
- **URL**: `http://localhost:8000/rules/{rule_id}`
- **Command**:
```bash
# Pick first draft rule ID
RULE_ID=$(curl -s "http://localhost:8000/rules?status=DRAFT" -H "Authorization: Bearer $TOKEN" | python3 -c 'import sys,json; print(json.load(sys.stdin)["rules"][0]["rule_id"])')

curl -i -X PATCH "http://localhost:8000/rules/$RULE_ID"   -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   -d '{
    "condition": {"field": "amount", "operator": "<=", "value": 2500},
    "required_approval_role": "senior_compliance_officer"
  }'
```
- **Expected Status**: `200 OK`
- **Expected Response**: `{"message": "Rule updated successfully", "rule": { ... }}`

---

### TC-13: Compliance Officer Approves Draft Rule with Attribution
- **Method**: `POST`
- **URL**: `http://localhost:8000/rules/{rule_id}/approve`
- **Command**:
```bash
curl -i -X POST "http://localhost:8000/rules/$RULE_ID/approve"   -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   -d '{
    "approved_by": "compliance_officer_1"
  }'
```
- **Expected Status**: `200 OK`
- **Expected Response**:
```json
{
  "message": "Rule approved successfully",
  "rule": {
    "rule_id": "<RULE_ID>",
    "status": "APPROVED",
    "version": 2,
    "approved_by": "compliance_officer_1"
  }
}
```
- **Audit Verification**: This approval triggers a `RULE_APPROVED` event in the SHA-256 hash-chained audit ledger attributed to `compliance_officer_1`.

---

### TC-14: Rule Rejection Flow
- **Method**: `POST`
- **URL**: `http://localhost:8000/rules/{rule_id}/reject`
- **Command**:
```bash
# Pick another draft rule
REJECT_RULE_ID=$(curl -s "http://localhost:8000/rules?status=DRAFT" -H "Authorization: Bearer $TOKEN" | python3 -c 'import sys,json; print(json.load(sys.stdin)["rules"][-1]["rule_id"])')

curl -i -X POST "http://localhost:8000/rules/$REJECT_RULE_ID/reject"   -H "Authorization: Bearer $TOKEN"
```
- **Expected Status**: `200 OK`
- **Expected Response**: `{"message": "Rule <ID> rejected successfully"}`

---

### TC-15: Frontend UI Rule Review Portal
1. Navigate to **Rule Governance** (`http://localhost:5173/`).
2. Notice the metric cards at top: `Draft Rules`, `Approved`, `Rejected`.
3. Switch between tabs: **Draft Rules**, **Approved Rules**, **Rejected Rules**.
4. In the **Draft Rules** table:
   - Click a row to view the original source clause citation and JSON condition.
   - Click the green **Approve** button.
   - Observe the toast notification: `"Rule ... approved successfully"`.
   - The rule instantly moves to the **Approved** tab and its version increments.

---

## 6. Section D: Zero-LLM Fast-Path Policy Enforcement (Component 3)

### TC-16: Automated `ALLOW` Execution (Sub-2,000 Refund)
- **Method**: `POST`
- **URL**: `http://localhost:8000/actions/execute`
- **Command**:
```bash
curl -i -X POST "http://localhost:8000/actions/execute"   -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   -d '{
    "action_id": "'$(uuidgen | tr "[:upper:]" "[:lower:]")'",
    "agent_id": "customer_agent_01",
    "user_id": "usr_cust_101",
    "tool": "payment",
    "operation": "issue_refund",
    "resource": "txn_101",
    "arguments": {
      "transaction_id": "txn_101",
      "amount": 1250.0,
      "reason": "Minor defect reported within 24h"
    }
  }'
```
- **Expected Status**: `200 OK`
- **Expected Response**:
```json
{
  "action_id": "<UUID>",
  "status": "success",
  "decision": "ALLOW",
  "executed": true,
  "result": {
    "status": "success",
    "refund_id": "<REFUND_ID>",
    "amount": 1250.0
  },
  "error": null
}
```

---

### TC-17: Automated `ESCALATE` Routing (Between 2,000 and 15,000)
- **Method**: `POST`
- **URL**: `http://localhost:8000/actions/execute`
- **Command**:
```bash
curl -i -X POST "http://localhost:8000/actions/execute"   -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   -d '{
    "action_id": "'$(uuidgen | tr "[:upper:]" "[:lower:]")'",
    "agent_id": "customer_agent_01",
    "user_id": "usr_cust_202",
    "tool": "payment",
    "operation": "issue_refund",
    "resource": "txn_202",
    "arguments": {
      "transaction_id": "txn_202",
      "amount": 6500.0,
      "reason": "Damaged television reported"
    }
  }'
```
- **Expected Status**: `200 OK`
- **Expected Response**:
```json
{
  "action_id": "<UUID>",
  "status": "pending_approval",
  "decision": "ESCALATE",
  "executed": false,
  "approval_id": "<APPROVAL_UUID>",
  "result": {
    "message": "Action requires human review: amount in [2000, 15000]",
    "required_role": "support_lead"
  },
  "error": null
}
```
- **Result**: The action is held in the gateway and queued for human review.

---

### TC-18: Automated `BLOCK` Denial (Policy Disallow / Deny-by-Default)
- **Method**: `POST`
- **URL**: `http://localhost:8000/actions/execute`
- **Command**:
```bash
curl -i -X POST "http://localhost:8000/actions/execute"   -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   -d '{
    "action_id": "'$(uuidgen | tr "[:upper:]" "[:lower:]")'",
    "agent_id": "malicious_bot_09",
    "user_id": "usr_rogue_303",
    "tool": "crm",
    "operation": "delete_customer",
    "resource": "cust_all",
    "arguments": {
      "customer_id": "cust_all"
    }
  }'
```
- **Expected Status**: `200 OK`
- **Expected Response**:
```json
{
  "action_id": "<UUID>",
  "status": "blocked",
  "decision": "BLOCK",
  "executed": false,
  "error": "No matching active policy permits this action (Deny-by-Default)"
}
```

---

### TC-19: Idempotency & Replay Protection (`X-Idempotency-Key`)
- **Method**: `POST`
- **URL**: `http://localhost:8000/actions/execute`
- **Header**: `X-Idempotency-Key: test-idempotency-key-001`
- **Command**:
```bash
KEY="test-idempotency-key-$(date +%s)"

# 1st Execution
curl -s -X POST "http://localhost:8000/actions/execute"   -H "Authorization: Bearer $TOKEN"   -H "X-Idempotency-Key: $KEY"   -H "Content-Type: application/json"   -d '{
    "action_id": "'$(uuidgen | tr "[:upper:]" "[:lower:]")'",
    "agent_id": "billing_agent",
    "user_id": "usr_cust_404",
    "tool": "payment",
    "operation": "issue_refund",
    "resource": "txn_404",
    "arguments": {"transaction_id": "txn_404", "amount": 500.0}
  }'

# 2nd Execution with same key
curl -s -X POST "http://localhost:8000/actions/execute"   -H "Authorization: Bearer $TOKEN"   -H "X-Idempotency-Key: $KEY"   -H "Content-Type: application/json"   -d '{
    "action_id": "'$(uuidgen | tr "[:upper:]" "[:lower:]")'",
    "agent_id": "billing_agent",
    "user_id": "usr_cust_404",
    "tool": "payment",
    "operation": "issue_refund",
    "resource": "txn_404",
    "arguments": {"transaction_id": "txn_404", "amount": 500.0}
  }'
```
- **Expected Result**: The second request returns the cached result without re-executing downstream payment transfer, preventing double refund transactions.

---

### TC-20: Direct Downstream Bypass Prevention
Attempt to call the Mock Payment Service directly on port 8001 without the gateway secret:
- **Command**:
```bash
curl -i -X POST "http://localhost:8001/payment/transfer"   -H "Content-Type: application/json"   -d '{
    "account_id": "acc_001",
    "recipient": "acc_999",
    "amount": 99999.0
  }'
```
- **Expected Status**: `401 Unauthorized`
- **Expected Response Body**: `{"detail": "Direct bypass rejected. Must route through Axiom Gateway"}`

---

## 7. Section E: Phase 2 Human-in-the-Loop — Escalation Approvals (Component 4)

### TC-21: Retrieve Pending Escalation Approvals
- **Method**: `GET`
- **URL**: `http://localhost:8000/actions/approvals`
- **Command**:
```bash
curl -s "http://localhost:8000/actions/approvals"   -H "Authorization: Bearer $TOKEN"   | python3 -c '
import sys, json
data = json.load(sys.stdin)
apps = data.get("approvals", [])
print(f"Total pending approvals: {len(apps)}")
for a in apps[:3]:
    print(f"Approval ID: {a["approval_id"]} | Status: {a["status"]} | Role: {a["required_role"]}")
'
```
- **Expected Status**: `200 OK`

---

### TC-22: Human Reviews & Approves Escalation with Pre-Execution Revalidation
**Workflow**: When human approves, the Gateway:
1. Re-validates the tool action against current active rules to ensure policy has not drifted.
2. Updates approval record with reviewer username (`compliance_officer_1`).
3. Dispatches the action downstream.
4. Records the human approval in the hash-chained audit log with `decision: "APPROVED"`.

- **Command**:
```bash
# 1. Trigger an escalation to ensure an item is queued
APP_ID=$(curl -s -X POST "http://localhost:8000/actions/execute"   -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   -d '{
    "action_id": "'$(uuidgen | tr "[:upper:]" "[:lower:]")'",
    "agent_id": "agent_alpha",
    "user_id": "usr_555",
    "tool": "payment",
    "operation": "issue_refund",
    "resource": "txn_555",
    "arguments": {"transaction_id": "txn_555", "amount": 8000.0}
  }' | python3 -c 'import sys,json; print(json.load(sys.stdin)["approval_id"])')

echo "Generated Approval ID: $APP_ID"

# 2. Officer approves the action
curl -i -X POST "http://localhost:8000/actions/approvals/$APP_ID/decision"   -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   -d '{
    "decision": "APPROVED",
    "decided_by": "compliance_officer_1",
    "reason": "Verified police report for stolen package"
  }'
```
- **Expected Status**: `200 OK`
- **Expected Response**:
```json
{
  "message": "Action re-validated, approved, and executed successfully",
  "status": "APPROVED",
  "execution": {
    "action_id": "<UUID>",
    "status": "success",
    "decision": "ALLOW",
    "executed": true,
    "result": { ... }
  }
}
```

---

### TC-23: Human Rejects Escalation
- **Command**:
```bash
# 1. Create escalation
APP_ID_REJ=$(curl -s -X POST "http://localhost:8000/actions/execute"   -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   -d '{
    "action_id": "'$(uuidgen | tr "[:upper:]" "[:lower:]")'",
    "agent_id": "agent_alpha",
    "user_id": "usr_666",
    "tool": "payment",
    "operation": "issue_refund",
    "resource": "txn_666",
    "arguments": {"transaction_id": "txn_666", "amount": 12000.0}
  }' | python3 -c 'import sys,json; print(json.load(sys.stdin)["approval_id"])')

# 2. Officer rejects action
curl -i -X POST "http://localhost:8000/actions/approvals/$APP_ID_REJ/decision"   -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   -d '{
    "decision": "REJECTED",
    "decided_by": "compliance_officer_1",
    "reason": "Receipt was found to be fraudulent"
  }'
```
- **Expected Status**: `200 OK`
- **Expected Response**: `{"message": "Action successfully rejected by reviewer", "status": "REJECTED"}`

---

### TC-24: Frontend UI Escalation Approvals Management
1. In the sidebar, click **Escalation Approvals** (`http://localhost:5173`).
2. Observe the **Pending Approvals Queue**:
   - Each card details the requesting Agent, Tool Operation, Requested Arguments, and Policy Reason.
   - Enter a review note in the text box (e.g. `"Approved per manager confirmation"`).
   - Click **Approve Action**.
3. **Expected UI Behavior**:
   - Card displays confirmation and smoothly transitions out of pending queue.
   - Bottom **Resolved History** table updates immediately with `APPROVED` status, showing reviewer `compliance_officer_1` and your note.

---

## 8. Section F: Immutable SHA-256 Audit Trail & Provenance (Component 5)

### TC-25: Retrieve Audit Trail with User Attribution
- **Method**: `GET`
- **URL**: `http://localhost:8000/actions/audit?limit=10`
- **Command**:
```bash
curl -s "http://localhost:8000/actions/audit?limit=10"   -H "Authorization: Bearer $TOKEN"   | python3 -c '
import sys, json
data = json.load(sys.stdin)
events = data.get("events", [])
print(f"Displaying {len(events)} audit events:")
print("-" * 80)
for e in events[:5]:
    details = e.get("details")
    if isinstance(details, str): details = json.loads(details)
    actor = details.get("decided_by") or e.get("user_id") or "System"
    print(f"Decision: {e.get("decision"):<12} | Actor: {actor:<20} | Tool: {e.get("tool"):<10} | Hash: {e.get("curr_hash")[:16]}...")
'
```
- **Expected Result**: Every decision (ALLOW, BLOCK, ESCALATE, APPROVED, REJECTED, EXECUTED) is listed with its actor, timestamp, and SHA-256 hash.

---

### TC-26: Cryptographic Chain Integrity Verification
- **Method**: `GET`
- **URL**: `http://localhost:8000/actions/audit/verify`
- **Command**:
```bash
curl -i -X GET "http://localhost:8000/actions/audit/verify"   -H "Authorization: Bearer $TOKEN"
```
- **Expected Status**: `200 OK`
- **Expected Response**:
```json
{
  "status": "TAMPER_FREE",
  "is_valid": true,
  "chain_issues": []
}
```

---

### TC-27: Tamper Detection Demonstration
**Objective**: Prove that manual SQL manipulation of an audit record is immediately detected by the cryptographic verification algorithm.

```bash
# 1. Tamper with a single decision in the database
PYTHONPATH=. ./.venv/bin/python -c "
import asyncio
from Dbhelper.db import AsyncDB
from sqlalchemy import text

async def tamper():
    async with AsyncDB() as s:
        await s.execute(text("UPDATE audit_events SET decision = 'ALLOW' WHERE decision = 'BLOCK' LIMIT 1"))
        await s.commit()
    print('Simulated malicious database modification!')
asyncio.run(tamper())
"

# 2. Run verification API
curl -s "http://localhost:8000/actions/audit/verify" -H "Authorization: Bearer $TOKEN"
```
- **Expected Response**:
```json
{
  "status": "TAMPER_DETECTED",
  "is_valid": false,
  "chain_issues": [
    "Hash mismatch at event <UUID>: recomputed ... != recorded ..."
  ]
}
```

> **Clean-Up / Auto-Repair**: Restore canonical cryptographic chain validity:
> ```bash
> PYTHONPATH=. ./.venv/bin/python scratch/repair_audit.py
> ```
> Verify it returns: `{"status": "TAMPER_FREE", "is_valid": true, "chain_issues": []}`.

---

### TC-28: Frontend UI Audit Explorer & Provenance Modal
1. Navigate to **Audit Logs** in the sidebar (`http://localhost:5173`).
2. Verify:
   - **Metric counters**: Total Events, Allowed/Executed, Blocked/Rejected, Escalated, Human Approvals.
   - **Actor Column**: Clearly displays human usernames (with green Deloitte indicator) vs system/agent identifiers.
   - **Filter Bar**: Test filtering by `Decision Type` (e.g. select `Human Approved` or `Block`).
3. Click the **Verify Chain Integrity** button:
   - Banner displays: `"Chain integrity: TAMPER_FREE"`.
4. Click on any table row:
   - Pop-up modal displays full, syntax-highlighted cryptographic provenance payload (`event_id`, `prev_hash`, `curr_hash`, `details`, `matched_rule_id`).

---

## 9. Comprehensive Test Execution Matrix

| Test ID | Area | Endpoint / Action | Input Condition | Expected Status & Result |
| :--- | :--- | :--- | :--- | :--- |
| **TC-01** | System | `GET /health` | Unauthenticated probe | `200 OK`, `healthy` |
| **TC-02** | Auth | `GET /rules` | Missing Bearer token | `401 Unauthorized` |
| **TC-03** | Auth | `GET /rules` | Invalid / expired JWT | `403 Forbidden` |
| **TC-04** | Auth | `POST /user/login` | Valid credentials | `200 OK`, Returns JWT Bearer token |
| **TC-05** | Auth | `POST /user/create_user` | New username / password | `200 OK`, Returns user ID |
| **TC-06** | UI | Browser `/` | Login form submit | Redirects to Ingestion, stores session |
| **TC-07** | Ingestion | `POST /upload/upload_pdf` | Policy PDF file | `200 OK`, FAISS & BM25 synced |
| **TC-08** | Ingestion | `GET /rules?status=DRAFT` | Multi-tier policy clause | Multiple distinct rules extracted |
| **TC-09** | RAG | `POST /query/semantic` | Policy natural query | `200 OK`, Returns top cosine chunks |
| **TC-10** | RAG | `POST /query/bm25` | Keyword search query | `200 OK`, Returns ranked lexical matches |
| **TC-11** | UI | Ingestion Page | File drag & drop | Live chunking & indexing metrics |
| **TC-12** | Governance | `GET /rules?status=DRAFT` | Filter by status | `200 OK`, Returns list of draft rules |
| **TC-13** | Governance | `PATCH /rules/{id}` | Update condition / role | `200 OK`, Scope & conditions updated |
| **TC-14** | Governance | `POST /rules/{id}/approve` | Reviewer approval | `200 OK`, Status -> APPROVED, Version +1 |
| **TC-15** | Governance | `POST /rules/{id}/reject` | Reviewer rejection | `200 OK`, Status -> REJECTED |
| **TC-16** | UI | Rule Review Page | Approve button click | Toast confirmation, moves to Approved |
| **TC-17** | Engine | `POST /actions/execute` | Refund < 2,000 | `200 OK`, `ALLOW` -> Executed |
| **TC-18** | Engine | `POST /actions/execute` | Refund 2,000 - 15,000 | `200 OK`, `ESCALATE` -> Queue created |
| **TC-19** | Engine | `POST /actions/execute` | Unauthorized operation | `200 OK`, `BLOCK` -> Deny-by-default |
| **TC-20** | Security | `POST /actions/execute` | Same `X-Idempotency-Key` | Returns cached result without replay |
| **TC-21** | Security | `POST :8001/payment/...` | Direct call without header | `401 Unauthorized` Direct bypass blocked |
| **TC-22** | Human-in-Loop | `GET /actions/approvals` | List pending queue | `200 OK`, Returns pending items |
| **TC-23** | Human-in-Loop | `POST /actions/approvals/{id}/decision` | Decision = APPROVED | Re-evaluates -> Executed -> Logged |
| **TC-24** | Human-in-Loop | `POST /actions/approvals/{id}/decision` | Decision = REJECTED | `200 OK`, Rejected in audit log |
| **TC-25** | Audit | `GET /actions/audit` | Retrieve log entries | `200 OK`, Shows human actor attribution |
| **TC-26** | Audit | `GET /actions/audit/verify` | Cryptographic check | `200 OK`, `TAMPER_FREE`, `is_valid: true` |
| **TC-27** | Audit | Database SQL tamper | Modified DB record | `200 OK`, `TAMPER_DETECTED`, `is_valid: false` |
| **TC-28** | UI | Audit Logs Page | Click row & verify button | Shows modal with hash provenance |

---

## 10. Evaluator Sign-Off Checklist

```markdown
[ ] 1. All three services run on respective ports (8000, 8001, 5173).
[ ] 2. Authentication requires Argon2-hashed credentials and HS256 JWT tokens.
[ ] 3. Multi-tier policy extraction extracts multiple rules per clause (no tier dropping).
[ ] 4. Zero-LLM Fast-Path Gateway deterministically outputs ALLOW, BLOCK, ESCALATE.
[ ] 5. Direct downstream access to port 8001 is denied without Gateway credentials.
[ ] 6. Escalations enter pending queue and require human reviewer sign-off.
[ ] 7. Approvals re-validate active policy state before downstream dispatch.
[ ] 8. Human reviewer identity is explicitly attributed in the audit ledger.
[ ] 9. SHA-256 cryptographic chain integrity validates as TAMPER_FREE.
[ ] 10. Unauthorized database edits are detected by the audit integrity verifier.
[ ] 11. Frontend UI adheres to Deloitte brand guidelines with zero rounded corners.
```