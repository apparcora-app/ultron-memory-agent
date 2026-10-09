"""
core/observability/langfuse_tracer.py - Layer 5: Observability & Monitoring

Uses the Langfuse @observe decorator for best-practice tracing.
"""

import os
from core.log_config import get_logger

_log = get_logger(__name__)

# Only apply tracing if keys are present
if os.environ.get("LANGFUSE_SECRET_KEY"):
    try:
        from langfuse.decorators import observe
        _log.info("Langfuse observability enabled.")
    except ImportError:
        _log.warning("langfuse package not installed. Run: pip install langfuse")
        def observe(*args, **kwargs):
            def decorator(func):
                return func
            return decorator
else:
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

def flush_traces():
    """Flush any pending traces before application exit."""
    try:
        from langfuse.decorators import langfuse_context
        langfuse_context.flush()
    except:
        pass

def get_managed_prompt(prompt_name: str, fallback_prompt: str, **kwargs) -> str:
    """
    Layer 8: Prompt Management.
    Attempts to fetch a managed prompt from Langfuse Cloud and compile it.
    If the prompt does not exist or Langfuse is offline, returns the fallback_prompt.
    """
    if os.environ.get("LANGFUSE_SECRET_KEY"):
        try:
            from langfuse import Langfuse
            lf = Langfuse()
            # Fetch the prompt from Langfuse
            prompt_obj = lf.get_prompt(prompt_name)
            if prompt_obj:
                _log.info(f"Loaded managed prompt '{prompt_name}' from Langfuse.")
                # Compile it with any provided variables (must match mustache {{}} syntax in Langfuse)
                return prompt_obj.compile(**kwargs)
        except Exception as e:
            if "NotFoundError" not in str(type(e)):
                _log.warning(f"Could not load managed prompt '{prompt_name}' from Langfuse. Using fallback. ({e})")
            else:
                _log.info(f"Prompt '{prompt_name}' not found in Langfuse. Using hardcoded fallback.")
    
    return fallback_prompt
