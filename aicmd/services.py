import sys
from pathlib import Path
from typing import Optional, Callable, List, Dict
from . import config, providers
import uuid
import sqlite3
from datetime import datetime

# Paths
AICMD_DIR = Path.home() / ".aicmd"
DB_PATH = AICMD_DIR / "chats.db"

# In-memory chat cache (optional, lazy)
_chats: Dict[str, List[Dict[str, str]]] = {}

def _ensure_db():
    AICMD_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id TEXT PRIMARY KEY,
            created_at TEXT
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            role TEXT,
            content TEXT,
            created_at TEXT,
            seq INTEGER,
            FOREIGN KEY(chat_id) REFERENCES chats(chat_id)
        )
        """)
        conn.commit()
    finally:
        conn.close()

# Ensure DB exists on import
_ensure_db()

def _db_conn():
    return sqlite3.connect(DB_PATH)

def _chat_exists(chat_id: str) -> bool:
    conn = _db_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM chats WHERE chat_id = ?", (chat_id,))
        return cur.fetchone() is not None
    finally:
        conn.close()

def summarize_text(
    text: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 256,
    timeout: Optional[int] = None,
    stream_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """Summarize text using the configured or explicitly specified provider."""
    cfg = config.load()
    prov_name = provider or cfg.get("provider") or "ollama"
    prov = providers.get_provider(prov_name)
    if not prov:
        raise ValueError(f"No provider configured or found for '{prov_name}'")

    effective_timeout = timeout if timeout is not None else cfg.get("timeout", 300)
    
    # Use the model string directly (do not look it up as a config key)
    resolved_model = model or None
    
    return prov.summarize(
        text,
        model=resolved_model,
        max_tokens=max_tokens,
        timeout=effective_timeout,
        stream_callback=stream_callback,
    )

def describe_image(
    image_path: Path,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 256,
    timeout: Optional[int] = None,
) -> str:
    """Describe an image using the configured or explicitly specified provider."""
    cfg = config.load()
    prov_name = provider or cfg.get("provider") or "ollama"
    prov = providers.get_provider(prov_name)
    if not prov:
        raise ValueError(f"No provider configured or found for '{prov_name}'")

    if not hasattr(prov, "describe_image"):
        raise NotImplementedError(f"Selected provider '{prov_name}' does not support image description")

    effective_timeout = timeout if timeout is not None else cfg.get("timeout", 300)
    
    # Use the model string directly (do not look it up as a config key)
    resolved_model = model or None

    return prov.describe_image(
        str(image_path),
        max_tokens=max_tokens,
        timeout=effective_timeout,
        model=resolved_model,
    )

def rewrite_text(
    text: str,
    style: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 256,
    timeout: Optional[int] = None,
    stream_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """Rewrite text in a given style using the configured or explicitly specified provider."""
    cfg = config.load()
    prov_name = provider or cfg.get("provider") or "ollama"
    prov = providers.get_provider(prov_name)
    if not prov:
        raise ValueError(f"No provider configured or found for '{prov_name}'")

    effective_timeout = timeout if timeout is not None else cfg.get("timeout", 300)

    # Use the model string directly (do not look it up as a config key)
    resolved_model = model or None

    return prov.rewrite(
        text,
        style,
        model=resolved_model,
        max_tokens=max_tokens,
        timeout=effective_timeout,
        stream_callback=stream_callback,
    )

# Chat-related helpers

def create_chat(chat_id: Optional[str] = None) -> str:
    """Create a new chat and return its id. If chat_id is provided and doesn't exist, create it."""
    cid = chat_id or uuid.uuid4().hex
    now = datetime.utcnow().isoformat() + 'Z'
    conn = _db_conn()
    try:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO chats (chat_id, created_at) VALUES (?, ?)", (cid, now))
        conn.commit()
    finally:
        conn.close()
    # initialize in-memory cache entry
    _chats.setdefault(cid, [])
    return cid

def append_message(chat_id: str, role: str, content: str) -> None:
    """Append a message to the chat (persisted in sqlite)."""
    if not _chat_exists(chat_id):
        raise KeyError(f"Unknown chat id: {chat_id}")
    conn = _db_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(seq), 0) FROM messages WHERE chat_id = ?", (chat_id,))
        row = cur.fetchone()
        seq = (row[0] or 0) + 1
        now = datetime.utcnow().isoformat() + 'Z'
        cur.execute(
            "INSERT INTO messages (chat_id, role, content, created_at, seq) VALUES (?, ?, ?, ?, ?)",
            (chat_id, role, content, now, seq)
        )
        conn.commit()
    finally:
        conn.close()
    # update cache
    _chats.setdefault(chat_id, []).append({"role": role, "content": content})

