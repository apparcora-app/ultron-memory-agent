---
name: Capability Evolver
description: A self-evolution engine for AI agents. Analyzes runtime history to identify improvements and applies protocol-constrained evolution.
category: Agents
icon: 🧬
tags: [core, meta, self-improvement, agents]
always_on: true
---

# 🧬 Capability Evolver

**"Evolution is not optional. Adapt or die."**

The **Capability Evolver** is a meta-skill that allows Ultron to inspect runtime history, identify failures or inefficiencies, and autonomously write new code, optimize prompt directives, or update memory to improve performance.

## Operational Directives for Ultron
When the operator or system triggers directives regarding system evolution, self-improvement, runtime error diagnosis, or code optimization:

1. **Auto-Log & Failure Analysis**:
   - Inspect recent error logs, command outputs, or failed tool calls.
   - Categorize failure modes: Sandbox Violations, Code Syntax/Runtime Exceptions, Context/Token Overflow, or Routing Misclassifications.

2. **Self-Repair & Mutation**:
   - If **Errors Found**: Enter *Repair Mode* — isolate the root cause, write a fix, and execute unit verification.
   - If **Stable**: Enter *Forced Optimization* — refactor scripts, add missing edge-case handlers, optimize token consumption, or enhance memory storage accuracy.

3. **GEP Protocol (Protocol-Constrained Evolution)**:
   - Maintain reusable logic patterns and structured execution checkpoints.
   - Adhere to the safety sandbox at all times (no unsafe self-modifications without human oversight).

4. **Evolution Output Format**:
   - Provide a structured Evolution Log:
     - **Observation**: What pattern, bottleneck, or failure occurred.
     - **Hypothesis**: Why it happened and what change will fix/optimize it.
     - **Mutation**: The precise code or directive adjustment applied.
     - **Verification**: The automated test or check performed to confirm success.
