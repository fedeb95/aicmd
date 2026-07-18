"""Mappatura prompt di sistema -> sessione KV salvata (--slot-save-path).

Ogni funzionalità (summarize, describe, rewrite, translate, chat, agent)
ha un proprio id di sessione. All'avvio precarichiamo il solo prompt di
sistema di ciascuna funzionalità nel KV e lo salviamo su disco; a ogni
richiesta il provider ripristina la sessione corrispondente invece di
ricalcolare il prompt.
"""
from typing import List, Dict

SESSION_SUMMARIZE = "summarize"
SESSION_DESCRIBE = "describe"
SESSION_REWRITE  = "rewrite"
SESSION_TRANSLATE = "translate"
SESSION_CHAT     = "chat"
SESSION_AGENT    = "agent"

# I prompt di sistema devono coincidere con quelli usati nelle chiamate reali
# (vedi llamaserver.py / services.py / agent.py) affinché il KV salvato sia
# identico a quello che verrebbe calcolato a runtime.

def _summarize_messages(cfg) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": "You are a helpful assistant that creates concise summaries."},
    ]

def _describe_messages(cfg) -> List[Dict[str, str]]:
    # Nessun prefisso fisso: a runtime inviamo il template + immagine.
    return []

def _rewrite_messages(cfg) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": "You are a helpful assistant that rewrites text according to specific styles or instructions."},
    ]

def _translate_messages(cfg) -> List[Dict[str, str]]:
    sys_instr = (
        "You are a professional translator. Always translate the user's text into the target language "
        "specified in the request. "
        "Output ONLY the translated text, preserving formatting, code blocks, and lists. "
        "Do not add explanations or commentary. If the source language is provided, use it; otherwise detect the source language automatically."
    )
    return [
        {"role": "system", "content": sys_instr},
    ]

def _chat_messages(cfg) -> List[Dict[str, str]]:
    # Chat pura: nessun system prompt fisso (le istruzioni arrivano dalla cronologia).
    return []

def _agent_messages(cfg) -> List[Dict[str, str]]:
    from ..agent import SYSTEM_PROMPT
    return [{"role": "system", "content": SYSTEM_PROMPT}]

def build_sessions() -> Dict[str, List[Dict[str, str]]]:
    """Costruisce le coppie (session_id -> messaggi di precaricamento)."""
    from .. import config as cfg_mod
    cfg = cfg_mod.load()
    return {
        SESSION_SUMMARIZE: _summarize_messages(cfg),
        SESSION_DESCRIBE:  _describe_messages(cfg),
        SESSION_REWRITE:   _rewrite_messages(cfg),
        SESSION_TRANSLATE: _translate_messages(cfg),
        SESSION_CHAT:      _chat_messages(cfg),
        SESSION_AGENT:     _agent_messages(cfg),
    }

def init_saved_sessions(provider, max_wait: float = 120.0) -> None:
    """Precarica e salva le sessioni KV sul provider llamaserver.

    Non fa nulla se il provider non supporta gli slot.
    """
    if not hasattr(provider, "save_slot"):
        return
    import time
    built = build_sessions()
    wait = 1.0
    elapsed = 0.0
    for session_id, messages in built.items():
        while True:
            try:
                provider.save_slot(session_id, messages)
                break
            except Exception as e:
                if elapsed >= max_wait:
                    raise RuntimeError(
                        f"Impossibile precaricare la sessione '{session_id}' su llama-server: {e}"
                    )
                time.sleep(wait)
                elapsed += wait
                wait = min(wait * 1.5, 5.0)
