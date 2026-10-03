from rag.classifier.intent_classifier import IntentClassifier

classifier = IntentClassifier()

questions = [
    "How can I raise an issue?",
    "Explain the Attendance page.",
    "How does Pulse work?",
    "What is my attendance today?",
    "How many leave days do I have?",
    "Show my productivity for this week.",
    "Hi",
    "Good morning",
    "Tell me a joke."
]

for question in questions:

    result = classifier.classify(question)

    print("=" * 80)
    print("Question :", question)
    print(result)