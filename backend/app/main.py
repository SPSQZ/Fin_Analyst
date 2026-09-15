from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from supabase_auth.types import User

from app.auth.dependencies import get_current_user
from app.chat import router as chat_router
from app.config import settings

app = FastAPI(title="Document Copilot")
current_user_dependency = Depends(get_current_user)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/me")
async def get_me(
    current_user: Annotated[User, current_user_dependency],
) -> dict[str, str | None]:
    return {"id": current_user.id, "email": current_user.email}


app.include_router(chat_router)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