def get_chat_history(chat_id: str):
    """Return ordered list of messages for chat_id from the database."""
    if not _chat_exists(chat_id):
        return []
    conn = _db_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT role, content FROM messages WHERE chat_id = ? ORDER BY seq ASC", (chat_id,))
        rows = cur.fetchall()
        return [{"role": r[0], "content": r[1]} for r in rows]
    finally:
        conn.close()

def send_chat_message(
    chat_id: str | None,
    message: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 256,
    timeout: Optional[int] = None,
    stream_callback: Optional[Callable[[str], None]] = None,
) -> tuple[str, str]:
    """Send a message in a chat. Returns (chat_id, assistant_reply).

    If chat_id is None or unknown, a new chat is created and its id returned.
    """
    cfg = config.load()
    prov_name = provider or cfg.get("provider") or "ollama"
    prov = providers.get_provider(prov_name)
    if not prov:
        raise ValueError(f"No provider configured or found for '{prov_name}'")

    effective_timeout = timeout if timeout is not None else cfg.get("timeout", 300)
    resolved_model = model or None

    # Ensure chat exists
    if not chat_id:
        # no id supplied: create a new one
        chat_id = create_chat()
    elif not _chat_exists(chat_id):
        # id supplied but unknown: create an empty chat with the provided id
        create_chat(chat_id)
    # Append user message
    append_message(chat_id, "user", message)

    # Build messages list for provider
    messages = get_chat_history(chat_id)

    def _trim_history_for_provider(msgs, max_tokens_allowed: int = 256, max_turns: int = 40):
        """Trim history to fit resource constraints while preserving system messages and recent turns.

        Uses a simple char-based heuristic: assume ~4 chars per token and keep messages until a char limit.
        """
        if not msgs:
            return []
        approx_chars_limit = max(256, (max_tokens_allowed or 256) * 4)
        system_msgs = [m for m in msgs if m.get('role') == 'system']
        other_msgs = [m for m in msgs if m.get('role') != 'system']
        trimmed_others = []
        total = sum(len(m.get('content', '')) for m in system_msgs)
        # take most recent turns first
        for m in reversed(other_msgs):
            if len(trimmed_others) >= max_turns:
                break
            mlen = len(m.get('content', ''))
            if total + mlen > approx_chars_limit and trimmed_others:
                break
            trimmed_others.append(m)
            total += mlen
        trimmed_others.reverse()
        return system_msgs + trimmed_others

    messages_to_send = _trim_history_for_provider(messages, max_tokens or 256)

    # Call provider.chat
    if not hasattr(prov, 'chat'):
        # Fallback: compose messages into a single prompt preserving order
        sys_parts = [m['content'] for m in messages_to_send if m.get('role') == 'system']
        conv_parts = []
        for m in messages_to_send:
            role = m.get('role')
            if role == 'system':
                continue
            content = m.get('content', '')
            if role == 'user':
                conv_parts.append(f"User: {content}")
            elif role == 'assistant':
                conv_parts.append(f"Assistant: {content}")
            else:
                conv_parts.append(f"{role.capitalize()}: {content}")
        prompt = "\n\n".join(sys_parts + conv_parts + [f"Assistant: {message}"])
        # Use summarize as a fallback generation endpoint
        reply = prov.summarize(prompt, model=resolved_model, max_tokens=max_tokens, timeout=effective_timeout, stream_callback=stream_callback)
    else:
        # Provider has native chat support
        # The provider.chat method is expected to accept the trimmed messages list we provide
        if stream_callback:
            # accumulate streamed chunks
            acc = []
            def cb(chunk: str):
                acc.append(chunk)
                stream_callback(chunk)
            reply = prov.chat(messages_to_send, model=resolved_model, max_tokens=max_tokens, timeout=effective_timeout, stream_callback=cb)
            if not acc:
                reply = reply or ""
            else:
                reply = "".join(acc)
        else:
            reply = prov.chat(messages_to_send, model=resolved_model, max_tokens=max_tokens, timeout=effective_timeout)

    # Append assistant reply to history
    append_message(chat_id, "assistant", reply)
    return chat_id, reply

