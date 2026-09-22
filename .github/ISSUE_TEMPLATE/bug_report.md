---
name: Bug Report
about: Report a reproducible bug in the Ultron Memory Agent
title: "[BUG] "
labels: bug
assignees: apparcora-app
---

## Bug Description
A clear and concise description of the bug.

## Environment
| Field | Value |
|---|---|
| OS | <!-- e.g. Windows 11, Ubuntu 22.04 --> |
| Python Version | <!-- e.g. 3.11.4 --> |
| LLM Provider | <!-- gemini / anthropic / openrouter --> |
| Vector Store | <!-- chroma / qdrant --> |
| Interface | <!-- CLI / Web HUD / Discord --> |

## Steps to Reproduce
1. Set `LLM_PROVIDER=...` in `.env`
2. Run `python main.py`
3. Enter `...`
4. See error

## Expected Behavior
What you expected to happen.

## Actual Behavior
What actually happened. Include the **full stack trace** if available:

```
Paste stack trace here
```

## Minimal Reproduction Script
```python
# If possible, provide a minimal script that reproduces the issue
```

## Additional Context
- Relevant `.env` settings (redact all API keys)
- Any custom configuration in `config/`
- Screenshots if applicable
