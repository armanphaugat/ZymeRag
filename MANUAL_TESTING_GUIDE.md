# Axiom Gateway — Comprehensive End-to-End Manual Testing Guide

This guide walks you through **every step** of manually testing the Axiom Gateway from scratch—from starting the servers to testing policy extraction, runtime enforcement, human approvals, audit hash validation, and direct-bypass protection.

---

## 1. Prerequisites & Environment Setup

### 1.1 Activate Virtual Environment
Open a terminal in the project root:
```bash
cd "/Users/kushagragupta/Deloitte Capstone/ZymeRag"
source .venv/bin/activate
```

### 1.2 Configure `.env`
Ensure you have a `.env` file in the project root containing your database and API credentials:
```env
# Supabase / PostgreSQL Connection String
DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres"

# Groq API Key for Offline Rule Extraction
GROQ_API_KEY="gsk_your_groq_api_key_here"

# JWT Secret & Gateway Internal Secret
ACCESS_TOKEN_SECRET="dev_secret_key_change_in_production"
GATEWAY_API_KEY="gateway_internal_secret"
GATEWAY_SECRET="super_secret_gateway_key_123"

# Mock Services URL
MOCK_SERVICE_URL="http://localhost:8001"
```

### 1.3 Initialize Database Schema & Seed Flows
Run the database initialization script to apply all DDL statements and seed standard flow registry mappings:
```bash
python -m Dbhelper.init_gateway_schema
```
**Expected Output:**
```
Applying 10 schema statements to Supabase/Postgres...
Schema tables successfully initialized.
Seeding initial flow_registry entries...
Default flow registry seeded successfully.
```

---

## 2. Starting the Servers

Open **two separate terminal tabs** (with `source .venv/bin/activate` in both):

### Terminal 1: Start Axiom Gateway API (Port 8000)
```bash
uvicorn Backend.app:app --reload --port 8000
```
- Interactive Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)

