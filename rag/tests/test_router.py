from rag.router.request_router import RequestRouter

router = RequestRouter()

intent = {
    "intent": "knowledge",
    "confidence": 0.98
}

request = {
    "message": "How can I raise an issue?"
}

response = router.route(intent, request)

print(response)