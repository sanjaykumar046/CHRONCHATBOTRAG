import json
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]

EXCEL_FILE = BASE_DIR / "registry" / "API_Registry_Correct.xlsx"
JSON_FILE = BASE_DIR / "registry" / "api_registry_Correct.json"


def convert():

    df = pd.read_excel(EXCEL_FILE)

    # Excel stores complex registry metadata as JSON text in a cell. Restore
    # those cells to native JSON values in the generated registry.
    metadata_columns = [
        column for column in df.columns
        if str(column).endswith(" Metrics")
    ]
    for column in metadata_columns:
        def parse_metadata(value):
            if not isinstance(value, str) or not value.strip():
                return ""
            try:
                return json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON in Excel registry column '{column}': {exc}"
                ) from exc

        df[column] = df[column].map(parse_metadata)

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
