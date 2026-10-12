# Quick Task: Step 2 Lightweight Embeddings & PyTorch Crash Elimination

## Objective
Eliminate the PyTorch/torchvision binary conflict (`operator torchvision::nms does not exist`) and reduce memory footprint:
1. Implement a lightweight `EmbeddingProvider` abstraction protocol in `memory/`.
2. Provide a default zero-PyTorch / ONNX embedding provider (`fastembed` or safe HuggingFace fallback).
3. Ensure `MemoryManager` and RAG components gracefully handle missing or conflicting torch libraries without crashing vector store initialization.
4. Verify tests `test_isolation.py` and `test_rag.py` pass or recover cleanly without torch crashes.
