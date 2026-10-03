import sys
import os
sys.path.insert(0, ".")

from rag.services.question_analyzer import QuestionAnalyzer

qa = QuestionAnalyzer()
q = "show my deparatement logged hours on 06-01-2026"
scores = qa.retriever.get_top_candidates_with_scores(q, k=10)
print("--- RETRIEVER TOP CANDIDATES WITH SCORES ---")
for entry, score in scores:
    print(f"[{score:.4f}] {entry.get('Intent Name')}")

print("\n--- ANALYZE RESULT ---")
res = qa.analyze(q)
print("RESULT:", res)

