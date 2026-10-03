from rag.services.chat_service import ChatService

chat = ChatService()

question = "How can an employee raise an issue?"

result = chat.ask(question)

print("=" * 80)

print("QUESTION")
print(result["question"])

print()

print("ANSWER")
print(result["answer"])

print()

print("SOURCES")

for source in result["sources"]:
    print(
        f"{source['module']} -> {source['page']}"
    )