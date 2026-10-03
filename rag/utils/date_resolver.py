"""
Date Resolver

Parses date references out of a user's question and resolves them into
a concrete {startDate, endDate} range.

Resolution order:
    1. Explicit dates in the question (e.g. "01-01-2026 to 06-01-2026",
       "2026-01-01 to 2026-01-06", "from 01/01/2026 to 06/01/2026")
       - if TWO explicit dates are found, they are used as start/end
         (sorted chronologically, in case the user wrote them out of order)
       - if ONE explicit date is found, it is used as both start and end
    2. Keyword phrases (case-insensitive):
        - "today", "yesterday", "tomorrow"
        - "this week", "last week"
        - "this month", "last month"
        - "this year", "last year"
        - "last N days" (e.g. "last 7 days", "last 30 days")
    3. Default: today's date for both startDate and endDate, if nothing
       above matched.

Dates are returned as ISO-format strings: "YYYY-MM-DD".
"""

import re
import calendar
from datetime import date, timedelta


class DateResolver:

    # Matches DD-MM-YYYY or DD/MM/YYYY, e.g. 01-01-2026, 6/1/2026
    _DMY_PATTERN = re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b")

    # Matches YYYY-MM-DD or YYYY/MM/DD, e.g. 2026-01-06
    _YMD_PATTERN = re.compile(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b")

    def __init__(self):
        pass

    def resolve(self, question: str, default_to_today: bool = True) -> dict | None:
        """
        Returns:
            {"startDate": "YYYY-MM-DD", "endDate": "YYYY-MM-DD"}
            or None if default_to_today=False and no date reference
            was found in the question.
        """

        original = question or ""
        text = original.lower()

        # -------------------------------------------------
        # 1. Explicit dates in the question take priority
        # -------------------------------------------------
        explicit_dates = self._find_explicit_dates(original)

        if len(explicit_dates) >= 2:
            start, end = sorted(explicit_dates[:2])
            return self._range(start, end)

        if len(explicit_dates) == 1:
            d = explicit_dates[0]
            return self._range(d, d)

        # -------------------------------------------------
        # 2. Keyword phrases
        # -------------------------------------------------
        today = date.today()

        match = re.search(r"last\s+(\d+)\s+days?", text)
        if match:
            n = int(match.group(1))
            start = today - timedelta(days=n - 1)
            return self._range(start, today)

        if "yesterday" in text:
            d = today - timedelta(days=1)
            return self._range(d, d)

        if "tomorrow" in text:
            d = today + timedelta(days=1)
            return self._range(d, d)

        if "today" in text:
            return self._range(today, today)

        if "last week" in text:
            start_of_this_week = today - timedelta(days=today.weekday())
            start = start_of_this_week - timedelta(days=7)
            end = start + timedelta(days=6)
            return self._range(start, end)

        if "this week" in text:
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
            return self._range(start, end)

        if "last month" in text:
            first_of_this_month = today.replace(day=1)
            last_month_end = first_of_this_month - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            return self._range(last_month_start, last_month_end)

        if "this month" in text:
            start = today.replace(day=1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            end = today.replace(day=last_day)
            return self._range(start, end)

        if "last year" in text:
            start = date(today.year - 1, 1, 1)
            end = date(today.year - 1, 12, 31)
            return self._range(start, end)

        if "this year" in text:
            start = date(today.year, 1, 1)
            end = date(today.year, 12, 31)
            return self._range(start, end)

        # -------------------------------------------------
        # 3. Named month — "January 2026", "in January", "for January"
        # -------------------------------------------------
        named = self._find_named_month(text, today)
        if named:
            return named

        # -------------------------------------------------
        # 3. No date info found in the question
        # -------------------------------------------------
        if default_to_today:
            return self._range(today, today)

        return None
    def _find_named_month(self, text: str, today: date):
        """
        Matches patterns like:
          "January 2026"  → 2026-01-01 to 2026-01-31
          "january"       → current year Jan 01 to Jan 31
          "for january"   → same
          "in feb 2026"   → 2026-02-01 to 2026-02-28
        """
        MONTHS = {
            "january": 1, "jan": 1,
            "february": 2, "feb": 2,
            "march": 3, "mar": 3,
            "april": 4, "apr": 4,
            "may": 5,
            "june": 6, "jun": 6,
            "july": 7, "jul": 7,
            "august": 8, "aug": 8,
            "september": 9, "sep": 9, "sept": 9,
            "october": 10, "oct": 10,
            "november": 11, "nov": 11,
            "december": 12, "dec": 12,
        }

        # Try "month_name year" e.g. "january 2026"
        pattern = re.compile(
            r"\b(" + "|".join(MONTHS.keys()) + r")\s+(\d{4})\b"
        )
        m = pattern.search(text)
        if m:
            month_num = MONTHS[m.group(1)]
            year = int(m.group(2))
            last_day = calendar.monthrange(year, month_num)[1]
            return self._range(date(year, month_num, 1), date(year, month_num, last_day))

        # Try bare "month_name" without year — assume current year,
        # but if the month is in the future use current year anyway
        pattern2 = re.compile(
            r"\b(" + "|".join(MONTHS.keys()) + r")\b"
        )
        m2 = pattern2.search(text)
        if m2:
            month_num = MONTHS[m2.group(1)]
            year = today.year
            last_day = calendar.monthrange(year, month_num)[1]
            return self._range(date(year, month_num, 1), date(year, month_num, last_day))

        return None

    def _find_explicit_dates(self, text: str) -> list:
        """
        Scans the text for explicit date patterns and returns them as
        a list of date objects, in the order they appear.

        Tries YYYY-MM-DD / YYYY/MM/DD first (unambiguous), then
        DD-MM-YYYY / DD/MM/YYYY.
        """

        found = []

        # Track character spans already consumed so the two patterns
        # don't double-match overlapping text.
        consumed_spans = []

        for m in self._YMD_PATTERN.finditer(text):
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            parsed = self._safe_date(year, month, day)
            if parsed:
                found.append((m.start(), parsed))
                consumed_spans.append((m.start(), m.end()))

        for m in self._DMY_PATTERN.finditer(text):
            # Skip if this span overlaps something already matched above
            if any(m.start() < end and m.end() > start for start, end in consumed_spans):
                continue

            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            parsed = self._safe_date(year, month, day)
            if parsed:
                found.append((m.start(), parsed))

        # Sort by position in the original text (order of appearance),
        # then strip the position marker before returning.
        found.sort(key=lambda pair: pair[0])
        return [d for _, d in found]

    def _safe_date(self, year: int, month: int, day: int):
        try:
            return date(year, month, day)
        except ValueError:
            return None

    def _range(self, start: date, end: date) -> dict:
        return {
            "startDate": start.isoformat(),
            "endDate": end.isoformat()
        }