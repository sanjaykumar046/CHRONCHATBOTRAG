class OffTalkPipeline:

    DEFAULT_MESSAGE = (
        "I'm ChronAI's assistant and I can only help with questions "
        "related to this application. I'm not able to discuss that topic."
    )

    def execute(self, request: dict, normalized_question: str) -> dict:

        return {
            "status": "success",
            "pipeline": "off_talk",
            "message": self.DEFAULT_MESSAGE
        }