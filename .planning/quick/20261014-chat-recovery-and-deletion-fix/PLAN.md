---
status: complete
date: 2026-10-14
slug: chat-recovery-and-deletion-fix
---

# Quick Task: Recover Authentic Chats and Fix Sidebar Deletion & Ghost Directives

## Objective
Address user issue regarding missing historical chats, failed sidebar deletion, and ghost "New Directive" generation:
1. Conduct an LLM Council deliberation across Systems Architect, Security & Resilience Specialist, and Pragmatic Builder personas.
2. Recover all 22 genuine user conversations across historical backups and encrypted archives (`mock_remote/*.enc`, `data-backup-*`, `temp_backup/`) and consolidate them into canonical `data/sessions/`.
3. Purge 53 synthetic automated test sessions (`confirm your active`, `Stitch Verification Session`) and 30 empty drafts.
4. Point `ChatSessionManager` in `src/ultron/memory/chat_session_manager.py` to canonical `data/sessions/` with prefix normalization and robust path resolution.
5. Fix `handleDeleteSession` and `handleNewSession` in `KimiChatWorkspace.tsx` to stop eager `POST /api/sessions/new` on deletion and instead transition cleanly to adjacent existing chats or local draft mode.
6. Rebuild frontend production assets and verify with automated pytest integration suite.
