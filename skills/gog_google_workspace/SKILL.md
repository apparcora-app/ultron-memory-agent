---
name: Google Workspace CLI (gog)
description: Autonomous integration for Gmail, Google Calendar, Google Drive, Google Sheets, Google Docs, and Contacts via the gog CLI tool.
category: Integrations
icon: 📧
tags: [gmail, calendar, drive, sheets, docs, contacts, google, email, gog, workspace]
---

# 📧 Google Workspace CLI Protocol (gog)

Use **`gog`** for deep programmatic access to Gmail, Google Calendar, Google Drive, Google Contacts, Google Sheets, and Google Docs.

## Setup Requirements (Once)
```bash
gog auth credentials /path/to/client_secret.json
gog auth add you@gmail.com --services gmail,calendar,drive,contacts,sheets,docs
gog auth list
```

## Operational Directives for Ultron

When Boss requests email, calendar, spreadsheet, or drive actions:

### 1. Gmail Operations
- **Search Unread/Recent**: `gog gmail search 'newer_than:7d is:unread' --max 10 --json`
- **Search by Query**: `gog gmail search 'from:client@company.com' --max 10 --json`
- **Send Email**: `gog gmail send --to "target@email.com" --subject "Subject Line" --body "Message Body"`
- *(Note: Always confirm with Boss before sending external emails unless explicitly instructed).*

### 2. Google Calendar Operations
- **List Events**: `gog calendar events <calendarId> --from <iso_date> --to <iso_date> --json`
- **Agenda Overview**: Extract today's events, timing, and meeting links for Boss.

### 3. Google Drive Operations
- **File Search**: `gog drive search "query" --max 10 --json`
- **Find Spreadsheets/Docs**: Search by mimeType or name to locate files on Drive.

### 4. Google Sheets Operations
- **Read Range**: `gog sheets get <sheetId> "Tab!A1:D10" --json`
- **Update Range**: `gog sheets update <sheetId> "Tab!A1:B2" --values-json '[["A","B"],["1","2"]]' --input USER_ENTERED`
- **Append Rows**: `gog sheets append <sheetId> "Tab!A:C" --values-json '[["x","y","z"]]' --insert INSERT_ROWS`
- **Clear Range**: `gog sheets clear <sheetId> "Tab!A2:Z"`
- **Inspect Metadata**: `gog sheets metadata <sheetId> --json`

### 5. Google Docs Operations
- **Export Content**: `gog docs export <docId> --format txt --out /path/to/doc.txt`
- **Read Document**: `gog docs cat <docId>`

### 6. Contacts Operations
- **List Contacts**: `gog contacts list --max 20 --json`

## Best Practices
- Prefer `--json` and `--no-input` when executing commands in automated script flows.
- Pass Sheets values using `--values-json`.
- Always structure output neatly in tabular markdown when reporting back to Boss.
