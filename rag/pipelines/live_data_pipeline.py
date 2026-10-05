from datetime import date

from rag.services.parameter_service import ParameterService
from rag.services.api_service import APIService
from rag.services.response_service import ResponseService
from rag.services.session_store import SessionStore
from rag.services.rbac_service import RbacService


class LiveDataPipeline:

    def __init__(self):
        self.parameter_service = ParameterService()
        self.api_service = APIService()
        self.response_service = ResponseService()
        self.session_store = SessionStore()
        self.rbac_service = RbacService()

    def execute(self, request, user=None, session=None):

        question = (
            request.get("message")
            or request.get("normalized_question")
            or request.get("question")
        )

        if not question:
            return {
                "status": "error",
                "message": "Question is required."
            }

        if user is None:
            user = {
                "userid": request.get("userid"),
                "access_role": request.get("access_role")
            }

        session_id = request.get("session_id")
        userid = (user or {}).get("userid")
        response_mode = "narrative"

        # ---------------------------------------------
        # Check for a pending ASK_USER context first.
        # ---------------------------------------------

        pending = self.session_store.load(session_id, userid=userid)

        if pending:
            registry_entry = pending["registry"]
            parameters = pending["parameters"]

            rbac_result = self.rbac_service.check(user, registry_entry)
            if rbac_result["status"] != "success":
                self.session_store.clear(session_id, userid=userid)
                return rbac_result

            merged = self._merge_reply_into_missing(
                question=question,
                missing=pending["missing"],
                parameters=parameters,
                user=user
            )

            parameters = merged

        else:
            # RequestAnalysisService already selected and validated the
            # registry entry in the single pre-fetch LLM call.
            analysis = request.get("_request_analysis")
            if not isinstance(analysis, dict) or not isinstance(analysis.get("registry"), dict):
                return {
                    "status": "error",
                    "message": "Live-data analysis is missing a validated registry entry.",
                }

            registry_entry = analysis["registry"]
            response_mode = analysis.get("response_mode", "narrative")

            # ---------------------------------------------
            # Enforce intent-level permissions before parameter resolution
            # and before contacting the backend API.
            # ---------------------------------------------
            rbac_result = self.rbac_service.check(user, registry_entry)
            if rbac_result["status"] != "success":
                return rbac_result

            # ---------------------------------------------
            # Stage 2 - Parameter Resolution
            # ---------------------------------------------
            params_result = self.parameter_service.resolve(
                question=question,
                registry=registry_entry,
                user=user,
                extracted=analysis.get("parameters", {}),
                evidence_question=analysis.get("parameter_evidence", question),
                source_question=analysis.get("source_question", question),
            )

            if params_result["status"] != "success":
                return params_result

            parameters = params_result["parameters"]

            # ---------------------------------------------
            # Stage 2b - Data Scope Enforcement
            # Ensures EXECUTIVE sees only themselves,
            # LEADERSHIP sees only self + direct reportees,
            # ADMIN/SUPER_ADMIN see everyone.
            # ---------------------------------------------
            scope_result = self.rbac_service.enforce_scope(user, parameters)
            if scope_result["status"] != "success":
                return scope_result
            parameters = scope_result["parameters"]

        # ---------------------------------------------
        # Stage 3 - Parameter Validation
        # ---------------------------------------------
        validation = self.parameter_service.validate(
            registry=registry_entry,
            parameters=parameters
        )

        if validation["status"] == "missing_parameters":
            missing = validation["missing"]

            self.session_store.save(session_id, {
                "registry": registry_entry,
                "parameters": parameters,
                "missing": missing
            }, userid=userid)

            return {
                "status": "ask_user",
                "message": self._build_ask_user_message(missing),
                "missing": missing,
                "intent": registry_entry.get("Intent Name")
            }

        if validation["status"] != "success":
            return validation

        # Validation passed - clear any pending session context
        self.session_store.clear(session_id, userid=userid)

      # ---------------------------------------------
        # Stage 4 - API Call
        # ---------------------------------------------
        import time
        t0 = time.time()

        api_result = self.api_service.execute(
            registry=registry_entry,
            parameters=parameters
        )

        t1 = time.time()
        print(f"[TIMING] API call took {t1 - t0:.2f}s")

        if api_result["status"] != "success":
            self.session_store.clear(session_id, userid=userid)
            return api_result

        print("=" * 80)
        print("RAW API RESPONSE (before LLM)")
        import json
        print(json.dumps(api_result["data"], indent=2, default=str)[:3000])
        print("=" * 80)

        # If PHP returned an error inside a 200 response, clear session and return error
        if isinstance(api_result["data"], dict) and api_result["data"].get("error"):
            self.session_store.clear(session_id, userid=userid)
            return {
                "status": "error",
                "message": api_result["data"]["error"]
            }

        if registry_entry.get("Intent Name") == "last_leave_taken":
            leave_response = api_result["data"]

            if isinstance(leave_response, dict) and leave_response.get("success") is False:
                return {
                    "status": "error",
                    "message": leave_response.get("message") or "The leave service could not retrieve your leave history."
                }

            leave_records = (
                leave_response.get("data", [])
                if isinstance(leave_response, dict)
                else []
            )
            today = date.today().isoformat()
            if not isinstance(leave_records, list):
                leave_records = []

            completed_approved = [
                record for record in leave_records
                if isinstance(record, dict)
                and str(record.get("status", "")).strip().upper() == "APPROVED"
                and str(record.get("toDate", ""))[:10]
                and str(record.get("toDate", ""))[:10] < today
            ]
            completed_approved.sort(
                key=lambda record: (
                    str(record.get("toDate", ""))[:10],
                    str(record.get("createdAt", "")),
                ),
                reverse=True,
            )

            if not completed_approved:
                return {
                    "status": "success",
                    "pipeline": "live_data",
                    "reply": "I couldn't find a completed, approved leave record in your history.",
                    "table": "",
                    "table_rows": {},
                    "data": {"leave_records": []},
                }

            # Keep the final answer grounded in just the latest past,
            # approved leave instead of asking the LLM to infer it from all history.
            latest_leave_data = {
                **leave_response,
                "data": [completed_approved[0]],
            }
            api_result["data"] = latest_leave_data

        # ---------------------------------------------
        # Stage 5 - Final Response (LLM turns API data into an answer)
        # ---------------------------------------------
        t2 = time.time()

        result = self.response_service.generate(
            question=question,
            api_response=api_result["data"],
            intent=registry_entry.get("Intent Name"),
            response_metrics=registry_entry.get("Response Metrics"),
            direct_metric=response_mode == "direct_metric",
        )

        t3 = time.time()
        print(f"[TIMING] LLM response generation took {t3 - t2:.2f}s")
        print(f"[TIMING] TOTAL live_data pipeline time: {t3 - t0:.2f}s")

        return result

    def _merge_reply_into_missing(self, question: str, missing: list, parameters: dict, user: dict = None) -> dict:
        """
        If there's exactly one missing field, treat the whole reply as
        its value. If there are multiple missing fields, re-run
        parameter extraction on the reply so each field can potentially
        be filled from the same message (e.g. "CL00262, 2026-01-15"
        answering both an employee ID and a date field at once).
        Falls back to filling only the first missing field if
        extraction finds nothing.
        """
        updated = dict(parameters)

        if len(missing) == 1:
            updated[missing[0]] = question.strip()
            return updated

        extracted = self.parameter_service.extract(
            question=question,
            parameter_names=missing,
            user=user
        )

        if extracted:
            updated.update(extracted)
        else:
            updated[missing[0]] = question.strip()

        return updated

    def _build_ask_user_message(self, missing: list) -> str:
        lines = "\n".join(f"- {field}" for field in missing)
        return f"Please provide the following:\n{lines}"
