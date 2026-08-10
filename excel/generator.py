import pandas as pd
from io import BytesIO
from typing import List, Dict

def generate_excel_bytes(records: List[Dict], filename: str) -> bytes:
    """Convert a list of dictionaries to an Excel file in memory.
    Returns the raw bytes that can be streamed to the client.
    """
    df = pd.DataFrame(records)
    # Reorder columns to match insertion order of first record if possible
    if not df.empty:
        first = records[0]
        df = df[[col for col in first.keys() if col in df.columns]]
    with BytesIO() as buffer:
        df.to_excel(buffer, index=False, engine="openpyxl")
        return buffer.getvalue()
