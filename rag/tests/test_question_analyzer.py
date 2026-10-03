from rag.services.question_analyzer import QuestionAnalyzer

analyzer = QuestionAnalyzer()

test_questions = [
    "Show me pending leave requests",
    "What is our holiday calendar",
    "Who are the top productive employees this month",
    "Show attendance summary for this week",
    "What websites are restricted",
]

for q in test_questions:
    print("=" * 80)
    print("Question:", q)
    result = analyzer.analyze(q)
    print("Status:", result["status"])
    if result["status"] == "success":
        print("Intent:", result["intent"])
        print("Scope:", result["scope"])
        print("Employee Reference:", result["employee_reference"])
        print("Confidence:", result["confidence"])
        print("Reason:", result["reason"])
    else:
        print("Message:", result.get("message"))
        print("Details:", result.get("details"))