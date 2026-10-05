"""Main entry point for ChronAI chat requests."""

from rag.router.request_router import RequestRouter
from rag.services.request_analysis_service import RequestAnalysisService
from rag.services.session_store import SessionStore


class ChronAI:
    def __init__(self):
        self.request_analyzer = RequestAnalysisService()
        self.request_router = RequestRouter()
        self.session_store = SessionStore()

    def process(self, request: dict):
        question = request.get("message", "").strip()
        if not question:
            return {
                "status": "error",
                "message": "Question is required.",
            }

        user = {
            "userid": request.get("userid"),
            "access_role": request.get("access_role"),
        } if request.get("userid") or request.get("access_role") else None
        session = request.get("session_id")
        current_userid = user.get("userid") if user else None

        # A pending parameter reply already has its intent and context, so it
        # bypasses new-request analysis and continues the saved pipeline.
        if self.request_router.has_pending_session(session, userid=current_userid):
            response = self.request_router.route_pending_reply(
                request=request,
                user=user,
                session=session,
            )
            if isinstance(response, dict) and response.get("status") == "success":
                reply_text = response.get("reply") or response.get("message") or "Completed."
                self.session_store.save_turn(session, question, reply_text, userid=current_userid)
            return {
                "status": "success",
                "original_question": question,
                "normalized_question": question,
                "classification": None,
                "response": response,
            }

        history = self.session_store.get_history(session, userid=current_userid)
        analysis = self.request_analyzer.analyze(question, history=history)
        if analysis.get("status") != "success":
            return {
                "status": "error",
                "original_question": question,
                "normalized_question": question,
                "classification": None,
                "response": analysis,
            }

        normalized_question = analysis["normalized_question"]
        classification = {
            "category": analysis["category"],
            "intent": analysis["intent"],
            "normalized_question": normalized_question,
            "category_confidence": analysis.get("confidence"),
            "category_reason": analysis.get("reason"),
            "intent_confidence": analysis.get("confidence"),
            "intent_reason": analysis.get("reason"),
        }

        request["message"] = normalized_question
        request["_request_analysis"] = analysis
        response = self.request_router.route(
            classification=classification,
            request=request,
            user=user,
            session=session,
        )

        if isinstance(response, dict) and response.get("status") == "success":
            reply_text = (
                response.get("reply")
                or response.get("message")
                or (response.get("data", {}) if isinstance(response.get("data"), dict) else {}).get("answer")
                or "Here are the results."
            )
            self.session_store.save_turn(
                session_id=session,
                user_message=question,
                bot_reply=reply_text,
                userid=current_userid,
            )

        return {
            "status": "success",
            "original_question": question,
            "normalized_question": normalized_question,
            "classification": classification,
            "response": response,
        }
