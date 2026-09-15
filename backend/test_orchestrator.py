import asyncio
import uuid
import os
import sys

from app.config import settings
os.environ["GEMINI_API_KEY"] = settings.gemini_api_key

from app.database.session import SessionLocal
from app.chat.orchestrator import process_chat_turn

async def main():
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "What is Apple's total revenue in 2024?"
        
    print(f"Query: {query}")
    thread_id = uuid.uuid4()
    
    with SessionLocal() as db:
        from app.database.models.chat_thread import ChatThread
        from app.database.models.user import User
        # Check if a user exists, or create one
        user = db.query(User).first()
        if not user:
            user = User(email="test@example.com")
            db.add(user)
            db.commit()
            
        thread = ChatThread(id=thread_id, user_id=user.id, title="Test Thread")
        db.add(thread)
        db.commit()
        
        print("Generating response...")
        async for chunk in process_chat_turn(db, thread_id, query):
            # Print the raw SSE chunks
            print(chunk, end="")
            
        print("\n\n--- Done ---")

if __name__ == "__main__":
    asyncio.run(main())
