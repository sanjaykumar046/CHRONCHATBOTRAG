"""
Data Aggregator

Raw API responses like fetch_employee_activity1.php return one row per
employee PER DAY, with time values as "HH:MM:SS" strings (e.g.
"07:12:09"). Handing this raw, multi-row, string-time data straight to
an LLM causes two problems:
    1. The LLM has to do arithmetic (summing HH:MM:SS across days) -
       small models are unreliable at this and frequently miscalculate.
    2. The full row list can be huge (100+ employees x many days),
       blowing up the prompt and making generation slow.

This module fixes both by aggregating correctly in Python BEFORE the
data reaches the LLM: summing each time-based column per employee
across all rows, and returning a compact, pre-computed summary. The
LLM then only has to turn already-correct numbers into a sentence.

Does NOT:
- Call any API
- Use the LLM
- Know anything about which specific intent/endpoint was called -
  this is generic, driven purely by the shape of the data (rows with
  an ID-like column and HH:MM:SS-formatted columns).
"""

import re


class DataAggregator:

    _TIME_PATTERN = re.compile(r"^\d{1,3}:\d{2}:\d{2}$")

    # Candidate column names that identify "which row belongs to whom".
    _ID_CANDIDATES = ["EmpID", "EMPID", "EMP_ID", "userid", "UserID"]
    _NAME_CANDIDATES = ["EmpName", "EMPNAME", "Name", "UserName"]

    def aggregate(self, api_response: dict, top_n: int = 15) -> dict:
        """
        Looks for a list of rows (under "data1", falling back to any
        top-level list-of-dicts value) and, if found, returns a compact
        per-entity summary with correctly-summed time totals.

        Returns the aggregation result. If the data doesn't look like
        row-based time-series data, returns {"aggregated": False} and
        the caller should fall back to handling api_response as-is.
        """

        rows = self._find_rows(api_response)

        if not rows:
            return {"aggregated": False}

        id_key = self._find_key(rows[0], self._ID_CANDIDATES)

        if not id_key:
            return {"aggregated": False}

        name_key = self._find_key(rows[0], self._NAME_CANDIDATES)
        time_keys = self._find_time_columns(rows)

        if not time_keys:
            return {"aggregated": False}

        # ---------------------------------------------------------
        # Sum each time column per entity, across all rows (days)
        # ---------------------------------------------------------

        grouped = {}

        for row in rows:
            entity_id = row.get(id_key)
            if entity_id is None:
                continue

            if entity_id not in grouped:
                grouped[entity_id] = {
                    "id": entity_id,
                    "name": row.get(name_key) if name_key else entity_id,
                    "days_counted": 0,
                    "_seconds": {k: 0 for k in time_keys}
                }

            grouped[entity_id]["days_counted"] += 1

            for key in time_keys:
                seconds = self._to_seconds(row.get(key))
                grouped[entity_id]["_seconds"][key] += seconds

        # ---------------------------------------------------------
        # Format results as readable totals
        # ---------------------------------------------------------

        summary = []
        for entity in grouped.values():
            entry = {
                "id": entity["id"],
                "name": entity["name"],
                "days_counted": entity["days_counted"],
            }
            for key in time_keys:
                entry[key] = self._format_seconds(entity["_seconds"][key])
            summary.append(entry)

        # Sort by the first time column, descending, so the most
        # relevant entries (e.g. highest productive hours) come first
        primary_key = time_keys[0]
        summary.sort(
            key=lambda e: self._to_seconds_from_formatted(e[primary_key]),
            reverse=True
        )

        return {
            "aggregated": True,
            "entity_count": len(summary),
            "time_columns": time_keys,
            "summary": summary[:top_n],
            "truncated": len(summary) > top_n
        }

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------

    def _find_rows(self, api_response: dict):
        if not isinstance(api_response, dict):
            return None

        if isinstance(api_response.get("data1"), list) and api_response["data1"]:
            return api_response["data1"]

        # Fallback: look for any top-level list of dicts
        for value in api_response.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value

        return None

    def _find_key(self, sample_row: dict, candidates: list):
        for c in candidates:
            if c in sample_row:
                return c
        return None

    def _find_time_columns(self, rows: list) -> list:
        if not rows:
            return []

        sample = rows[0]
        time_keys = []

        for key, value in sample.items():
            if isinstance(value, str) and self._TIME_PATTERN.match(value):
                time_keys.append(key)

        return time_keys

    def _to_seconds(self, time_str) -> int:
        if not time_str or not isinstance(time_str, str):
            return 0
        if not self._TIME_PATTERN.match(time_str):
            return 0
        h, m, s = time_str.split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)

    def _to_seconds_from_formatted(self, time_str: str) -> int:
        return self._to_seconds(time_str)

    def _format_seconds(self, total_seconds: int) -> str:
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"