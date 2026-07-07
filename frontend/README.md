# aicmd-frontend

Interfaccia web minimale e moderna per interagire con le funzionalità di **aicmd** (riassunto testi e descrizione immagini).

## Prerequisiti

1. Assicurati che l'API di `aicmd` sia in esecuzione. Puoi avviarla dalla cartella del repository `aicmd` tramite il comando:
   ```bash
   aicmd serve --port 8000
   ```
   (oppure eseguendo `./venv/bin/aicmd serve` se non l'hai installato globalmente).

## Come Eseguire il Frontend

Poiché si tratta di un'applicazione client-side pura (HTML/CSS/JS), puoi servirla con qualsiasi server HTTP minimale.

### Opzione 1: Server Python integrato (Consigliato)
Esegui questo comando all'interno di questa directory:
```bash
python3 -m http.server 3000
```
Quindi apri il browser all'indirizzo [http://localhost:3000](http://localhost:3000).

### Opzione 2: Estensione "Live Server" (in VS Code)
Se utilizzi VS Code, fai click destro su `index.html` e seleziona **"Open with Live Server"**.

## Funzionalità
- **Riassunto Testi**: Inserisci o incolla qualsiasi testo per richiedere una sintesi.
- **Descrizione Immagini**: Carica un'immagine tramite drag-and-drop o esplora file per riceverne la descrizione.
- **Personalizzazione**: Modifica l'indirizzo delle API, il provider (`ollama` o `openrouter`) e il modello specifico direttamente dall'interfaccia.
