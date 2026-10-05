import json
import re

from rag.llm.ollama_client import OllamaClient
from rag.prompts.response_generation_prompt import RESPONSE_GENERATION_PROMPT


class ResponseService:
    """
    Final Stage - Intelligent Response Generation

    Option B: Frontend-Driven Rendering + Dynamic Natural Language Synthesis

    Backend uses an LLM to synthesize direct answers, summaries, rankings,
    or intros based on the user's specific question, and returns the raw API
    data so the frontend can render dynamic tables below the answer.
    """

    def __init__(self):
        self.llm = OllamaClient()

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "")).strip().lower()

    def _generate_llm_reply(self, question: str, data) -> str:
        """
        Dynamically formulates an intelligent, concise answer using local Ollama.
        Directly answers specific metrics, summarizes overviews, or ranks results.
        """
        try:
            if isinstance(data, (dict, list)):
                data_str = json.dumps(data, default=str)
                if len(data_str) > 3000:
                    data_str = data_str[:3000] + " ... (truncated)"
            else:
                data_str = str(data)

            prompt = RESPONSE_GENERATION_PROMPT.format(
                question=question,
                data=data_str
            )
            reply = self.llm.generate(
                prompt,
                options={"temperature": 0.2, "num_predict": 250},
                json_mode=False
            )
            cleaned = (reply or "").strip()
            return cleaned if cleaned else "Here are the results:"
        except Exception as e:
            print(f"[ResponseService] LLM generation error: {e}")
            return "Here are the results:"

    @staticmethod
    def _schema_value(data, path: str):
        """Resolve a dotted response path; '*' expands a list of records."""
        values = [data]
        for part in path.split("."):
            next_values = []
            for value in values:
                if part == "*" and isinstance(value, list):
                    next_values.extend(value)
                elif isinstance(value, dict) and part in value:
                    next_values.append(value[part])
            values = next_values
        return values

    @staticmethod
    def _duration_seconds(value):
        """Convert a HH:MM:SS value to seconds without assuming a day limit."""
        if isinstance(value, (int, float)):
            return float(value)
        parts = str(value).strip().split(":")
        if len(parts) != 3:
            raise ValueError("Duration must use HH:MM:SS format")
        hours, minutes, seconds = (int(part) for part in parts)
        return hours * 3600 + minutes * 60 + seconds

    @staticmethod
    def _format_duration(seconds: float) -> str:
        total = round(seconds)
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _schema_answer(
        self, question: str, data, response_metrics, direct_metric: bool
    ) -> str | None:
        """Answer a single explicitly mapped metric directly from API data."""
        if not direct_metric or not isinstance(response_metrics, list):
            return None

        normalized_question = self._normalize(question)
        matches = []
        for metric in response_metrics:
            if not isinstance(metric, dict):
                continue
            aliases = metric.get("matches", [])
            matched_aliases = [
                self._normalize(alias)
                for alias in aliases
                if isinstance(alias, str)
                and re.search(
                    rf"(?<!\w){re.escape(self._normalize(alias))}(?!\w)",
                    normalized_question,
                )
            ]
            if matched_aliases:
                matches.append((len(max(matched_aliases, key=len)), metric))

        # Only shortcut when one configured metric matches. Requests naming
        # multiple metrics continue through the existing LLM path.
        if len(matches) != 1:
            return None

        metric = matches[0][1]
        path = metric.get("path")
        if not isinstance(path, str) or not path:
            return None
        try:
            values = [value for value in self._schema_value(data, path) if value is not None]
            if not values:
                return None
            aggregation = metric.get("aggregation", "first")
            value_format = metric.get("format", "text")
            if value_format == "duration":
                seconds = [self._duration_seconds(value) for value in values]
                if aggregation == "sum":
                    result = sum(seconds)
                elif aggregation == "average":
                    result = sum(seconds) / len(seconds)
                elif aggregation == "first":
                    result = seconds[0]
                else:
                    return None
                rendered = self._format_duration(result)
            else:
                if aggregation != "first" or len(values) != 1:
                    return None
                rendered = f"{values[0]}{metric.get('suffix', '')}"
        except (TypeError, ValueError, ZeroDivisionError):
            return None

        label = str(metric.get("label", "Result")).strip()
        return f"{label}: **{rendered}**."

    def _matches_designation_filter(self, question: str, tree: dict = None) -> str | None:
        q = self._normalize(question)
        if not q:
            return None

        # 1. Dynamically extract all available designations from the data tree if present
        if isinstance(tree, dict):
            reportees = tree.get("reportees")
            if isinstance(reportees, list):
                tree_designations = {
                    self._normalize(r.get("DESIGNATION_CATEGORY", ""))
                    for r in reportees
                    if isinstance(r, dict) and r.get("DESIGNATION_CATEGORY")
                }
                # Sort by length descending so longer phrases match first (e.g. "senior executive" before "executive")
                for desig in sorted(tree_designations, key=len, reverse=True):
                    if desig and (desig in q or desig.rstrip("s") in q):
                        return desig

        # 2. General fallback for standard designation patterns in descending length order
        standard_designations = [
            "senior executive",
            "executive",
            "intern",
            "manager",
            "team leader",
            "lead",
            "director",
        ]
        for desig in standard_designations:
            if desig in q or desig.rstrip("s") in q:
                return desig

        return None

    def _filter_reportees(self, tree: dict, designation_filter: str):
        reportees = tree.get("reportees")
        if not isinstance(reportees, list):
            return tree

        target = self._normalize(designation_filter)
        filtered = [
            r
            for r in reportees
            if isinstance(r, dict) and target == self._normalize(r.get("DESIGNATION_CATEGORY", ""))
        ]
        # Fallback to substring inclusion if exact category match found nothing
        if not filtered:
            filtered = [
                r
                for r in reportees
                if isinstance(r, dict) and target in self._normalize(r.get("DESIGNATION_CATEGORY", ""))
            ]

        return {
            **tree,
            "reportees": filtered,
        }

    # ----------------------------------------------------------
    # Main generate
    # ----------------------------------------------------------

    def generate(
        self,
        question: str,
        api_response,
        intent: str = None,
        response_metrics: list = None,
        direct_metric: bool = False,
    ) -> dict:
        if isinstance(api_response, dict):
            data = api_response.get("data")
            if isinstance(data, dict):
                lists = [v for v in data.values() if isinstance(v, list)]
                if lists and all(len(lst) == 0 for lst in lists):
                    return {
                        "status": "success",
                        "pipeline": "live_data",
                        "reply": "No data available for the selected date range. Please provide another date range.",
                        "table": "",
                        "table_rows": {},
                        "data": api_response,
                    }
            elif isinstance(data, list) and len(data) == 0:
                return {
                    "status": "success",
                    "pipeline": "live_data",
                    "reply": "No data available for the selected date range. Please provide another date range.",
                    "table": "",
                    "table_rows": {},
                    "data": api_response,
                }

            data1 = api_response.get("data1")
            totals = api_response.get("totals", {})
            if isinstance(data1, list) and len(data1) == 0 and isinstance(totals, dict):
                zero_totals = all(
                    str(v) in ("00:00:00", "0", 0, 0.0)
                    for v in totals.values()
                )
                if zero_totals:
                    return {
                        "status": "success",
                        "pipeline": "live_data",
                        "reply": "No data available for the selected date range. Please provide another date range.",
                        "table": "",
                        "table_rows": {},
                        "data": api_response,
                    }

        elif isinstance(api_response, list) and len(api_response) == 0:
            return {
                "status": "success",
                "pipeline": "live_data",
                "reply": "No data available for the selected date range. Please provide another date range.",
                "table": "",
                "table_rows": {},
                "data": api_response,
            }

        if isinstance(api_response, dict):
            tree = api_response.get("tree")
            if isinstance(tree, dict):
                # 1. User Profile Details Intent
                if intent == "user_profile_details":
                    user_info = tree.get("loggedIn")
                    if isinstance(user_info, dict) and user_info:
                        profile_rows = []
                        if user_info.get("EMPID"):
                            profile_rows.append({"Field": "Employee ID", "Value": str(user_info["EMPID"])})
                        if user_info.get("EMPNAME"):
                            profile_rows.append({"Field": "Name", "Value": str(user_info["EMPNAME"]).strip()})
                        if user_info.get("DESIGNATION_CATEGORY"):
                            profile_rows.append({"Field": "Designation", "Value": str(user_info["DESIGNATION_CATEGORY"]).strip()})
                        if user_info.get("DEPARTMENT"):
                            profile_rows.append({"Field": "Department", "Value": str(user_info["DEPARTMENT"]).strip()})
                        if user_info.get("EMAIL"):
                            profile_rows.append({"Field": "Email", "Value": str(user_info["EMAIL"]).strip()})
                        if user_info.get("manager_name"):
                            profile_rows.append({"Field": "Reporting Manager", "Value": str(user_info["manager_name"]).strip()})

                        name = user_info.get("EMPNAME", "").strip()
                        reply_greeting = f"Here are your profile details, **{name}**:" if name else "Here are your profile details:"

                        return {
                            "status": "success",
                            "pipeline": "live_data",
                            "reply": reply_greeting,
                            "table": "",
                            "table_rows": {},
                            "data": {
                                "profile": profile_rows
                            },
                        }

                # 2. Reporting Manager Intent
                elif intent == "reporting_manager_view":
                    mgr = tree.get("manager")
                    if isinstance(mgr, dict) and mgr:
                        manager_rows = []
                        if mgr.get("EMPNAME"):
                            manager_rows.append({"Field": "Manager Name", "Value": str(mgr["EMPNAME"]).strip()})
                        if mgr.get("EMPID"):
                            manager_rows.append({"Field": "Manager ID", "Value": str(mgr["EMPID"])})
                        if mgr.get("DESIGNATION_CATEGORY"):
                            manager_rows.append({"Field": "Designation", "Value": str(mgr["DESIGNATION_CATEGORY"]).strip()})
                        if mgr.get("DEPARTMENT"):
                            manager_rows.append({"Field": "Department", "Value": str(mgr["DEPARTMENT"]).strip()})
                        if mgr.get("EMAIL"):
                            manager_rows.append({"Field": "Email", "Value": str(mgr["EMAIL"]).strip()})

                        mgr_name = mgr.get("EMPNAME", "").strip()
                        reply_text = f"Your reporting manager is **{mgr_name}**." if mgr_name else "Here are your manager details:"

                        return {
                            "status": "success",
                            "pipeline": "live_data",
                            "reply": reply_text,
                            "table": "",
                            "table_rows": {},
                            "data": {
                                "manager_details": manager_rows
                            },
                        }

                # 3. Otherwise, check designation filtering on reportees
                designation_filter = self._matches_designation_filter(question, tree)
                if designation_filter:
                    api_response = {
                        **api_response,
                        "tree": self._filter_reportees(tree, designation_filter),
                    }

        # Registry metadata enables exact answers for simple single-metric
        # requests without another model generation. Other requests retain
        # the existing natural-language generation path.
        reply = self._schema_answer(
            question, api_response, response_metrics, direct_metric
        )
        if reply is None:
            reply = self._generate_llm_reply(question, api_response)

        return {
            "status": "success",
            "pipeline": "live_data",
            "reply": reply,
            "table": "",
            "table_rows": {},
            "data": api_response,
        }
