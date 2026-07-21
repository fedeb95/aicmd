import sys
import re
from pathlib import Path
from typing import Optional, Callable, List, Dict
from . import config, providers, agent, agent_tools
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

def _normalize_language(lang: str) -> str:
    """Normalize language codes/names to readable language names for instructions."""
    if not lang:
        return lang
    mapping = {
        'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German', 'pt': 'Portuguese',
        'zh': 'Chinese', 'zh-cn': 'Chinese (Simplified)', 'zh-tw': 'Chinese (Traditional)',
        'ja': 'Japanese', 'ko': 'Korean', 'it': 'Italian', 'ru': 'Russian'
    }
    key = lang.strip().lower()
    return mapping.get(key, lang)


def translate_text(
    text: str,
    target_lang: str,
    source_lang: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 256,
    timeout: Optional[int] = None,
    stream_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """Translate text into target_lang. Prefer provider.chat when available for better translation fidelity.

    If provider has no chat, fall back to provider.rewrite with an explicit instruction.
    """
    cfg = config.load()
    prov_name = provider or cfg.get("provider") or "llamaserver"
    prov = providers.get_provider(prov_name)
    if not prov:
        raise ValueError(f"No provider configured or found for '{prov_name}'")

    effective_timeout = timeout if timeout is not None else cfg.get("timeout", 300)
    resolved_model = model or None

    tname = _normalize_language(target_lang)
    sname = _normalize_language(source_lang) if source_lang else None

    # Strong system instruction for translation
    # (il system prompt è già nel KV della sessione translate; qui inviamo
    #  solo il testo + hint lingua come user message)
    user_content = text
    if sname:
        user_content = f"[Source language: {sname}]\n[Target language: {tname}]\n\n{text}"
    else:
        user_content = f"[Target language: {tname}]\n\n{text}"

    # Se il provider supporta le sessioni KV, ripristiniamo quella di translate
    # (il system prompt è già nel KV) e inviamo solo il contenuto utente.
    if hasattr(prov, 'set_session') and hasattr(prov, 'chat'):
        from .providers.sessions import SESSION_TRANSLATE
        prov.set_session(SESSION_TRANSLATE)
        messages = [{"role": "user", "content": user_content}]
        if stream_callback:
            acc = []
            def cb(chunk: str):
                acc.append(chunk)
                stream_callback(chunk)
            reply = prov.chat(messages, model=resolved_model, max_tokens=max_tokens, timeout=effective_timeout, stream_callback=cb)
            if acc:
                return "".join(acc)
            return reply or ""
        else:
            return prov.chat(messages, model=resolved_model, max_tokens=max_tokens, timeout=effective_timeout)

    # Fallback: provider senza sessioni KV -> usiamo system + user completi
    sys_instr = (
        f"You are a professional translator. Always translate the user's text into {tname}. "
        "Output ONLY the translated text, preserving formatting, code blocks, and lists. "
        "Do not add explanations or commentary. If the source language is provided, use it; otherwise detect the source language automatically."
    )
    messages = [{"role": "system", "content": sys_instr}]
    if sname:
        messages.append({"role": "system", "content": f"Source language hint: {sname}."})
    messages.append({"role": "user", "content": text})

    if hasattr(prov, 'chat'):
        if stream_callback:
            acc = []
            def cb(chunk: str):
                acc.append(chunk)
                stream_callback(chunk)
            reply = prov.chat(messages, model=resolved_model, max_tokens=max_tokens, timeout=effective_timeout, stream_callback=cb)
            if acc:
                return "".join(acc)
            return reply or ""
        else:
            return prov.chat(messages, model=resolved_model, max_tokens=max_tokens, timeout=effective_timeout)

    # Fallback: use rewrite with a clear instruction
    if sname:
        instr = f"Translate the following text from {sname} to {tname}. Output only the translated text, preserving meaning and formatting."
    else:
        instr = f"Translate the following text to {tname}. Output only the translated text, preserving meaning and formatting."

    return prov.rewrite(
        text,
        instr,
        model=resolved_model,
        max_tokens=max_tokens,
        timeout=effective_timeout,
        stream_callback=stream_callback,
    )


def recipe_from_ingredients(
    ingredients: str,
    people: Optional[int] = None,
    speed: Optional[str] = None,
    target_language: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 512,
    timeout: Optional[int] = None,
    stream_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """Generate one or more recipes from a list of available ingredients.

    Optionally constrain to a number of servings (people), preparation speed, 
    and desired language. Prefer provider.chat with the dedicated recipe KV session when available.
    """
    cfg = config.load()
    prov_name = provider or cfg.get("provider") or "llamaserver"
    prov = providers.get_provider(prov_name)
    if not prov:
        raise ValueError(f"No provider configured or found for '{prov_name}'")

    effective_timeout = timeout if timeout is not None else cfg.get("timeout", 300)
    resolved_model = model or None

    # Determina la lingua target (priorità: parametro esplicito → config → auto)
    target = (target_language or cfg.get("language") or "auto").strip().lower()
    if target not in ("auto", "en", "it", "es", "fr", "de", "pt"):
        target = "auto"

    # Costruisce il contenuto utente con vincoli opzionali.
    # Quando la lingua è esplicita, la segnaliamo con un prefisso "xx:" così
    # il modello risponde nella lingua richiesta anche via sessione KV generica.
    user_content = ingredients.strip()
    if target != "auto":
        user_content = f"[{target}]: {user_content}"
    if people is not None:
        user_content += f"\n\nNumber of servings: {people}"
    if speed is not None and speed.strip():
        user_content += f"\n\nPreparation speed / constraint: {speed.strip()}"
    user_content += "\n\nPropose a recipe (or a few alternatives) using these ingredients."

    # NOTA: questo llama-server si impalla (streaming e non) se riceve un
    # messaggio con ruolo "system". Inseriamo quindi le istruzioni nel messaggio
    # user (come fa di fatto translate), evitando il ruolo system.
    sys_instr = (
        "You are a chef. Given a list of available ingredients, "
        "propose EXACTLY ONE recipe using ONLY those ingredients. "
        "Respond in the same language as the user's request. Be concise."
    )
    full_user = f"{sys_instr}\n\n---\n\n{user_content}"
    messages = [{"role": "user", "content": full_user}]

    if hasattr(prov, 'set_session') and hasattr(prov, 'chat'):
        from .providers.sessions import SESSION_RECIPE
        prov.set_session(SESSION_RECIPE)
        messages = [{"role": "user", "content": user_content}]
        if stream_callback:
            acc = []
            def cb(chunk: str):
                acc.append(chunk)
                stream_callback(chunk)
            reply = prov.chat(messages, model=resolved_model, max_tokens=max_tokens, timeout=effective_timeout, stream_callback=cb)
            if acc:
                return "".join(acc)
            return reply or ""
        else:
            return prov.chat(messages, model=resolved_model, max_tokens=max_tokens, timeout=effective_timeout)


    if hasattr(prov, 'chat'):
        if stream_callback:
            acc = []
            def cb(chunk: str):
                acc.append(chunk)
                stream_callback(chunk)
            reply = prov.chat(messages, model=resolved_model, max_tokens=max_tokens, timeout=effective_timeout, stream_callback=cb)
            if acc:
                return "".join(acc)
            return reply or ""
        else:
            return prov.chat(messages, model=resolved_model, max_tokens=max_tokens, timeout=effective_timeout)    # Fallback: use rewrite with a clear instruction

    instr = (
        "You are a creative chef. Using the ingredients below, propose a recipe "
        "with servings, ingredients and quantities, and step-by-step instructions.\n\n"
        + user_content
    )
    if hasattr(prov, 'rewrite'):
        return prov.rewrite(
            ingredients,
            instr,
            model=resolved_model,
            max_tokens=max_tokens,
            timeout=effective_timeout,
            stream_callback=stream_callback,
        )

    raise NotImplementedError("The selected provider does not support chat or rewrite.")


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

    # Build messages list for provider (excluding thought/observation intermediate agent roles)
    raw_messages = get_chat_history(chat_id)
    messages = [m for m in raw_messages if m.get("role") in ["user", "assistant", "system"]]

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


def execute_agent_tool(tool_name: str, tool_args: dict) -> str:
    """Execute a tool specified by tool_name with arguments in tool_args, handling stream context."""
    try:
        # Initialize stream context if not provided
        if 'stream_context' not in tool_args:
            tool_args['stream_context'] = {
                'session_id': str(uuid.uuid4()),
                'type': 'tool_stream',
                'tool_name': tool_name,
                'provided_by': 'agent'
            }
        
        # Handle specific tools
        if tool_name == 'web_search':
            return agent_tools.web_search(tool_args.get('query', ''))
        elif tool_name == 'read_file':
            return agent_tools.read_file(tool_args.get('filepath', ''))
        elif tool_name == 'execute_command':
            # Preserve full command context
            return agent_tools.execute_command(tool_args.get('command', ''))
        elif tool_name == 'write_file':
            return agent_tools.write_file(tool_args.get('filepath', ''), tool_args.get('content', ''))
        elif tool_name == 'modify_file':
            return agent_tools.modify_file(
                tool_args.get('filepath', ''),
                tool_args.get('search_text', ''),
                tool_args.get('replace_text', '')
            )
        else:
            # Fallback for unknown tools with context tracking
            return f"Error: Tool '{tool_name}' not implemented. Context: {tool_args.get('stream_context', {})}"
    except Exception as e:
        return f"Execution error: {str(e)} (Context: {tool_args.get('stream_context', {})})"


def detect_tool_from_response(resp: str, history: list) -> Optional[tuple]:
    """Filtro semantico sulla risposta in linguaggio libero dell'LLM.

    Se la risposta segnala (IT/EN) che servirebbe uno strumento, restituisce
    (tool_name, tool_args) da forzare. Altrimenti None.
    Non viene chiamato se un tool è già stato usato nel turno (gestito dal caller).
    """
    # --- web_search: delega a fonte esterna / "non lo so" / argomenti real-time ---
    web_signals = re.search(
        # IT: delega/rimando a fonte esterna
        r"dovresti (?:cercare|consultare|verificare)|prova (?:a )?(?:cercare|consultare)|"
        r"(?:puoi|devi|dovresti) (?:andare|visitare|collegarti)|"
        r"(?:risolta|trov[aai]|scopri|otteni|cerca)[^.]*(?:sito|pagina|portale|web|internet|online|motore di ricerca)|"
        r"(?:tramite|su|mediante|attraverso) (?:un |il )?(?:sito|pagina|portale|sito web|website)[^.]{0,30}(?:web|previsioni?|meteo|notizie|tempo)|"
        r"sito (?:web|internet)|pagina web|motore di ricerca|"
        # IT: ammissione di non conoscenza / impossibilità
        r"non (?:conosco|so|ho|dispongo|posso|riesco) (?:la |i |il )?(?:meteo|prevision|notizie?|prezz|orari|risposta|dati?)|"
        r"non (?:posso|riesco|sono in grado di) (?:sapere|dirti|fornirti|trovare)|"
        # EN: delegate / defer to external source
        r"you (?:should|can|could|need to) (?:search|look[\s-]?up|check|consult|visit|use)|"
        r"(?:look|check|search|find)[^.]*(?:website|web page|online|search engine|the web|internet)|"
        r"(?:via|on|through|using) (?:a |the )?(?:website|web page|web portal|search engine|internet|online)|"
        r"search engine|web ?site|web page|"
        # EN: admission of not knowing
        r"i (?:don'?t|do not) (?:know|have|have access)|i (?:can'?t|cannot) (?:tell|provide|find|know)|"
        r"you (?:should|need to) (?:check|visit|search)|"
        # generic real-time topics that imply an external source is needed
        r"previsioni? (?:del )?meteo|meteo (?:di|per|oggi|domani)|weather (?:forecast|for|today|tomorrow)|"
        r"notizie (?:di|del|oggi)|news (?:today|about|of)|prezzi(?: correnti| attuali| di oggi)|current prices?",
        resp,
        re.IGNORECASE,
    )
    if web_signals:
        user_msgs = [m.get("content", "") for m in history if m.get("role") == "user"]
        query = user_msgs[-1] if user_msgs else resp
        return ("web_search", {"query": query})

    # --- read_file: cita un percorso di file o propone di leggerlo ---
    read_signals = re.search(
        r"legg(?:o|i|ere)|apr(?:o|i) (?:il )?file|mostr(?:o|a) (?:il )?contenuto|"
        r"read (?:the )?file|show (?:me )?the (?:file|content)|open (?:the )?file",
        resp,
        re.IGNORECASE,
    )
    if read_signals:
        path_match = re.search(r"(?:/[\w.\-/]+|(?:[A-Za-z]:)?\.[\\\/\w.\-]+)", resp)
        if path_match:
            return ("read_file", {"filepath": path_match.group(0)})

    # --- execute_command: propone/esegue un comando di shell ---
    cmd_signals = re.search(
        r"eseguo|esegui(?:amo)?|lancio|avvio|run (?:the |this )?command|"
        r"i (?:can |will )?run|execute (?:the )?command|comando[:\s]",
        resp,
        re.IGNORECASE,
    )
    if cmd_signals:
        # Comando tra backtick, oppure dopo "esegui/run/comando:"
        backtick = re.search(r"`([^`]+)`", resp)
        if backtick:
            return ("execute_command", {"command": backtick.group(1).strip()})
        after = re.search(r"(?:esegui|run|comando|command)[:\s]+([^\n]+)", resp, re.IGNORECASE)
        if after:
            return ("execute_command", {"command": after.group(1).strip()})

    return None


def run_agent_loop(
    chat_id: str,
    message: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[int] = None,
    stream_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """Agente lightweight: una risposta in chat, eventuale esecuzione di uno
    strumento (rilevata semanticamente dalla risposta), e risposta hardcoded
    di conferma + estratto. L'osservazione resta nel contesto per le domande
    successive.
    """
    import json
    cfg = config.load()
    prov_name = provider or cfg.get("provider") or "ollama"
    resolved_model = model or None

    # Se c'è un nuovo messaggio dell'utente, lo salviamo
    if message:
        append_message(chat_id, "user", message)

    executor = agent.AgentExecutor(prov_name, resolved_model)

    if stream_callback:
        stream_callback(json.dumps({"status": "thinking"}))

    history = get_chat_history(chat_id)
    step_res = executor.step(history)

    if step_res["status"] == "error":
        err_msg = step_res["error"]
        if stream_callback:
            stream_callback(json.dumps({"error": err_msg}))
        append_message(chat_id, "assistant", f"Errore: {err_msg}")
        return err_msg

    resp = step_res["response"]

    # Tool già usato in questo turno? Allora niente doppio trigger.
    has_used_tool = any(
        m.get("role") == "observation" or "Observation:" in m.get("content", "")
        for m in get_chat_history(chat_id)
    )

    forced = None
    if not has_used_tool:
        forced = detect_tool_from_response(resp, get_chat_history(chat_id))

    if forced:
        tool_name, tool_args = forced

        # Tool sensibile: richiede approvazione prima di eseguire
        if tool_name in ["execute_command", "write_file", "modify_file"]:
            if stream_callback:
                stream_callback(json.dumps({
                    "requires_approval": True,
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "thought": f"Risposta che implica l'uso di {tool_name}.",
                }))
            action_desc = f"Chiedo di eseguire lo strumento '{tool_name}' con parametri: {json.dumps(tool_args)}"
            append_message(chat_id, "assistant", action_desc)
            return f"In attesa di approvazione per il tool: {tool_name}"

        if stream_callback:
            stream_callback(json.dumps({
                "thought": f"Risposta che implica l'uso di {tool_name}: lo eseguo.",
                "executing_tool": tool_name,
                "args": tool_args,
            }))

        observation = execute_agent_tool(tool_name, tool_args)
        # L'osservazione entra nel contesto per le domande successive
        append_message(chat_id, "observation", f"Observation: {observation}")

        # Risposta hardcoded: conferma + breve estratto dei risultati
        if tool_name == "web_search":
            extract = _first_lines(observation, 6)
            reply = f"Ho cercato sul web per «{tool_args.get('query', '')}». Risultati:\n\n{extract}"
        elif tool_name == "read_file":
            extract = _first_lines(observation, 20)
            reply = f"Ho letto il file «{tool_args.get('filepath', '')}». Contenuto:\n\n{extract}"
        else:
            reply = f"Ho eseguito «{tool_args.get('command', '')}».\n{_first_lines(observation, 10)}"

        if stream_callback:
            stream_callback(json.dumps({"reply": reply}))
        append_message(chat_id, "assistant", reply)
        return reply

    # Nessun tool: risposta diretta del modello
    if stream_callback:
        stream_callback(json.dumps({"reply": resp}))
    append_message(chat_id, "assistant", resp)
    return resp


def _first_lines(text: str, n: int) -> str:
    """Tronca il testo alle prime n righe non vuote per l'estratto hardcoded."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines[:n])

