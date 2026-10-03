from fastapi import APIRouter
from rag.api.models import ChatRequest
from rag.chronai import ChronAI

router = APIRouter()

chronai = ChronAI()


@router.post("/chat")
def chat(request: ChatRequest):

    print("=" * 80)
    print("INCOMING REQUEST:", request.model_dump())
    print("=" * 80)

    result = chronai.process(
        request.model_dump()
    )

    return result