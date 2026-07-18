import re
from typing import Dict, Any, List, Optional
from . import providers, config

SYSTEM_PROMPT = """Sei un assistente conversazionale. Rispondi in modo naturale e utile nella lingua dell'utente.

Se una richiesta riguarda informazioni in tempo reale che non conosci con certezza (meteo, previsioni, notizie, prezzi, fatti attuali) o richiede di leggere/eseguire qualcosa sul sistema, dillo esplicitamente nella risposta (es. "dovresti cercare sul web", "leggo il file X", "eseguo il comando Y"): un livello superiore si occuperà di eseguire lo strumento adatto. Non fingere di avere dati che non possiedi. Mantieni le risposte brevi."""

class AgentExecutor:
    def __init__(self, provider_name: str, model_name: Optional[str] = None):
        self.provider = providers.get_provider(provider_name)
        self.model = model_name
        
    def _call_llm(self, messages: List[Dict[str, str]], timeout: int = 120) -> str:
        """Chiama il modello linguistico tramite il provider corrente."""
        # Se il provider supporta la chat
        if hasattr(self.provider, 'chat'):
            # L'agente usa un system prompt dedicato: ripristiniamo la sua sessione KV.
            if hasattr(self.provider, 'set_session'):
                from .providers.sessions import SESSION_AGENT
                self.provider.set_session(SESSION_AGENT)
            return self.provider.chat(messages, model=self.model, max_tokens=512, timeout=timeout)
        else:
            # Fallback a completamento di testo
            prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages]) + "\nassistant:"
            return self.provider.summarize(prompt, model=self.model, max_tokens=512, timeout=timeout)

    def step(self, history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Esegue un singolo passo: chiama il modello in modalità chat e
        restituisce la sua risposta libera. Nessun parsing ReAct.
        {
            "status": "response" | "error",
            "response": "..."
        }
        """
        # Se il provider usa sessioni KV (es. llamaserver), il system prompt
        # dell'agente è già nel KV: non lo duplichiamo nei messages.
        use_kv_session = hasattr(self.provider, 'set_session')
        if use_kv_session:
            from .providers.sessions import SESSION_AGENT
            self.provider.set_session(SESSION_AGENT)
            messages = list(history)
        else:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

        try:
            raw_response = self._call_llm(messages)
            return {
                "status": "response",
                "response": raw_response.strip(),
            }
        except Exception as e:
            return {
                "status": "error",
                "error": f"Errore durante l'esecuzione del modello: {str(e)}"
            }
