import os
import subprocess
import httpx
import re
from urllib.parse import quote_plus
from typing import Dict, Any

def web_search(query: str) -> str:
    """Cerca sul web tramite DuckDuckGo HTML e restituisce i primi risultati."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        with httpx.Client(headers=headers, follow_redirects=True, timeout=10) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return f"Errore nella ricerca (HTTP {resp.status_code})"
            
            # Parsing minimale dei risultati usando regex per evitare dipendenze da BeautifulSoup
            html = resp.text
            results = []
            # DuckDuckGo HTML snippet pattern
            pattern = re.compile(
                r'<a class="result__snippet"[^>]*>(.*?)</a>',
                re.DOTALL
            )
            snippets = pattern.findall(html)
            
            # Estrae anche i titoli
            title_pattern = re.compile(
                r'<a class="result__url"[^>]*>(.*?)</a>',
                re.DOTALL
            )
            titles = title_pattern.findall(html)
            
            for i, snippet in enumerate(snippets[:4]):
                clean_snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                title = clean_snippet[:50]
                if i < len(titles):
                    title = re.sub(r'<[^>]+>', '', titles[i]).strip()
                results.append(f"Result {i+1}: {title}\nSnippet: {clean_snippet}\n")
                
            if not results:
                return "Nessun risultato rilevante trovato."
            return "\n".join(results)
    except Exception as e:
        return f"Errore durante la ricerca web: {str(e)}"

def execute_command(command: str) -> str:
    """Esegue un comando di shell sul PC locale e restituisce l'output."""
    try:
        # Eseguiamo in modalità sicura con timeout
        res = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        output = ""
        if res.stdout:
            output += f"[STDOUT]\n{res.stdout}\n"
        if res.stderr:
            output += f"[STDERR]\n{res.stderr}\n"
        if not output:
            output = "Comando completato con successo (nessun output)."
        return output
    except subprocess.TimeoutExpired:
        return "Errore: Il comando ha superato il timeout massimo di 30 secondi."
    except Exception as e:
        return f"Errore durante l'esecuzione del comando: {str(e)}"

def read_file(filepath: str) -> str:
    """Legge il contenuto di un file sul PC locale."""
    try:
        if not os.path.exists(filepath):
            return f"Errore: Il file {filepath} non esiste."
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Errore nella lettura del file: {str(e)}"

def write_file(filepath: str, content: str) -> str:
    """Scrive un nuovo file o sovrascrive un file esistente con il contenuto specificato."""
    try:
        # Crea le directory genitore se non esistono
        dirname = os.path.dirname(filepath)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"File '{filepath}' scritto con successo ({len(content)} caratteri)."
    except Exception as e:
        return f"Errore nella scrittura del file: {str(e)}"

def modify_file(filepath: str, search_text: str, replace_text: str) -> str:
    """Modifica un file esistente sostituendo una porzione di testo specifica."""
    try:
        if not os.path.exists(filepath):
            return f"Errore: Il file {filepath} non esiste."
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if search_text not in content:
            return f"Errore: Testo target per la sostituzione non trovato all'interno del file."
            
        new_content = content.replace(search_text, replace_text)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return f"File '{filepath}' modificato con successo."
    except Exception as e:
        return f"Errore nella modifica del file: {str(e)}"
