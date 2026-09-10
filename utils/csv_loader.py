"""
Permanent standard CSV loader for Boss's data analysis tasks.
Enforces: on_bad_lines='skip' + missing-header recovery + fillna('N/A').
Locked in per Boss directive — do not bypass for CSV analysis requests.
"""
import pandas as pd


def _is_header_broken(columns):
    """True if columns look auto-generated/garbage rather than real header labels."""
    for c in columns:
        s = str(c).strip()
        if s.startswith("Unnamed"):
            continue
        if s.lstrip("-").isdigit():
            continue
        if isinstance(c, (int, float)):
            continue
        return False  # found at least one genuine-looking text header -> assume OK
    return True  # every column looked auto-generated / numeric-only


def safe_read_csv(filepath, expected_columns=None, **kwargs):
    """
    Standardized CSV reader that:
      1. Skips malformed/bad lines instead of raising ParserError.
      2. Detects missing/corrupted headers and recovers using expected_columns
         (if provided) to prevent downstream KeyError.
      3. Fills all missing values with 'N/A' before returning.

    Args:
        filepath: path to CSV file.
        expected_columns: optional list of column names to enforce/recover
                           if header row is missing or malformed.
        **kwargs: passed through to pd.read_csv (except on_bad_lines).

    Returns:
        pandas.DataFrame ready for summary/metric extraction.
    """
    kwargs.pop("on_bad_lines", None)

    try:
        df = pd.read_csv(filepath, on_bad_lines="skip", engine="python", **kwargs)
    except Exception:
        df = pd.read_csv(
            filepath, on_bad_lines="skip", engine="python", header=None, **kwargs
        )

    if _is_header_broken(df.columns):
        if expected_columns:
            n = min(len(expected_columns), df.shape[1])
            df = df.iloc[:, :n]
            df.columns = expected_columns[:n]
        else:
            df.columns = [f"col_{i}" for i in range(df.shape[1])]

    df = df.fillna("N/A")
    return df


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = safe_read_csv(sys.argv[1])
        print(result.head())
        print(f"\nShape: {result.shape}")
