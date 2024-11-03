from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from server.routers import user, llm

app = FastAPI(title="NeYapAI API")

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(user.router)
app.include_router(llm.router)

# Statik dosyaları mount et
app.mount("/images", StaticFiles(directory=Path(__file__).parent.parent / "images"), name="images")

@app.get("/")
async def root():
    return {"message": "AI Suppported Learning API"}
