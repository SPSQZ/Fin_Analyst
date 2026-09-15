import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth.dependencies import get_current_user
from supabase_auth.types import User as SupabaseUser
from app.database.session import get_db
from app.database.models.chat_thread import ChatThread
from app.database.models.chat_message import ChatMessage
from app.database.models.user import User

client = TestClient(app)

TEST_USER_ID = str(uuid.uuid4())

def mock_get_current_user():
    return SupabaseUser(
        id=TEST_USER_ID,
        app_metadata={},
        user_metadata={},
        aud="authenticated",
        created_at="2026-01-01T00:00:00Z",
        email="test_analyst@firm.internal",
    )

app.dependency_overrides[get_current_user] = mock_get_current_user

def test_create_and_delete_thread():
    # 1. Create a thread
    res = client.post("/chat/threads", json={"title": "Thread to Delete"})
    assert res.status_code == 201, res.text
    thread_data = res.json()
    thread_id = thread_data["id"]

    # 2. Verify it exists in list
    list_res = client.get("/chat/threads")
    assert list_res.status_code == 200
    ids = [t["id"] for t in list_res.json()]
    assert thread_id in ids

    # 3. Delete the thread
    del_res = client.delete(f"/chat/threads/{thread_id}")
    assert del_res.status_code == 204, del_res.text

    # 4. Verify it is gone
    list_res2 = client.get("/chat/threads")
    ids2 = [t["id"] for t in list_res2.json()]
    assert thread_id not in ids2

    # 5. Calling get on deleted thread should fail with 403 or 404
    get_res = client.get(f"/chat/threads/{thread_id}")
    assert get_res.status_code in (403, 404)
