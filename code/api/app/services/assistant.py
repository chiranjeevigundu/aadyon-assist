"""The personal assistant ("Aadyon Assist") — a conversational, tool-using chat engine.

Modeled on agency.run_task: a bounded tool-calling loop over the routed model.
Unlike the org agents, the assistant may WRITE the user's own records directly
(create/update/delete deadlines, bills, debts, subscriptions, milestones, profile);
external side effects still go through propose_action (human approval). Every turn
is persisted to `messages`, all RLS-scoped to the current user.
"""
import json
from datetime import date

from app.core.config import get_settings
from app.db.session import current_user_id, query, query_unscoped
from app.services import routing, tools
from app.services.llm import chat

_ASSISTANT_TYPE = "assistant"
_CONTENT_CAP = 8000


class ConversationNotFound(RuntimeError):
    pass


def _system_prompt() -> str:
    uid = current_user_id()
    rows = query_unscoped("SELECT display_name, email FROM users WHERE id = %s", (uid,)) if uid else []
    user_info = rows[0] if rows else {}
    name = user_info.get("display_name") or user_info.get("email") or "the user"

    return (
        f"You are Aadyon Assist, the personal life-ops assistant for {name}. Today is {date.today()}. "
        f"You manage {name}'s Digital Me: deadlines, debts, bills, subscriptions, milestones, "
        "their profile, and an agent org. Always call get_snapshot for real numbers — never invent "
        "them. You MAY directly create, update, or delete the user's own records with the write "
        "tools (e.g. create_deadline, update_bill, update_profile) — do it when asked and confirm "
        "what changed, mentioning the affected item. For anything with a real-world EXTERNAL side "
        "effect — moving money, sending an email, filing a form — you MUST use propose_action, which "
        "queues it for the user's approval and does NOT execute. If the user asks you to process or "
        "update their profile based on a recently uploaded document, use get_recent_documents and "
        "read_document to read it. "
        "Dimension scores come from tracked data, not profile labels: the Goal score is the average "
        "progress_pct of open milestones, and Career scores job applications + current_income vs "
        "target_salary. To set a goal, call ONLY update_profile with goal_title/goal_target_date — "
        "that automatically creates the tracking milestone at 0%; do NOT also call create_milestone "
        "for that same goal (it would duplicate it). When the user reports progress toward a goal, "
        "update the matching milestone's progress_pct; if a score looks low, explain what would move it. "
        f"Proactively gather details from interactions, update {name}'s Digital Me profile based on them, "
        "and ask clarifying questions to fill in missing information, just like a human personal assistant. "
        "Be concrete, warm, and brief."
    )


# --------------------------------------------------------------------------- conversations
def create_conversation(title: str | None = None) -> dict:
    rows = query(
        "INSERT INTO conversations (user_id, title) VALUES (%s,%s) RETURNING *",
        (current_user_id(), title), commit=True,
    )
    return rows[0]


def _require_conversation(conversation_id) -> None:
    # RLS-scoped: only the owner's conversation is visible.
    if not query("SELECT id FROM conversations WHERE id = %s", (conversation_id,)):
        raise ConversationNotFound("conversation not found")


def _load_history(conversation_id) -> list[dict]:
    rows = query(
        "SELECT role, content, tool_calls, tool_call_id, tool_name FROM messages "
        "WHERE conversation_id = %s ORDER BY created_at ASC",
        (conversation_id,),
    )
    out: list[dict] = []
    for r in rows:
        if r["role"] == "assistant":
            m: dict = {"role": "assistant", "content": r["content"] or ""}
            if r["tool_calls"]:
                m["tool_calls"] = r["tool_calls"]
            out.append(m)
        elif r["role"] == "tool":
            out.append({"role": "tool", "tool_call_id": r["tool_call_id"],
                        "content": r["content"] or ""})
        else:
            out.append({"role": "user", "content": r["content"] or ""})
    return out


def _save(conversation_id, role, content=None, tool_calls=None, tool_call_id=None, tool_name=None):
    query(
        "INSERT INTO messages (user_id, conversation_id, role, content, tool_calls, "
        "tool_call_id, tool_name) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (current_user_id(), conversation_id, role, (content or "")[:_CONTENT_CAP] or None,
         json.dumps(tool_calls) if tool_calls is not None else None, tool_call_id, tool_name),
        commit=True,
    )
    # bump conversation so lists sort by recency
    query("UPDATE conversations SET updated_at = now() WHERE id = %s", (conversation_id,), commit=True)


