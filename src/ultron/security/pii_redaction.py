import re


def safe_redact_text(text: str) -> str:
    if not isinstance(text, str):
        return text
    # Redact SSN (XXX-XX-XXXX or XXXXXXXXX)
    text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[REDACTED_SSN]', text)
    # Redact EIN (XX-XXXXXXX)
    text = re.sub(r'\b\d{2}-\d{7}\b', '[REDACTED_EIN]', text)
    # Redact Credit Cards (16 digits)
    text = re.sub(r'\b(?:\d{4}[-\s]?){3}\d{4}\b', '[REDACTED_CARD]', text)
    # Redact Emails
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[REDACTED_EMAIL]', text)
    return text

def safe_redact_obj(obj):
    if isinstance(obj, str):
        return safe_redact_text(obj)
    elif isinstance(obj, dict):
        return {k: safe_redact_obj(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [safe_redact_obj(i) for i in obj]
    return obj

if __name__ == "__main__":
    # Test
    print(safe_redact_text("SSN is 123-45-6789 and EIN is 12-3456789."))
