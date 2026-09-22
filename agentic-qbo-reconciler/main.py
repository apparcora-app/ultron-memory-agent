import os
import csv
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

# Mock QuickBooks data (in a real implementation this would be fetched via QuickBooks API)
MOCK_QBO_TRANSACTIONS = [
    {"id": "qb1", "date": "2024-09-01", "amount": -150.00, "description": "Office Supplies"},
    {"id": "qb2", "date": "2024-09-02", "amount": 2000.00, "description": "Client Payment"},
    {"id": "qb3", "date": "2024-09-03", "amount": -75.50, "description": "Utility Bill"},
    # Add more mock entries as needed
]

# Simple LLM mock – in a real POC you would call an LLM (e.g., OpenAI, Claude) to perform fuzzy matching.
def mock_llm_match(bank_tx: Dict[str, Any], qbo_txs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return the best matching QBO transaction for a bank transaction.
    Matching criteria: same amount (within $0.01 tolerance) and date proximity (±1 day).
    """
    from datetime import datetime, timedelta
    bank_date = datetime.strptime(bank_tx["date"], "%Y-%m-%d")
    best_match = None
    for q in qbo_txs:
        q_date = datetime.strptime(q["date"], "%Y-%m-%d")
        if abs((bank_date - q_date).days) <= 1 and abs(bank_tx["amount"] - q["amount"]) < 0.01:
            best_match = q
            break
    return best_match

class ReconciliationResult(BaseModel):
    bank_transaction: Dict[str, Any]
    qbo_match: Dict[str, Any] | None
    status: str

app = FastAPI(title="Agentic QBO Reconciler (Proof of Concept)")

@app.post("/reconcile", response_model=List[ReconciliationResult])
async def reconcile(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")
    content = await file.read()
    # Parse CSV – expecting columns: date, amount, description
    try:
        decoded = content.decode('utf-8').splitlines()
        reader = csv.DictReader(decoded)
        bank_transactions = []
        for row in reader:
            # Normalize fields
            bank_tx = {
                "date": row["date"].strip(),
                "amount": float(row["amount"].replace(',', '')),
                "description": row.get("description", "").strip()
            }
            bank_transactions.append(bank_tx)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV parsing error: {e}")

    results: List[ReconciliationResult] = []
    for bt in bank_transactions:
        match = mock_llm_match(bt, MOCK_QBO_TRANSACTIONS)
        status = "matched" if match else "unmatched"
        results.append(ReconciliationResult(bank_transaction=bt, qbo_match=match, status=status))
    return results

# Endpoint to fetch mock QBO data (for debugging / demo purposes)
@app.get("/qbo-mock", response_model=List[Dict[str, Any]])
async def get_qbo_mock():
    return MOCK_QBO_TRANSACTIONS
