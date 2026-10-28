# DESIGN.md — Ultron Protocol Design System Specification

**Version:** 1.0.0  
**Status:** Approved via `/plan-design-review` (October 2026)  
**Archetype:** Autonomous Cybernetic Mainframe (Dual Mode: Obsidian Cyber default / Crisp Laboratory toggle)

---

## 1. Design Principles & Anti-Slop Policy

1. **Autonomous Mainframe, Not a Generic SaaS Starter:**
   - No 3-column generic card grids ("Image Generator / Video Generator / Dev Assistant").
   - Cards are used only when the card itself is the primary interactive container (e.g., live canvas, modal drawer).
2. **Substance over Decoration:**
   - Every badge, status light, and metric reflects live backend telemetry (indexed vectors, swarm squad, sandbox state).
   - No floating SVG blobs, generic purple gradients, or unmotivated dropshadows.
3. **Calm Surface Hierarchy:**
   - Asymmetric visual weight: Command Dock acts as the visual anchor.
   - Secondary context stays muted until focused or activated by tool execution.
4. **Empathetic Feedback:**
   - Live execution steppers show in-flight tool actions (`[1/3] RRF memory query... [2/3] Sandbox execution...`).
   - Clean auto-collapse on turn completion to keep reading flow uninterrupted.

---

## 2. Semantic Color Token System

All components must reference semantic CSS variables, never raw hardcoded hex codes.

### 2.1 Dark Mode (Obsidian Cyber — Default)
```css
:root[data-theme="dark"], body.dark-theme {
  --bg-ground: #07090e;        /* Deep void background */
  --bg-panel: #0d121d;         /* Sidebar and card surface */
  --bg-dock: #111827;          /* Floating command input dock */
  --bg-overlay: rgba(7, 9, 14, 0.85);

  --border-subtle: #1e293b;    /* Hairline borders */
  --border-focus: #0284c7;     /* Focused inputs & active state */
  --border-accent: #38bdf8;

  --text-main: #f8fafc;        /* High-contrast primary type */
  --text-muted: #94a3b8;       /* Secondary descriptions */
  --text-dim: #64748b;         /* Metadata & timestamps */

  --accent-primary: #0284c7;   /* Cobalt / Sky Blue primary */
  --accent-glow: rgba(2, 132, 199, 0.35);
  --accent-success: #10b981;  /* Emerald for ledger truth */
  --accent-warning: #f59e0b;  /* Amber for fallback routes */
  --accent-danger: #ef4444;   /* Crimson for lockdown */
}
```

### 2.2 Light Mode (Crisp Laboratory — Toggle)
```css
:root[data-theme="light"], body.light-theme {
  --bg-ground: #f8fafc;        /* Slate-50 clean backdrop */
  --bg-panel: #ffffff;         /* Pure white sidebar & cards */
  --bg-dock: #ffffff;          /* White input container */
  --bg-overlay: rgba(248, 250, 252, 0.85);

  --border-subtle: #e2e8f0;    /* Crisp light border */
  --border-focus: #0284c7;     /* Sky-600 focus ring */
  --border-accent: #0284c7;

  --text-main: #0f172a;        /* Slate-900 primary text */
  --text-muted: #475569;       /* Slate-600 secondary text */
  --text-dim: #94a3b8;         /* Slate-400 subtle labels */

  --accent-primary: #0284c7;   /* Sky-600 primary */
  --accent-glow: rgba(2, 132, 199, 0.15);
  --accent-success: #059669;
  --accent-warning: #d97706;
  --accent-danger: #dc2626;
}
```

---

## 3. Typography & Spacing Grid

- **Display & Headings:** `Inter`, system-ui fallback (`font-sans font-bold`).
- **Data, Code, & Telemetry:** `JetBrains Mono` or `Roboto Mono` (`font-mono text-xs`).
- **Scale:**
  - H1 / Screen Title: `text-2xl sm:text-3xl font-bold tracking-tight`
  - H2 / Section Header: `text-xs font-semibold tracking-[0.2em] uppercase font-mono`
  - Body Text: `text-sm leading-relaxed font-normal`
  - Code & Badges: `text-xs font-mono font-medium`
- **Spacing Scale:** Standard 8px rhythm (p-2 = 8px, p-4 = 16px, p-6 = 24px, gap-4 = 16px).

---

## 4. Interaction State Matrix

| Component | Loading State | Empty State | Error State | Success / Active State |
|---|---|---|---|---|
| **Directive Threads** | 3-row shimmer skeleton | "No directives yet. Press Ctrl+K to begin." | "Thread sync failed. [Retry]" | Highlighted active thread badge |
| **Command Dock** | Subtle pulsing border glow | Placeholder: "Transmit directive or query memory..." | Red shake animation + error pill | Send button circular sky-blue ring |
| **Live WebRTC Canvas** | Connecting overlay + 60fps pill | "Canvas Standby — Awaiting tool execution" | "Stream disconnected. [Reconnect]" | Interactive 60fps canvas feed |
| **Thought & Tool Ledger** | Live step stepper (`[1/3] RRF query`) | N/A (hidden if no tools) | Failed tool execution block + stderr | Auto-collapsed summary pill |

---

## 5. Responsive & Accessibility Directives

- **Mobile Viewport (< 768px):**
  - Left sidebar collapses into an off-canvas slide-out sheet (hamburger trigger).
  - Horizontal 50/50 split canvas changes to a tabbed toggle: `[Directive Thread] | [Live Canvas]`.
- **Touch Targets:** All clickable icon buttons and tags must measure a minimum of `44px x 44px` click target area.
- **Keyboard Navigation:**
  - `Ctrl+K`: Focus command dock / trigger new directive.
  - `Escape`: Close open modals, dismiss canvas overlay.
- **ARIA:** All incoming message streams must carry `aria-live="polite"`. Modals must enforce `role="dialog"` with focus trapping.
