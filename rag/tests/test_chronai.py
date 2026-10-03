from rag.chronai import ChronAI

chronai = ChronAI()

request = {
    "message": "How can I raise an issue?"
}

response = chronai.process(request)

print(response)