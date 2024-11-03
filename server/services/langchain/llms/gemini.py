from langchain_google_genai import ChatGoogleGenerativeAI
from server.config import settings

def build_llm():
    return ChatGoogleGenerativeAI(
        api_key=settings.GEMINI_API_KEY,
        model="gemini-1.5-pro",
        temperature=0.7,
        top_p=0.8,
        top_k=40,
        max_output_tokens=2048,
        verbose=True
    )

build_llm()
