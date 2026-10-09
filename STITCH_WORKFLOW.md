# Stitch <-> Ultron Memory Agent Workflow Guide

## Overview
Your **Ultron Memory Agent** frontend is connected to **Google Stitch** via the Stitch Model Context Protocol (MCP) server in Antigravity.

---

## 1. Project Details
- **Project Name:** `Ultron Memory Agent`
- **Project Resource Name:** `projects/2782394628247933211`
- **Project ID:** `2782394628247933211`
- **Account / Profile:** Chrome Profile `Demo` (`demoworking791@gmail.com`)
- **Stitch Web URL:** [https://stitch.withgoogle.com](https://stitch.withgoogle.com)
- **Design System:** `Obsidian Cybernetics` (`#090a0f` base, `#00f0ff` cyan luminescence, Space Grotesk / JetBrains Mono)

---

## 2. Generated Screens in Stitch
1. **Ultron Memory Agent - Autonomous AI Workspace**
   - **Screen ID:** `e36e683d404b4675b7d88bcfb587302d`
   - **Full Path:** `projects/2782394628247933211/screens/e36e683d404b4675b7d88bcfb587302d`
   - **Description:** Complete cybernetic AI command workspace featuring the 3D glowing iridescent orb hero, floating command bar, active agent telemetry, and capability cards.
2. **Ultron Memory Agent - 50/50 Parallel Split Mode**
   - **Description:** Split workspace showing real-time AI conversation and tool call execution on the left, paired with the WebRTC browser execution screencast on the right.

---

## 3. Recommended Workflow for Editing

### Step A: Visual Iteration in Stitch
1. Open Google Chrome with your **Demo** profile.
2. Navigate to [Stitch](https://stitch.withgoogle.com).
3. Select **"Ultron Memory Agent"**.
4. Use the Stitch visual editor and prompt bar to tweak layouts, adjust components, or generate variants.

### Step B: Pulling Updates into Your Codebase via Antigravity
Whenever you make changes in Stitch, you don't need to manually copy code:
- Simply tell Antigravity:
  > *"Pull the latest updates from my Stitch screen `e36e683d404b4675b7d88bcfb587302d` into the React components in `ultron-memory-agent/frontend`."*
- Antigravity will invoke the Stitch MCP `get_screen` tool, extract the updated Tailwind CSS classes and HTML elements, and integrate them cleanly into `KimiChatWorkspace.tsx`, `ChatInput.tsx`, `Sidebar.tsx`, etc.

### Step C: Local Preview & Hot Reloading
Run your frontend locally to see the changes in real-time:
```powershell
cd "e:\Personal Data\Apps\AI Agents\ultron-memory-agent\frontend"
npm run dev
```
Preview at `http://localhost:5173`.
