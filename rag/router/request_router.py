from rag.pipelines.knowledge_pipeline import KnowledgePipeline
from rag.pipelines.small_talk_pipeline import SmallTalkPipeline
from rag.pipelines.off_talk_pipeline import OffTalkPipeline
from rag.pipelines.live_data_pipeline import LiveDataPipeline


class RequestRouter:

    def __init__(self):
        self.knowledge_pipeline = KnowledgePipeline()
        self.small_talk_pipeline = SmallTalkPipeline()
        self.off_talk_pipeline = OffTalkPipeline()
        self.live_data_pipeline = LiveDataPipeline()

    def has_pending_session(self, session_id, userid=None) -> bool:
        if not session_id and not userid:
            return False
        return self.live_data_pipeline.session_store.load(session_id, userid=userid) is not None

    def route_pending_reply(self, request: dict, user=None, session=None):
        """
        Sends a reply straight to the pipeline that owns the pending
        session, bypassing category/intent classification entirely.
        """
        return self._live_data_pipeline(
            request=request,
            user=user,
            session=session
        )

    def route(self, classification: dict, request: dict, user=None, session=None):

        category = classification.get("category")
        normalized_question = classification.get("normalized_question", "")

        if category == "small_talk":
            return self.small_talk_pipeline.execute(request, normalized_question)

        elif category == "off_talk":
            return self.off_talk_pipeline.execute(request, normalized_question)

        elif category == "on_talk":
            return self._on_talk_pipeline(classification, request, user, session)

        return {
            "status": "error",
            "message": "Unknown category."
        }

    def _on_talk_pipeline(self, classification, request, user=None, session=None):

        intent_name = classification.get("intent")

        if intent_name == "knowledge":
            return self.knowledge_pipeline.execute(request)

        elif intent_name == "live_data":
            return self._live_data_pipeline(
                request=request,
                user=user,
                session=session
            )

        return {
            "status": "error",
            "message": "Unknown intent for on_talk category."
        }

    def _live_data_pipeline(self, request, user=None, session=None):
        return self.live_data_pipeline.execute(
            request=request,
            user=user,
            session=session
        )