"""
Table Formatter

Converts raw PHP API response data into either:
1. A plain-text ASCII table (format()) - used as a fallback / for
   any consumer that just wants readable text.
2. A structured list of row dicts (format_rows()) - used by the
   frontend to render a real HTML table via renderTable().

Both share the same header/row-building logic so they can never
drift out of sync with each other.

Supports two layouts:

1. SINGLE EMPLOYEE - date-by-date rows + total row at the bottom
2. MULTIPLE EMPLOYEES - one row per employee with totals across date range

Does NOT:
- Call any API
- Call the LLM
- Do any aggregation (that's DataAggregator's job)
"""

import re
from datetime import datetime


class TableFormatter:

    _TIME_PATTERN = re.compile(r"^\d{1,3}:\d{2}:\d{2}$")

    # Candidate column names for employee identity
    _ID_CANDIDATES = ["EmpID", "EMPID", "EMP_ID", "userid", "UserID"]
    _NAME_CANDIDATES = ["EmpName", "EMPNAME", "Name", "UserName"]
    _DATE_CANDIDATES = ["Date", "DATE", "date", "ACTIVITY_DATE"]

    # Maps question keywords -> which time columns to show
    _COLUMN_KEYWORDS = {
        "TotalLoggedHours":      ["logged", "login", "log"],
        "TotalIdleHours":        ["idle"],
        "TotalProductiveHours":  ["productive", "productivity"],
        "TOTAL_ON_SYSTEM":       ["on system", "on-system", "system time"],
        "AwayFromSystem":        ["away", "away from system"],
    }

    def _filter_columns(self, question: str, time_columns: list) -> list:
        q = question.lower()
        matched = []

        for col, keywords in self._COLUMN_KEYWORDS.items():
            if col in time_columns and any(kw in q for kw in keywords):
                matched.append(col)

        return matched if matched else time_columns

    # ----------------------------------------------------------
    # Public entry points
    # ----------------------------------------------------------

    def format(self, api_response: dict, agg_result: dict, question: str = "") -> str:
        """Returns a plain-text ASCII table string (existing behaviour)."""
        built = self._build(api_response, agg_result, question)
        if not built:
            return ""

        title, headers, rows, total_row = built
        return self._build_table(title=title, headers=headers, rows=rows, total_row=total_row)

    def format_rows(self, api_response: dict, agg_result: dict, question: str = "") -> dict:
        """
        Returns structured data for UI rendering:
        {
            "title": str,
            "columns": [ {"key": "Date", "label": "Date"}, ... ],
            "rows": [ {"Date": "...", "Idle Hours": "...", ...}, ... ],
            "total": {"Date": "Total", "Idle Hours": "...", ...} or None
        }
        Returns {} if there's nothing to show.
        """
        built = self._build(api_response, agg_result, question)
        if not built:
            return {}

        title, headers, rows, total_row = built

        columns = [{"key": h, "label": h} for h in headers]
        row_dicts = [dict(zip(headers, r)) for r in rows]
        total_dict = dict(zip(headers, total_row)) if total_row else None

        return {
            "title": title,
            "columns": columns,
            "rows": row_dicts,
            "total": total_dict,
        }

    def _build(self, api_response: dict, agg_result: dict, question: str):
        """
        Shared logic - returns (title, headers, rows, total_row) or None.
        rows is a list of lists (not yet zipped into dicts).
        """
        if not agg_result.get("aggregated"):
            return None

        entity_count = agg_result.get("entity_count", 0)
        summary = agg_result.get("summary", [])
        time_columns = agg_result.get("time_columns", [])

        if not summary or not time_columns:
            return None

        filtered_columns = self._filter_columns(question, time_columns)

        if entity_count == 1:
            return self._build_single_employee(
                api_response=api_response,
                summary=summary[0],
                time_columns=filtered_columns
            )
        else:
            return self._build_multi_employee(
                summary=summary,
                time_columns=filtered_columns,
                truncated=agg_result.get("truncated", False),
                total_count=entity_count
            )

    # ----------------------------------------------------------
    # Single Employee Layout
    # ----------------------------------------------------------

    def _build_single_employee(self, api_response: dict, summary: dict, time_columns: list):

        rows = self._get_rows(api_response)
        emp_id = summary.get("id", "")
        emp_name = summary.get("name", emp_id)

        emp_rows = [r for r in rows if self._get_id(r) == emp_id]
        emp_rows = self._sort_by_date(emp_rows)

        if not emp_rows:
            return None

        date_key = self._find_key(emp_rows[0], self._DATE_CANDIDATES)

        headers = ["Date"] + [self._readable_col(c) for c in time_columns]

        data_rows = []
        for row in emp_rows:
            date_val = self._format_date(row.get(date_key, "")) if date_key else ""
            values = [date_val] + [row.get(c, "--") for c in time_columns]
            data_rows.append(values)

        total_values = ["Total"] + [summary.get(c, "--") for c in time_columns]

        title = f"{emp_name} ({emp_id})"
        return title, headers, data_rows, total_values

    # ----------------------------------------------------------
    # Multi Employee Layout
    # ----------------------------------------------------------

    def _build_multi_employee(self, summary: list, time_columns: list, truncated: bool, total_count: int):

        headers = ["Emp ID", "Name"] + [self._readable_col(c) for c in time_columns]

        data_rows = []
        for entry in summary:
            values = [
                entry.get("id", ""),
                entry.get("name", "")
            ] + [entry.get(c, "--") for c in time_columns]
            data_rows.append(values)

        grand_totals = self._compute_grand_totals(summary, time_columns)
        total_row = ["", "Total"] + [grand_totals.get(c, "--") for c in time_columns]

        title = f"(Showing top {len(summary)} of {total_count} employees)" if truncated else ""
        return title, headers, data_rows, total_row

    # ----------------------------------------------------------
    # ASCII Table Builder (used only by format())
    # ----------------------------------------------------------

    def _build_table(self, title: str, headers: list, rows: list, total_row: list = None) -> str:

        all_rows = [headers] + rows
        if total_row:
            all_rows.append(total_row)

        col_widths = [
            max(len(str(row[i])) for row in all_rows if i < len(row))
            for i in range(len(headers))
        ]

        def format_row(row):
            cells = []
            for i, cell in enumerate(row):
                width = col_widths[i] if i < len(col_widths) else 10
                cells.append(str(cell).ljust(width))
            return "| " + " | ".join(cells) + " |"

        def separator(char="-"):
            parts = [char * (w + 2) for w in col_widths]
            return "+" + "+".join(parts) + "+"

        lines = []

        if title:
            lines.append(title)

        lines.append(separator())
        lines.append(format_row(headers))
        lines.append(separator())

        for row in rows:
            lines.append(format_row(row))

        if total_row:
            lines.append(separator())
            lines.append(format_row(total_row))

        lines.append(separator())

        return "\n".join(lines)

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------

    def _get_rows(self, api_response: dict) -> list:
        if isinstance(api_response.get("data1"), list):
            return api_response["data1"]
        for value in api_response.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value
        return []

    def _find_key(self, row: dict, candidates: list):
        for c in candidates:
            if c in row:
                return c
        return None

    def _get_id(self, row: dict):
        key = self._find_key(row, self._ID_CANDIDATES)
        return row.get(key) if key else None

    def _sort_by_date(self, rows: list) -> list:
        date_key = self._find_key(rows[0], self._DATE_CANDIDATES) if rows else None
        if not date_key:
            return rows
        try:
            return sorted(rows, key=lambda r: r.get(date_key, ""))
        except Exception:
            return rows

    def _format_date(self, date_str: str) -> str:
        if not date_str:
            return ""
        try:
            d = datetime.strptime(str(date_str), "%Y-%m-%d")
            return d.strftime("%d %b %Y")
        except Exception:
            return str(date_str)

    def _readable_col(self, col_name: str) -> str:
        mapping = {
            "TotalLoggedHours": "Logged Hours",
            "TotalIdleHours": "Idle Hours",
            "TotalProductiveHours": "Productive Hours",
            "TOTAL_ON_SYSTEM": "On System",
            "AwayFromSystem": "Away From System",
        }
        return mapping.get(col_name, col_name)

    def _to_seconds(self, time_str) -> int:
        if not time_str or not isinstance(time_str, str):
            return 0
        if not self._TIME_PATTERN.match(time_str):
            return 0
        h, m, s = time_str.split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)

    def _format_seconds(self, total_seconds: int) -> str:
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _compute_grand_totals(self, summary: list, time_columns: list) -> dict:
        totals = {c: 0 for c in time_columns}
        for entry in summary:
            for c in time_columns:
                totals[c] += self._to_seconds(entry.get(c, ""))
        return {c: self._format_seconds(totals[c]) for c in time_columns}