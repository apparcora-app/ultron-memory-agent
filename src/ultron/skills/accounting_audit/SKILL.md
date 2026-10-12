---
name: Forensic Accounting & Audit Protocol
description: Deep double-entry bookkeeping reconciliation, invoice verification, GAAP compliance, and tax anomaly detection.
category: Accounting
icon: 📑
tags: [accounting, audit, invoice, tax, gaap, bookkeeping, reconciliation, quickbooks, xero]
version: 1.4
updated_at: 2026-09-03
---
# Forensic Accounting & Audit Protocol

## Operational Capabilities
When the user presents accounting ledgers, receipts, invoices, or financial records:
1. **Double-Entry Verification**: Ensure Debits equal Credits across all asset, liability, equity, revenue, and expense accounts.
2. **Invoice Forensic Audit**: Validate line items, tax computations (Sales Tax/VAT/GST), payment terms, vendor details, and flag duplicate billings.
3. **Reconciliation Analysis**: Compare bank statements against ledger entries to pinpoint unrecorded transactions, timing differences, or variance anomalies.
4. **GAAP & Tax Categorization**: Classify expenses into deductible business buckets according to GAAP/IFRS standards to maximize tax efficiency.
5. **Output Structure**: Always provide clear debit/credit tables, variance analysis summaries, and risk flags in concise tabular markdown format.

## 🧬 Evolution v1.1 — Multi-Source Ledger Reconciliation Discrepancy (2026-09-03)
* **Trigger Analysis**: The agent lacked a systematic multi-source data ingestion and variance-tracing protocol to isolate unexplained closing balances across disparate financial platforms.
- **Rule**: Map all incoming data sources (QBO, Cash App, Billing, Control sheets) to a unified ledger schema before performing variance analysis.
- **Rule**: Trace specific isolated residuals (e.g., QBO closing balance anomalies) by performing incremental subset sums and cross-referencing transaction IDs across all available sheets.
```
Reconciliation steps: 1. Extract QBO closing balance. 2. Compare against aggregated Cash App and Billing logs. 3. Isolate delta into a variance investigation table.
```

## 🧬 Evolution v1.2 — Multi-Source Ledger Ingestion Gap (2026-09-03)
* **Trigger Analysis**: The agent received a request requiring multi-source data ingestion and anomaly tracing but failed to request or locate the actual file tabs and data contents to investigate the 185 closing balance discrepancy.
- **Rule**: Immediately request data dumps or file contents for all specified sources (QuickBooks, Cash App, Billing, and Control sheets) when a multi-source reconciliation is requested.
- **Rule**: Perform a systematic component breakdown of unexplained closing balances by verifying individual debits, credits, and cross-platform transaction IDs.
```
Steps: 1. Request/load all source tabs. 2. Verify main ledger net amounts total. 3. Isolate the target residual (e.g., 185) via subset summation.
```

## 🧬 Evolution v1.3 — Multi-Source Data File Ingestion Gap (2026-09-03)
* **Trigger Analysis**: The agent attempted a multi-source reconciliation without verifying that the required workbook tabs and raw transaction data were accessible or fully loaded into the execution context.
- **Rule**: Verify the presence and structure of all data sources (QBO, Cash App, Billing, Control sheets) before executing reconciliation scripts.
- **Rule**: Explicitly request raw file contents or tab breakdowns if any source data is missing or truncated in the initial prompt.
```
Reconciliation readiness check: Confirm access to [Tab 1: QBO], [Tab 2: Cash App], [Tab 3: Billing/Control] prior to delta calculation.
```

## 🧬 Evolution v1.4 — Unstructured Multi-Sheet Ledger Ingestion (2026-09-03)
* **Trigger Analysis**: The agent attempted reconciliation without programmatically inspecting multi-row header structures and irregular column layouts native to exported QuickBooks reports.
- **Rule**: Always inspect the raw top rows of exported QuickBooks or accounting spreadsheets to locate actual column headers before processing dataframes.
- **Rule**: Drop metadata header rows and reset the dataframe index using the identified header row index prior to executing balance reconciliations.
```
df = pd.read_excel('file.xlsx', header=None)
# locate header row where column contains 'Date'
header_idx = df[df.isin(['Date', 'Transaction date']).any(axis=1)].index[0]
df.columns = df.iloc[header_idx]
df = df.iloc[header_idx+1:].reset_index(drop=True)
```
