# Test Fixtures

This directory contains sample financial data files used exclusively for testing the reconciliation and accounting pipelines.

> [!CAUTION]
> **These files must never contain real financial data.** Only sanitized/anonymized dummy data should be committed here.

## Files

| File | Purpose |
|---|---|
| `bank_statement.csv` | Sample bank transaction ledger for reconciliation tests |
| `transactions.csv` | Sample transaction log for accounting pipeline tests |
| `quickbooks_export.csv` | Sample QuickBooks Online export for QBO reconciler tests |

## Generating Fresh Fixtures

```bash
python scripts/generate_fixtures.py
```