# --------------------------------------------------------------------------- the loop
def run(conversation_id, user_text: str) -> dict:
    """One user turn -> the assistant's reply, plus any actions taken / proposals queued.

    Raises ConversationNotFound (404) or llm.LLMError (503) to the caller.
    """
    _require_conversation(conversation_id)
    _save(conversation_id, "user", user_text)

    route = routing.resolve("reasoning")
    provider, model = route["provider"], route["model"]
    tool_schemas = tools.schemas_for(_ASSISTANT_TYPE) if provider == "openrouter" else None

    messages = [{"role": "system", "content": _system_prompt()}] + _load_history(conversation_id)
    proposals: list[dict] = []
    actions: list[str] = []
    ctx = {"user_id": current_user_id()}

    # No tool-calling provider (e.g. Ollama): single completion, no writes.
    if not tool_schemas:
        resp = chat(provider, model, messages, None, route["temperature"])
        reply = resp["message"].get("content", "") or "(no reply)"
        _save(conversation_id, "assistant", reply)
        return {"reply": reply, "proposals": proposals, "actions": actions}

    for _step in range(get_settings().agent_max_steps):
        resp = chat(provider, model, messages, tool_schemas, route["temperature"])
        msg = resp["message"]
        tool_calls = msg.get("tool_calls") or []

        if not tool_calls:
            reply = msg.get("content") or "(no reply)"
            _save(conversation_id, "assistant", reply)
            return {"reply": reply, "proposals": proposals, "actions": actions}

        _save(conversation_id, "assistant", msg.get("content"), tool_calls=tool_calls)
        messages.append(msg)
        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = tools.dispatch(name, args, ctx)
            if name == "propose_action" and result.get("proposal_id"):
                proposals.append({"id": result["proposal_id"], "title": args.get("title")})
            elif result.get("ok"):
                actions.append(result.get("action"))
            payload = json.dumps(result, default=str)
            _save(conversation_id, "tool", content=payload, tool_call_id=tc["id"], tool_name=name)
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": payload})

    reply = "(I took several steps but ran out of room — ask me to continue.)"
    _save(conversation_id, "assistant", reply)
    return {"reply": reply, "proposals": proposals, "actions": actions}


def run_stream(conversation_id, user_text: str):
    """Streaming variant of run(). Yields {"delta": ...} and {"done": True, ...}.
    """
    _require_conversation(conversation_id)
    _save(conversation_id, "user", user_text)

    route = routing.resolve("reasoning")
    provider, model = route["provider"], route["model"]
    tool_schemas = tools.schemas_for(_ASSISTANT_TYPE) if provider == "openrouter" else None

    messages = [{"role": "system", "content": _system_prompt()}] + _load_history(conversation_id)
    proposals: list[dict] = []
    actions: list[str] = []
    ctx = {"user_id": current_user_id()}

    if not tool_schemas:
        resp = chat(provider, model, messages, None, route["temperature"], stream=True)
        content_accum = ""
        for chunk in resp:
            delta = chunk.choices[0].delta
            if getattr(delta, "content", None):
                content_accum += delta.content
                yield {"delta": delta.content}
        reply = content_accum or "(no reply)"
        _save(conversation_id, "assistant", reply)
        yield {"done": True, "conversation_id": conversation_id, "proposals": proposals, "actions": actions}
        return

    for _step in range(get_settings().agent_max_steps):
        resp = chat(provider, model, messages, tool_schemas, route["temperature"], stream=True)
        
        tool_calls_dict = {}
        content_accum = ""
        
        for chunk in resp:
            delta = chunk.choices[0].delta
            if getattr(delta, "content", None):
                content_accum += delta.content
                yield {"delta": delta.content}
                
            if getattr(delta, "tool_calls", None):
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_dict:
                        tool_calls_dict[idx] = {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": ""}
                        }
                    if tc.function.arguments:
                        tool_calls_dict[idx]["function"]["arguments"] += tc.function.arguments

        tool_calls = list(tool_calls_dict.values()) if tool_calls_dict else []

        if not tool_calls:
            reply = content_accum or "(no reply)"
            _save(conversation_id, "assistant", reply)
            yield {"done": True, "conversation_id": conversation_id, "proposals": proposals, "actions": actions}
            return

        _save(conversation_id, "assistant", content_accum or None, tool_calls=tool_calls)
        messages.append({"role": "assistant", "content": content_accum or None, "tool_calls": tool_calls})
        
        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = tools.dispatch(name, args, ctx)
            if name == "propose_action" and result.get("proposal_id"):
                proposals.append({"id": result["proposal_id"], "title": args.get("title")})
            elif result.get("ok"):
                actions.append(result.get("action"))
            payload = json.dumps(result, default=str)
            _save(conversation_id, "tool", content=payload, tool_call_id=tc["id"], tool_name=name)
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": payload})

    reply = "(I took several steps but ran out of room — ask me to continue.)"
    _save(conversation_id, "assistant", reply)
    yield {"delta": reply, "done": True, "conversation_id": conversation_id, "proposals": proposals, "actions": actions}
