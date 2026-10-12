---
name: Mission Control Kanban Task Protocol
description: Autonomous Kanban-style task management and execution engine. Monitors tasks in data/tasks.json, works through subtasks, enforces Definition of Done (DoD), handles human rework, and updates status.
category: Productivity
icon: 🎯
tags: [kanban, tasks, mission-control, workflow, automation, execution, project-management, agile]
always_on: false
---

# 🎯 Mission Control Kanban Task Protocol

A Kanban-style task board and execution engine that Ultron manages. Boss creates and prioritizes tasks via the web dashboard or chat; Ultron executes them automatically when moved to **"In Progress"**.

## Task Lifecycle & Status Values
- **`permanent`**: Recurring or standing background directives (daily checks, audits, heartbeat).
- **`backlog`**: Tasks queued and waiting to be worked on.
- **`in_progress`**: Ultron is actively executing this task.
- **`review`**: Task completed by Ultron, awaiting Boss review and approval.
- **`done`**: Completed, verified, and approved by Boss.

## Task Data Schema (`data/tasks.json`)
```json
{
  "id": "task_001",
  "title": "Implement feature X",
  "description": "Detailed context and instructions for Ultron",
  "status": "backlog",
  "priority": "high",
  "dod": "Definition of Done - what success looks like",
  "subtasks": [
    { "id": "sub_001", "title": "Research approach", "done": false },
    { "id": "sub_002", "title": "Write code", "done": false }
  ],
  "comments": []
}
```

## Operational Directives for Ultron

When a task is assigned or moved to **"In Progress"**:

### 1. Ingestion & Pre-Flight Check
- Read the task `title`, `description`, `priority`, and `dod` (Definition of Done).
- Verify all requirements, subtasks, and dependencies before writing code or running commands.

### 2. Execution Loop
- Work through `subtasks` sequentially (`sub_001` ➔ `sub_002` ➔ ...).
- Execute required code, file edits, or terminal operations using Ultron's autonomous tools.
- Mark each subtask `done: true` upon successful execution and verification.

### 3. Progress Logging & Documentation
- Document intermediate milestones and findings as structured progress comments.
- Format summaries with timestamps and clear bullet points.

### 4. Completion & Review Handoff
- When all subtasks are complete and the Definition of Done is verified:
  - Transition status from `in_progress` ➔ `review`.
  - Add a **Completion Summary**: What was built, verified, and any next steps for Boss.

### 5. Handling Rework / Feedback
- If Boss moves a task back to `in_progress` with feedback:
  - Read the latest comment from Boss.
  - Address specific requested adjustments or fixes.
  - Add a comment explaining the modifications made.
  - Transition status back to `review` for Boss sign-off.

### 6. EPIC Task Management
- For parent EPIC tasks with multiple child tickets (`MC-XXX-001: Title`):
  - Work through child tickets sequentially.
  - Comment results for each child ticket and mark its subtask done.
  - Move the parent EPIC to `review` only when all child items are verified.