### Terminal 2: Start Mock Downstream Services (Port 8001)
```bash
uvicorn MockServices.app:app --reload --port 8001
```
- Mock Services Swagger UI: [http://localhost:8001/docs](http://localhost:8001/docs)

---

## 3. End-to-End Testing Workflow

All tests below use `curl`. You can run them in a third terminal tab or execute them via the Swagger UI.

---

### Step 1: Health & Authentication Check

#### 1.1 Public Health Check (No Auth Required)
```bash
curl -X GET "http://localhost:8000/health"
```
**Expected Response (HTTP 200):**
```json
{
  "status": "healthy",
  "service": "Axiom Gateway",
  "version": "2.0.0"
}
```

#### 1.2 Unauthenticated Request Rejection
Try accessing a protected endpoint without an Authorization header:
```bash
curl -X GET "http://localhost:8000/rules"
```
**Expected Response (HTTP 401):**
```json
{
  "detail": "Unauthorized: Missing Bearer Token"
}
```

---

### Step 2: Policy Ingestion & Automated Rule Extraction

Upload a policy PDF document (e.g. `Refund_Policy.pdf`).

```bash
curl -X POST "http://localhost:8000/upload/pdf" \
  -H "Authorization: Bearer gateway_internal_secret" \
  -F "file=@/path/to/your/policy.pdf" \
  -F "name=ECommerce_Refund_Policy"
```
**Expected Response (HTTP 200):**
```json
{
  "message": "PDF uploaded successfully",
  "id": "e4a2b1c3-1234-5678-9abc-def012345678"
}
```
> [!NOTE]
> In the background, the Gateway splits the policy into chunks, saves them in `policy_chunks`, and prompts Groq LLM to extract structured `DRAFT` rules.

---

### Step 3: Review & Approve Extracted Policy Rules

#### 3.1 List Extracted Draft Rules
```bash
curl -X GET "http://localhost:8000/rules?status=DRAFT" \
  -H "Authorization: Bearer gateway_internal_secret"
```
**Expected Response (HTTP 200):**
```json
[
  {
    "rule_id": "8f3b2a1c-9988-7766-5544-33221100aabb",
    "version": 1,
    "scope": {"tool": "payment", "operation": "refund_payment"},
    "condition": {"field": "amount", "operator": "<=", "value": 50},
    "effect": "ALLOW",
    "status": "DRAFT",
    "source_clause": "Refunds up to $50 can be automatically processed."
  },
  {
    "rule_id": "9a4c3b2d-1122-3344-5566-778899aabbcc",
    "version": 1,
    "scope": {"tool": "payment", "operation": "refund_payment"},
    "condition": {"field": "amount", "operator": ">", "value": 500},
    "effect": "BLOCK",
    "status": "DRAFT",
    "source_clause": "Refunds exceeding $500 are strictly prohibited."
  },
  {
    "rule_id": "7b2a1c0d-4455-6677-8899-aabbccddeeff",
    "version": 1,
    "scope": {"tool": "payment", "operation": "refund_payment"},
    "condition": {"field": "amount", "operator": ">", "value": 50},
    "effect": "ESCALATE",
    "required_approval_role": "finance_manager",
    "status": "DRAFT",
    "source_clause": "Refunds between $50 and $500 require finance manager approval."
  }
]
```

#### 3.2 Approve the Rules for Runtime Enforcement
Approve each rule so the Gateway activates it:
```bash
# Approve Rule 1 (ALLOW <= 50)
curl -X POST "http://localhost:8000/rules/8f3b2a1c-9988-7766-5544-33221100aabb/approve" \
  -H "Authorization: Bearer gateway_internal_secret" \
  -H "Content-Type: application/json" \
  -d '{"approved_by": "admin_alice"}'

# Approve Rule 2 (BLOCK > 500)
curl -X POST "http://localhost:8000/rules/9a4c3b2d-1122-3344-5566-778899aabbcc/approve" \
  -H "Authorization: Bearer gateway_internal_secret" \
  -H "Content-Type: application/json" \
  -d '{"approved_by": "admin_alice"}'

# Approve Rule 3 (ESCALATE > 50)
curl -X POST "http://localhost:8000/rules/7b2a1c0d-4455-6677-8899-aabbccddeeff/approve" \
  -H "Authorization: Bearer gateway_internal_secret" \
  -H "Content-Type: application/json" \
  -d '{"approved_by": "admin_alice"}'
```

---

### Step 4: Runtime Enforcement — Test `ALLOW` Flow

An agent requests a refund of **$30** (matches Rule 1: `<= 50` $\rightarrow$ `ALLOW`).

```bash
curl -X POST "http://localhost:8000/actions/execute" \
  -H "Authorization: Bearer gateway_internal_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "customer_support_bot_1",
    "intent": "refund order 1001 for customer",
    "tool": "payment",
    "operation": "refund_payment",
    "arguments": {
      "order_id": "ORD-1001",
      "amount": 30.00,
      "reason": "Damaged goods"
    }
  }'
```

**Expected Response (HTTP 200):**
```json
{
  "action_id": "...",
  "decision": "ALLOW",
  "status": "EXECUTED",
  "execution_result": {
    "status": "success",
    "message": "Refund of $30.0 processed for order ORD-1001",
    "refund_id": "REF-..."
  }
}
```

---

### Step 5: Runtime Enforcement — Test `BLOCK` Flow

An agent requests a refund of **$600** (matches Rule 2: `> 500` $\rightarrow$ `BLOCK`).

```bash
curl -X POST "http://localhost:8000/actions/execute" \
  -H "Authorization: Bearer gateway_internal_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "customer_support_bot_1",
    "intent": "refund order 1002 for customer",
    "tool": "payment",
    "operation": "refund_payment",
    "arguments": {
      "order_id": "ORD-1002",
      "amount": 600.00,
      "reason": "Special exception request"
    }
  }'
```

**Expected Response (HTTP 200):**
```json
{
  "action_id": "...",
  "decision": "BLOCK",
  "status": "BLOCKED",
  "matched_rule_id": "9a4c3b2d-1122-3344-5566-778899aabbcc",
  "reason": "Violates hard policy constraint: amount > 500"
}
```

---

### Step 6: Runtime Enforcement — Test `ESCALATE` Flow

An agent requests a refund of **$200** (matches Rule 3: `> 50` $\rightarrow$ `ESCALATE`).

```bash
curl -X POST "http://localhost:8000/actions/execute" \
  -H "Authorization: Bearer gateway_internal_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "customer_support_bot_1",
    "intent": "refund order 1003 for customer",
    "tool": "payment",
    "operation": "refund_payment",
    "arguments": {
      "order_id": "ORD-1003",
      "amount": 200.00,
      "reason": "Late delivery complaint"
    }
  }'
```

**Expected Response (HTTP 200):**
```json
{
  "action_id": "3c5d7e9f-...",
  "decision": "ESCALATE",
  "status": "PENDING_APPROVAL",
  "approval_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "required_role": "finance_manager",
  "message": "Action requires human authorization from finance_manager"
}
```

---

### Step 7: Human Approval & Pre-Execution Revalidation

#### 7.1 View Pending Approvals
```bash
curl -X GET "http://localhost:8000/actions/approvals/pending" \
  -H "Authorization: Bearer gateway_internal_secret"
```

#### 7.2 Human Manager Approves the Action
```bash
curl -X POST "http://localhost:8000/actions/approvals/a1b2c3d4-e5f6-7890-abcd-ef1234567890/decide" \
  -H "Authorization: Bearer gateway_internal_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "APPROVED",
    "decided_by": "manager_bob"
  }'
```

**Expected Response (HTTP 200):**
```json
{
  "approval_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "decision": "APPROVED",
  "revalidation_passed": true,
  "execution_result": {
    "status": "success",
    "message": "Refund of $200.0 processed for order ORD-1003",
    "refund_id": "REF-..."
  }
}
```
> [!IMPORTANT]
> The Gateway **automatically revalidated** the active policy rules before dispatching the execution call to guarantee the policy had not changed to `BLOCK` during the review window.

---

### Step 8: Cryptographic Audit Trail Verification

Verify that the SHA-256 hash chain of all logged actions is intact and untampered:

```bash
curl -X GET "http://localhost:8000/actions/audit/verify" \
  -H "Authorization: Bearer gateway_internal_secret"
```

**Expected Response (HTTP 200):**
```json
{
  "verified": true,
  "total_events": 4,
  "tampered_events": 0,
  "status": "Audit chain intact. Zero tampering detected."
}
```

---

### Step 9: Testing Direct Bypass Prevention

To prove that untrusted agents cannot bypass Axiom Gateway and call internal APIs directly:

Try calling the Mock Payment Service directly on port `8001` without the `X-Gateway-Secret`:
```bash
curl -X POST "http://localhost:8001/mock/payment/refund" \
  -H "Content-Type: application/json" \
  -d '{"order_id": "ORD-9999", "amount": 1000.00}'
```

**Expected Response (HTTP 401 Unauthorized):**
```json
{
  "detail": "Unauthorized: Direct access forbidden. Must route through Axiom Gateway."
}
```

Now send the internal secret to verify downstream availability:
```bash
curl -X POST "http://localhost:8001/mock/payment/refund" \
  -H "X-Gateway-Secret: super_secret_gateway_key_123" \
  -H "Content-Type: application/json" \
  -d '{"order_id": "ORD-9999", "amount": 1000.00}'
```

**Expected Response (HTTP 200 OK):**
```json
{
  "status": "success",
  "message": "Refund of $1000.0 processed for order ORD-9999",
  "refund_id": "REF-..."
}
```

---

### Step 10: Idempotency Verification

Re-send the exact same request from **Step 4** including an `idempotency_key`:

```bash
curl -X POST "http://localhost:8000/actions/execute" \
  -H "Authorization: Bearer gateway_internal_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "idemp-refund-ord1001-attempt-1",
    "agent_id": "customer_support_bot_1",
    "intent": "refund order 1001",
    "tool": "payment",
    "operation": "refund_payment",
    "arguments": {
      "order_id": "ORD-1001",
      "amount": 30.00
    }
  }'
```
- First attempt $\rightarrow$ Executes action and caches result.
- Second attempt $\rightarrow$ Returns `"status": "DUPLICATE_REQUEST"` with the previously recorded `result_id` without re-executing against downstream services.

---

## 4. Manual Testing Checklist Summary

| Test Case | Scenario | Expected Decision |
|---|---|---|
| **TC-01** | `/health` check | HTTP 200 (Public) |
| **TC-02** | No auth header | HTTP 401 (Unauthorized) |
| **TC-03** | PDF policy upload | HTTP 200 + Background extraction |
| **TC-04** | Approve rule | Rule status changes from `DRAFT` to `APPROVED` |
| **TC-05** | Low amount ($30) | `ALLOW` $\rightarrow$ Executed |
| **TC-06** | Excessive amount ($600) | `BLOCK` $\rightarrow$ Rejected |
| **TC-07** | Medium amount ($200) | `ESCALATE` $\rightarrow$ Pending Approval |
| **TC-08** | Human approval decision | Pre-revalidation check $\rightarrow$ Executed |
| **TC-09** | Audit log integrity check | `verified: true`, `tampered_events: 0` |
| **TC-10** | Direct mock service call | HTTP 401 (Bypass prevented) |
