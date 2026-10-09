import contextvars

# Stores the hash of the API key for the current request
current_caller_id = contextvars.ContextVar("current_caller_id", default=None)
