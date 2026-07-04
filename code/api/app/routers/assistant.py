"""Personal assistant ("Aadyon Assist") endpoints: conversations + chat (sync + SSE).

Protected by get_current_user (wired in main.py), which binds the RLS context so
every query here is scoped to the signed-in user.
"""
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from uuid import UUID

from app.db.session import query
from app.services import assistant
from app.services.llm import LLMError

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


def _title_from(text: str) -> str:
    t = " ".join(text.split())
    return (t[:60] + "…") if len(t) > 60 else t


@router.get("/conversations")
def list_conversations():
    return query("SELECT * FROM conversations ORDER BY updated_at DESC LIMIT 100")


@router.post("/conversations")
def new_conversation(payload: dict | None = None):
    return assistant.create_conversation((payload or {}).get("title"))


@router.get("/conversations/{cid}/messages")
def conversation_messages(cid: UUID):
    # RLS scopes this to the owner; unknown/foreign ids simply return [].
    return query(
        "SELECT id, role, content, tool_name, created_at FROM messages "
        "WHERE conversation_id = %s ORDER BY created_at ASC",
        (str(cid),),
    )


def _resolve(payload: dict) -> tuple[str, str]:
    text = (payload or {}).get("message", "").strip()
    if not text:
        raise HTTPException(400, "Provide a 'message'.")
    cid = (payload or {}).get("conversation_id")
    if not cid:
        cid = str(assistant.create_conversation(_title_from(text))["id"])
    return cid, text


@router.post("/chat")
def chat(payload: dict):
    cid, text = _resolve(payload)
    try:
        result = assistant.run(cid, text)
    except assistant.ConversationNotFound as e:
        raise HTTPException(404, "Conversation not found") from e
    except LLMError as e:
        raise HTTPException(503, str(e)) from e
    return {"conversation_id": cid, **result}


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, default=str)}\n\n"


@router.post("/chat/stream")
def chat_stream(payload: dict):
    """SSE variant. Tool rounds run server-side; the reply is streamed in chunks,
    then a terminal event carries the actions taken and any proposals queued.
    (True token-by-token LLM streaming is a planned fast-follow.)"""
    cid, text = _resolve(payload)

    def gen():
        try:
            for chunk in assistant.run_stream(cid, text):
                yield _sse(chunk)
        except assistant.ConversationNotFound:
            yield _sse({"error": "conversation not found"})
        except LLMError as e:
            yield _sse({"error": str(e)})
        # Last resort: an escaped exception here resets the connection mid-stream
        # (the client sees a network error, not a message) — end with an SSE error.
        except Exception as e:
            yield _sse({"error": f"{type(e).__name__}: {e}"})

    return StreamingResponse(gen(), media_type="text/event-stream")
