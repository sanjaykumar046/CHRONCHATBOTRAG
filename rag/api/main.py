import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chronai.settings")
django.setup()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rag.api.routes import router

app = FastAPI(
    title="ChronAI API",
    version="1.0.0"
)

# Allow React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Later replace with your React URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)