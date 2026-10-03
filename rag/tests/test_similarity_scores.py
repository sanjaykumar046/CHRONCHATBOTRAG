from rag.services.api_registry_service import APIRegistryService
from rag.services.intent_retriever import IntentRetriever

registry = APIRegistryService().get_all()
retriever = IntentRetriever(registry)

test_questions = [
    # (question, expected_intent_name)
    ("how many hours did I work today", "employee_activity_summary"),
    ("show my team's activity for this week", "employee_activity_summary"),
    ("who is on leave tomorrow", "upcoming_leave_schedule"),
    ("apply for leave next monday", "apply_leave"),
    ("show attendance for CL00262", "attendance_summary"),
    ("what websites is john browsing", "employee_website_activity"),
    ("who are the top performers this month", "top_productive_users"),
    ("show my reporting manager", "reporting_manager_view"),
    ("what's the weather today", None),  # should NOT match anything
    ("tell me a joke", None),  # should NOT match anything
]

for question, expected in test_questions:
    results = retriever.get_top_candidates_with_scores(question, k=5)
    print("=" * 80)
    print(f"Q: {question}")
    print(f"Expected: {expected}")
    for entry, score in results:
        marker = "✅" if entry["Intent Name"] == expected else "  "
        print(f"{marker} {score:.4f}  {entry['Intent Name']}")