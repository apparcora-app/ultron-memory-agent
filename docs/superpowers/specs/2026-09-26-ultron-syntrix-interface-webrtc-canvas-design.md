# Design Specification: Ultron Cybernetic Workspace with Parallel WebRTC Canvas

**Document**: `2026-09-26-ultron-syntrix-interface-webrtc-canvas-design.md`  
**Date**: September 26, 2026  
**Status**: Approved (Brainstorming Phase)  
**Target Repository**: `ultron-memory-agent`  

---

## 1. Executive Summary

This specification defines the complete redesign of the **Ultron Protocol** frontend and its integration with the backend WebRTC screencast engine. 

The user interface transitions from a utilitarian HUD to a sleek, dark-mode conversational dashboard inspired by modern agent design systems (syntrix aesthetic), featuring:
1. An ambient dark viewport with a 3D glowing iridescent central sphere, welcome typography, and bottom capability cards (*Image Generator*, *Video Generator*, *Dev Assistant*).
2. A streamlined sidebar with categorized features (*Images, Videos, Codex, Apps, Projects*), persistent chat history, and system telemetry (with all promotional/upgrade cards removed).
3. Directly accessible operational controls: **Solo Agent vs. Swarm Agent** toggle, **Prompt Optimizer** on/off toggle, in-bar **LLM Shift selector**, and a dedicated **Skills Matrix** manager.
4. An intelligent **Side-by-Side Parallel WebRTC Canvas** that smoothly slides into view whenever the agent activates browser automation or computer execution tools, streaming low-latency 60 FPS video of the active browser environment with interactive takeover capabilities.

---

## 2. Visual Architecture & Layout System

### 2.1 Workspace Structure

The application operates in two primary visual phases:

* **State A: Welcome View (Zero Messages)**
  * **Top Header**: Version pill dropdown (`Ultron v4.2 ▾`), quick navigation (`Dashboard`, `Settings`, `Help & Support`), and user avatar profile.
  * **Center Stage**:
    * An iridescent, cyan-to-emerald gradient glowing sphere with ambient radial diffusion.
    * Uppercase sub-heading: `WELCOME BACK`.
    * Bold hero statement: `Bring your ideas to life today`.
    * Centered floating card input with ambient shadow and glassmorphism outline.
  * **Bottom Feature Grid**:
    * Three equal-width interactive cards: *Image Generator*, *Video Generator*, and *Dev Assistant*, each with category icon and outbound launch arrow (`↗`).

* **State B: Active Conversation Feed (Messages Present)**
  * Welcome hero, orb, and starter cards smoothly animate out via Framer Motion.
  * The message history scrolls vertically, displaying user queries and Ultron responses (with formatted Markdown, syntax-highlighted code blocks with copy buttons, heuristic reasoning accordions, and active tool execution badges).
  * The chat input bar docks neatly at the bottom with all active controls preserved.
  * Clicking `+ New Chat` in the sidebar restores State A.

---

## 3. Parallel WebRTC Browser Window

### 3.1 Dual-Pane Split Layout

When a browser or computer tool is invoked (or when the user clicks the Live View button):
* The main workspace transitions into a **50/50 dual pane** (or user-dragged ratio):
  * **Left Column**: Conversational chat thread and controls.
  * **Right Column**: Live WebRTC Browser Canvas.
* A vertical draggable divider allows flexible resizing between 25% and 75% width.
* A prominent `[X]` button on the canvas header allows instant collapse back to single-pane chat.

### 3.2 WebRTC Streaming Pipeline

* **Protocol**: WebRTC PeerConnection with `H.264` / `VP8` / `yuv420p` video track negotiated via `/api/webrtc/offer`.
* **Framerate & Latency**: Target 60 FPS streaming with sub-100ms local network latency.
* **Cursor Overlay**: Real-time agent cursor coordinates rendered as an animated pointer over the video canvas.
* **Manual Navigation Bar**: Includes a URL search bar and quick-launch shortcuts (*DuckDuckGo*, *Hacker News*, *GitHub*, *Wikipedia*) that dispatch navigation commands directly to the backend.

---

## 4. Agent Operational Controls

### 4.1 Solo Agent vs. Swarm Agent Selector
* Located as a quick-switch toggle in the chat controls bar:
  * **Solo Agent (`DIRECT`)**: High-speed, single-model execution for rapid answers.
  * **Swarm Agent (`SWARM`)**: Multi-agent mesh coordinating Ultron Prime, Titan (Full-Stack), Sentinel (Security/Audit), and Nexus (Integration).

### 4.2 Prompt Optimizer (ON / OFF)
* Dedicated button toggle (`⚡ Prompt Optimizer: ON/OFF`).
* When active, passes `optimize_prompt=True` to `/api/chat`, triggering backend prompt enhancement and returning optimization telemetry.

### 4.3 LLM Shift (In-Chat Model Selector)
* Dropdown selector embedded right in the chat input panel:
  * `Auto-Route (Intelligent Heuristic)` *(Default)*
  * `Gemini 2.5 Flash`
  * `Gemini 2.5 Pro`
  * `Claude 3.7 Sonnet`
  * `GPT-4o`
  * `DeepSeek R1`
  * `Llama 3.3 (Local Ollama)`

### 4.4 Skills Matrix (`✨ Skills` Manager)
* Modal dialog or slide-over drawer triggered by the `Skills` button:
  * Displays all loaded skills discovered by the backend (`/api/skills`), showing skill names, description, parameters, and active status.
  * Search/filter bar to quickly locate specialized skills.
  * Form to register or install custom skills on the fly (`POST /api/skills`).

---

## 5. Component Breakdown

| Component | Responsibility |
| :--- | :--- |
| `App.tsx` | Root container, viewport bounds, global theme provider. |
| `UltronWorkspace.tsx` | Main orchestrator managing dual-pane split ratio, session states, and WebRTC visibility. |
| `Sidebar.tsx` | Left navigation drawer with brand header, `+ New Chat`, FEATURES list, YOUR CHATS, and system status. |
| `WelcomeHero.tsx` | Renders the 3D iridescent glowing sphere, greeting typography, and the 3 bottom cards. |
| `ChatInput.tsx` | Floating/docked input card with Solo/Swarm, Prompt Opt, LLM shift, Skills trigger, Voice, and Send. |
| `ChatMessageItem.tsx` | Renders message bubbles, Markdown, code blocks, reasoning accordions, and tool badges. |
| `CanvasPane.tsx` | Right-side container for URL navigation, connection status pill, and WebRTC viewport. |
| `WebRTCPlayer.tsx` | HTML5 `<video>` element wired to WebRTC `MediaStream` with canvas cursor overlay. |
| `SkillsModal.tsx` | Comprehensive dialog for viewing and adding capabilities from the backend skills registry. |

---

## 6. Verification & Quality Protocol

1. **TypeScript & Build Check**: Run `tsc -b && vite build` inside `ultron-memory-agent/frontend` to verify 0 compile or bundling errors.
2. **Static Asset Verification**: Ensure the Vite build artifacts are properly emitted to `ultron-memory-agent/static/assets` so FastAPI serves the updated frontend seamlessly.
3. **End-to-End Functional Test**:
   * Verify chat submission transitions the UI smoothly from Welcome to Chat state.
   * Verify toggling Solo vs Swarm, Prompt Optimizer, and LLM selection properly sends parameters to `/api/chat`.
   * Verify browser queries open the parallel WebRTC canvas and establish the live video stream.
