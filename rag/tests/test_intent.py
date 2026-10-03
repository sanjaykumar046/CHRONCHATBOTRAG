from rag.classifier.intent_classifier import IntentClassifier

classifier = IntentClassifier()

question = "hw cn i ras an isu"

result = classifier.classify(question)

print(result)