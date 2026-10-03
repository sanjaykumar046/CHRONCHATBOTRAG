import json
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]

EXCEL_FILE = BASE_DIR / "registry" / "API_Registry_Correct.xlsx"
JSON_FILE = BASE_DIR / "registry" / "api_registry_Correct.json"


def convert():

    df = pd.read_excel(EXCEL_FILE)

    records = df.fillna("").to_dict(orient="records")

    with open(JSON_FILE, "w", encoding="utf-8") as file:
        json.dump(
            records,
            file,
            indent=4,
            ensure_ascii=False
        )

    print("=" * 80)
    print("Registry converted successfully.")
    print(f"Total Records : {len(records)}")
    print(f"Output File   : {JSON_FILE}")
    print("=" * 80)


if __name__ == "__main__":
    convert()