import os
from typing import Dict, Any, Optional
from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel

app = FastAPI(title="Mock Enterprise Services", description="Isolated CRM, Payment, and Email Services", version="1.0.0")

GATEWAY_SECRET = os.getenv("GATEWAY_INTERNAL_SECRET", "gateway_internal_secret")


def verify_gateway_auth(x_gateway_secret: Optional[str] = Header(None)):
    """Enforces that only calls originating from the AI Action Gateway are accepted."""
    if not x_gateway_secret or x_gateway_secret != GATEWAY_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Direct bypass attempt blocked: Only calls with valid Gateway credentials are accepted."
        )


class PaymentTransferRequest(BaseModel):
    account_id: str
    recipient: str
    amount: float
    currency: str = "USD"
    note: Optional[str] = None


class PaymentRefundRequest(BaseModel):
    transaction_id: str
    amount: float
    reason: Optional[str] = None


class CustomerUpdateRequest(BaseModel):
    customer_id: str
    email: Optional[str] = None
    status: Optional[str] = None
    tier: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SendEmailRequest(BaseModel):
    recipient: str
    subject: str
    body: str


# --- Health check ---
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Mock Enterprise Services"}


# --- CRM Endpoints ---
@app.get("/crm/customer/{customer_id}")
def get_customer(customer_id: str, x_gateway_secret: Optional[str] = Header(None)):
    verify_gateway_auth(x_gateway_secret)
    return {
        "customer_id": customer_id,
        "name": f"Customer {customer_id}",
        "email": f"customer_{customer_id}@example.com",
        "tier": "enterprise",
        "status": "active",
    }


@app.put("/crm/customer/{customer_id}")
def update_customer(customer_id: str, payload: CustomerUpdateRequest, x_gateway_secret: Optional[str] = Header(None)):
    verify_gateway_auth(x_gateway_secret)
    return {
        "status": "success",
        "customer_id": customer_id,
        "updated_fields": payload.model_dump(exclude_none=True),
        "message": f"Customer {customer_id} updated successfully in CRM.",
    }


@app.delete("/crm/customer/{customer_id}")
def delete_customer(customer_id: str, x_gateway_secret: Optional[str] = Header(None)):
    verify_gateway_auth(x_gateway_secret)
    return {
        "status": "success",
        "customer_id": customer_id,
        "message": f"Customer {customer_id} successfully deleted from CRM.",
    }


# --- Payment Endpoints ---
@app.post("/payment/transfer")
def transfer_funds(payload: PaymentTransferRequest, x_gateway_secret: Optional[str] = Header(None)):
    verify_gateway_auth(x_gateway_secret)
    return {
        "status": "success",
        "transaction_id": f"txn_{payload.account_id[:6]}_{int(payload.amount)}",
        "amount": payload.amount,
        "currency": payload.currency,
        "recipient": payload.recipient,
        "message": f"Transferred {payload.amount} {payload.currency} to {payload.recipient}.",
    }


@app.post("/payment/refund")
def refund_payment(payload: PaymentRefundRequest, x_gateway_secret: Optional[str] = Header(None)):
    verify_gateway_auth(x_gateway_secret)
    return {
        "status": "success",
        "refund_id": f"ref_{payload.transaction_id}",
        "amount": payload.amount,
        "message": f"Refund of {payload.amount} processed for {payload.transaction_id}.",
    }


# --- Email Endpoints ---
@app.post("/email/send")
def send_email(payload: SendEmailRequest, x_gateway_secret: Optional[str] = Header(None)):
    verify_gateway_auth(x_gateway_secret)
    return {
        "status": "success",
        "recipient": payload.recipient,
        "subject": payload.subject,
        "message": f"Email successfully dispatched to {payload.recipient}.",
    }
