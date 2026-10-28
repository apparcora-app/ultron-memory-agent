# TODOS.md — Ultron Protocol Design & Architecture Backlog

## Pending Design Improvements (Post-Review Follow-ups)

### 1. Dual-Theme Light/Dark Toggle Component
- **What:** Add a dedicated theme switcher button in `TopBar.tsx` that toggles `data-theme="dark"` / `data-theme="light"` on `document.documentElement` and persists to `localStorage`.
- **Why:** Delivers immediate high-contrast accessibility for operators in bright ambient lighting environments while preserving Obsidian Cyber by default.
- **Pros:** Empowers user choice, prevents eye strain, respects system preferences (`prefers-color-scheme`).
- **Cons:** Requires testing all modal backdrops in both palettes.
- **Context:** Decided in D7 of `/plan-design-review`.
- **Depends on / blocked by:** Semantic token mapping in `frontend/src/index.css`.

### 2. Live Stepper Animation in `ChatMessageItem.tsx`
- **What:** Replace the static reasoning accordion with an animated 3-stage stepper during streaming responses.
- **Why:** Communicates in-flight agent activity (memory retrieval, code sandbox execution, grounded synthesis) so users don't perceive multi-second tool latency as freezing.
- **Pros:** Enhances perceived responsiveness and provides transparency.
- **Cons:** Needs WebSocket/SSE event streaming hooks from `web.py`.
- **Context:** Decided in D9 of `/plan-design-review`.
- **Depends on / blocked by:** Web interface SSE endpoint.

### 3. Mobile Viewport Drawer & Tabbed Canvas
- **What:** Implement mobile off-canvas drawer and tabbed `[Chat] | [Canvas]` toggle for screens `< 768px`.
- **Why:** Ensures browser-use canvas and agent conversations are usable on mobile devices.
- **Pros:** Unlocks full remote monitoring from phones/tablets.
- **Cons:** Moderate React state restructuring in `KimiChatWorkspace.tsx`.
- **Context:** Decided in D8 of `/plan-design-review`.
