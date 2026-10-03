from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]

EXCEL_FILE = BASE_DIR / "registry" / "API Registry.xlsx"

print(f"Reading: {EXCEL_FILE}")

df = pd.read_excel(EXCEL_FILE)

print("=" * 100)
print("Columns")
print("=" * 100)
print(df.columns.tolist())

print()

print("=" * 100)
print("First Row")
print("=" * 100)
print(df.iloc[0].to_dict())