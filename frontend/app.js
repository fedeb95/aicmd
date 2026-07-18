// ============================================================
// State
// ============================================================
let selectedFile = null;
let llamaStatusInterval = null;

// ============================================================
// DOM Elements
// ============================================================
const apiUrlInput       = document.getElementById('api-url');
const providerSelect    = document.getElementById('provider-select');
const modelSelect       = document.getElementById('model-select');
const panelTitle        = document.getElementById('panel-title');
const panelSubtitle     = document.getElementById('panel-subtitle');
const providerBadge     = document.getElementById('provider-badge');
const providerDot       = document.getElementById('provider-dot');
const providerLabel     = document.getElementById('provider-label');
const llamaControlGroup = document.getElementById('llama-control-group');
const llamaDot          = document.getElementById('llama-dot');
const llamaStatusText   = document.getElementById('llama-status-text');
const btnLlamaStart     = document.getElementById('btn-llama-start');
const btnLlamaStop      = document.getElementById('btn-llama-stop');

// Toast
const toast        = document.getElementById('toast');
const toastMessage = document.getElementById('toast-message');
const toastClose   = document.getElementById('toast-close');
let toastTimer = null;

// ============================================================
// Panel metadata
// ============================================================
const panelMeta = {
    'summarize-section': {
        title: 'Sintesi Testi',
        subtitle: 'Inserisci o incolla un testo per estrarre un riassunto conciso.'
    },
    'describe-section': {
        title: 'Descrizione Immagini',
        subtitle: "Carica un'immagine per ottenere una descrizione dettagliata generata dall'AI."
    },
    'rewrite-section': {
        title: 'Riscrittura Testi',
        subtitle: 'Riscrivi un testo seguendo uno stile o delle istruzioni personalizzate.'
    },
    'translate-section': {
        title: 'Traduzione',
        subtitle: 'Traduci il tuo testo in una lingua diversa.'
    },
    'settings-section': {
        title: 'Impostazioni',
        subtitle: 'Configura provider, modello e connessione al server.'
    }
};

// ============================================================
// Provider badge helper
// ============================================================
function updateProviderBadge() {
    const prov = providerSelect.value;
    const model = modelSelect.value;
    const labels = {
        '': 'Default',
        'ollama': 'Ollama',
        'llamaserver': 'llama-server',
        'openrouter': 'OpenRouter',
    };
    providerLabel.textContent = model
        ? `${labels[prov] || prov} · ${model}`
        : (labels[prov] || prov || '—');

    // Dot color
    providerDot.className = 'provider-dot';
    if (prov === 'openrouter') providerDot.classList.add('dot-cloud');
    else if (prov === '' ) providerDot.classList.add('dot-default');
    else providerDot.classList.add('dot-local');
}

// ============================================================
// Sidebar Navigation
// ============================================================
const allMenuItems   = document.querySelectorAll('.menu-item');
const featurePanels  = document.querySelectorAll('.feature-panel');

function activatePanel(targetId) {
    // Update active state on ALL menu items (including settings btn)
    allMenuItems.forEach(mi => mi.classList.remove('active'));
    const btn = document.querySelector(`[data-tab="${targetId}"]`);
    if (btn) btn.classList.add('active');

    // Show target panel, hide others
    featurePanels.forEach(panel => {
        if (panel.id === targetId) {
            panel.classList.remove('hidden');
            panel.classList.add('active');
        } else {
            panel.classList.add('hidden');
            panel.classList.remove('active');
        }
    });

    // Update header
    if (panelMeta[targetId]) {
        panelTitle.textContent    = panelMeta[targetId].title;
        panelSubtitle.textContent = panelMeta[targetId].subtitle;
    }

    // llama-server status polling
    if (targetId === 'settings-section') {
        pollLlamaStatus();
    }
}

allMenuItems.forEach(item => {
    item.addEventListener('click', () => activatePanel(item.dataset.tab));
});

// ============================================================
// Model loader
// ============================================================
async function fetchModels() {
    const apiUrl   = apiUrlInput.value.trim().replace(/\/$/, '');
    const provider = providerSelect.value;
    modelSelect.innerHTML = '<option value="">Caricamento...</option>';
    modelSelect.disabled = true;
    try {
        const url = provider
            ? `${apiUrl}/api/models?provider=${encodeURIComponent(provider)}`
            : `${apiUrl}/api/models`;
        const res = await fetch(url);
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const data   = await res.json();
        const models = data.models || [];
        modelSelect.innerHTML = '<option value="">(Default provider)</option>';
        models.forEach(m => {
            const opt = document.createElement('option');
            opt.value       = m;
            opt.textContent = m;
            modelSelect.appendChild(opt);
        });
    } catch (e) {
        modelSelect.innerHTML = '<option value="">(Default provider)</option>';
        console.warn('Could not load models:', e.message);
    } finally {
        modelSelect.disabled = false;
        updateProviderBadge();
    }
}

// ============================================================
// llama-server lifecycle management
// ============================================================
async function fetchLlamaStatus() {
    const apiUrl = apiUrlInput.value.trim().replace(/\/$/, '');
    try {
        const res  = await fetch(`${apiUrl}/api/llama/status`);
        const data = await res.json();
        return data;
    } catch (e) {
        return { running: false, pid: null, managed: false };
    }
}

function setLlamaUI(running, managed) {
    llamaDot.className = 'llama-dot';
    if (!managed) {
        llamaDot.classList.add('dot-unmanaged');
        llamaStatusText.textContent = 'Non gestito in questa modalità';
        btnLlamaStart.disabled = true;
        btnLlamaStop.disabled  = true;
        return;
    }
    if (running) {
        llamaDot.classList.add('dot-running');
        llamaStatusText.textContent = 'In esecuzione';
        btnLlamaStart.disabled = true;
        btnLlamaStop.disabled  = false;
    } else {
        llamaDot.classList.add('dot-stopped');
        llamaStatusText.textContent = 'Fermo';
        btnLlamaStart.disabled = false;
        btnLlamaStop.disabled  = true;
    }
}

async function pollLlamaStatus() {
    if (providerSelect.value !== 'llamaserver') return;
    const data = await fetchLlamaStatus();
    setLlamaUI(data.running, data.managed);
}

// Avvia polling quando viene mostrata la sezione impostazioni con llamaserver selezionato
function startLlamaPolling() {
    if (llamaStatusInterval) return;
    llamaStatusInterval = setInterval(pollLlamaStatus, 4000);
}

function stopLlamaPolling() {
    if (llamaStatusInterval) {
        clearInterval(llamaStatusInterval);
        llamaStatusInterval = null;
    }
}

btnLlamaStart.addEventListener('click', async () => {
    const apiUrl = apiUrlInput.value.trim().replace(/\/$/, '');
    setLoading(btnLlamaStart, true);
    try {
        const res  = await fetch(`${apiUrl}/api/llama/start`, { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Errore avvio llama-server');
        showToast(`llama-server avviato (PID ${data.pid})`);
        await pollLlamaStatus();
    } catch (e) {
        showToast(e.message, true);
    } finally {
        setLoading(btnLlamaStart, false);
    }
});

btnLlamaStop.addEventListener('click', async () => {
    const apiUrl = apiUrlInput.value.trim().replace(/\/$/, '');
    setLoading(btnLlamaStop, true);
    try {
        const res  = await fetch(`${apiUrl}/api/llama/stop`, { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Errore stop llama-server');
        showToast('llama-server fermato.');
        await pollLlamaStatus();
    } catch (e) {
        showToast(e.message, true);
    } finally {
        setLoading(btnLlamaStop, false);
    }
});

// ============================================================
// Provider change handler
// ============================================================
async function onProviderChange() {
    const provider = providerSelect.value;

    // Mostra/nascondi sezione llama-server
    if (provider === 'llamaserver') {
        llamaControlGroup.style.display = '';
        await pollLlamaStatus();
        startLlamaPolling();
    } else {
        llamaControlGroup.style.display = 'none';
        stopLlamaPolling();

        // Se si era su llamaserver e ora si cambia, ferma il processo
        // (solo se l'API supporta la gestione)
        const apiUrl = apiUrlInput.value.trim().replace(/\/$/, '');
        try {
            const statusRes  = await fetch(`${apiUrl}/api/llama/status`);
            const statusData = await statusRes.json();
            if (statusData.managed && statusData.running) {
                await fetch(`${apiUrl}/api/llama/stop`, { method: 'POST' });
                showToast('llama-server fermato automaticamente.');
            }
        } catch (_) { /* silent: API standalone non gestisce llama */ }
    }

    await fetchModels();
}

providerSelect.addEventListener('change', onProviderChange);
apiUrlInput.addEventListener('change', fetchModels);
modelSelect.addEventListener('change', updateProviderBadge);

// ============================================================
// Summarize elements
// ============================================================
const textInput                  = document.getElementById('text-input');
const charCount                  = document.getElementById('char-count');
const btnSummarize               = document.getElementById('btn-summarize');
const summarizeResultContainer   = document.getElementById('summarize-result-container');
const summarizeResult            = document.getElementById('summarize-result');

// Describe elements
const dropZone             = document.getElementById('drop-zone');
const fileInput            = document.getElementById('file-input');
const uploadPrompt         = document.getElementById('upload-prompt');
const previewContainer     = document.getElementById('preview-container');
const imagePreview         = document.getElementById('image-preview');
const btnRemoveImage       = document.getElementById('btn-remove-image');
const btnDescribe          = document.getElementById('btn-describe');
const describeResultContainer = document.getElementById('describe-result-container');
const describeResult       = document.getElementById('describe-result');

// Rewrite elements
const rewriteTextInput         = document.getElementById('rewrite-text-input');
const rewriteStyleInput        = document.getElementById('rewrite-style-input');
const btnRewrite               = document.getElementById('btn-rewrite');
const rewriteResultContainer   = document.getElementById('rewrite-result-container');
const rewriteResult            = document.getElementById('rewrite-result');

// Translate elements
const translateTextInput         = document.getElementById('translate-text-input');
const translateFromInput         = document.getElementById('translate-from-input');
const translateToInput           = document.getElementById('translate-to-input');
const btnTranslate               = document.getElementById('btn-translate');
const translateResultContainer   = document.getElementById('translate-result-container');
const translateResult            = document.getElementById('translate-result');

// ============================================================
// Toast
// ============================================================
function dismissToast() {
    toast.classList.add('hidden');
    if (toastTimer) { clearTimeout(toastTimer); toastTimer = null; }
}

toastClose.addEventListener('click', dismissToast);

function showToast(message, isError = false) {
    if (toastTimer) { clearTimeout(toastTimer); toastTimer = null; }
    toastMessage.textContent = message;
    toast.style.borderLeftColor = isError ? 'var(--danger)' : 'var(--accent)';
    toast.classList.remove('hidden');
    if (!isError) { toastTimer = setTimeout(dismissToast, 6000); }
}

// ============================================================
// Character counter
// ============================================================
textInput.addEventListener('input', () => { charCount.textContent = textInput.value.length; });

// ============================================================
// Drag & Drop
// ============================================================
dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', e => handleFiles(e.target.files));

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) handleFiles(e.dataTransfer.files);
});

function handleFiles(files) {
    if (!files.length) return;
    const file = files[0];
    if (!file.type.startsWith('image/')) {
        showToast("Per favore, carica solo file d'immagine.", true);
        return;
    }
    selectedFile = file;
    const reader = new FileReader();
    reader.onload = e => {
        imagePreview.src = e.target.result;
        uploadPrompt.classList.add('hidden');
        previewContainer.classList.remove('hidden');
        btnDescribe.disabled = false;
    };
    reader.readAsDataURL(file);
}

btnRemoveImage.addEventListener('click', e => { e.stopPropagation(); resetImageUpload(); });

function resetImageUpload() {
    selectedFile = null;
    fileInput.value = '';
    imagePreview.src = '#';
    previewContainer.classList.add('hidden');
    uploadPrompt.classList.remove('hidden');
    btnDescribe.disabled = true;
    describeResultContainer.classList.add('hidden');
    describeResult.textContent = '';
}

// ============================================================
// API Helpers
// ============================================================
function getConfig() {
    return {
        apiUrl:   apiUrlInput.value.trim().replace(/\/$/, ''),
        provider: providerSelect.value,
        model:    modelSelect.value,
    };
}

// ============================================================
// Summarize
// ============================================================
btnSummarize.addEventListener('click', async () => {
    const text = textInput.value.trim();
    if (!text) { showToast('Inserisci del testo da riassumere.', true); return; }
    setLoading(btnSummarize, true);
    summarizeResultContainer.classList.add('hidden');
    const { apiUrl, provider, model } = getConfig();
    try {
        const response = await fetch(`${apiUrl}/api/summarize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, provider: provider || null, model: model || null })
        });
        if (!response.ok) { const e = await response.json(); throw new Error(e.detail || 'Errore server'); }
        const data = await response.json();
        summarizeResult.textContent = data.summary;
        summarizeResultContainer.classList.remove('hidden');
        showToast('Riassunto generato con successo!');
    } catch (err) {
        showToast(err.message, true);
    } finally {
        setLoading(btnSummarize, false);
    }
});

// ============================================================
// Describe
// ============================================================
btnDescribe.addEventListener('click', async () => {
    if (!selectedFile) { showToast("Seleziona prima un'immagine.", true); return; }
    setLoading(btnDescribe, true);
    describeResultContainer.classList.add('hidden');
    const { apiUrl, provider, model } = getConfig();
    try {
        const formData = new FormData();
        formData.append('file', selectedFile);
        if (provider) formData.append('provider', provider);
        if (model)    formData.append('model', model);
        const response = await fetch(`${apiUrl}/api/describe`, { method: 'POST', body: formData });
        if (!response.ok) { const e = await response.json(); throw new Error(e.detail || "Errore descrizione immagine"); }
        const data = await response.json();
        describeResult.textContent = data.description;
        describeResultContainer.classList.remove('hidden');
        showToast('Descrizione completata!');
    } catch (err) {
        showToast(err.message, true);
    } finally {
        setLoading(btnDescribe, false);
    }
});

// ============================================================
// Rewrite
// ============================================================
btnRewrite.addEventListener('click', async () => {
    const text  = rewriteTextInput.value.trim();
    const style = rewriteStyleInput.value.trim();
    if (!text)  { showToast('Inserisci del testo da riscrivere.', true); return; }
    if (!style) { showToast("Specifica lo stile o l'istruzione per la riscrittura.", true); return; }
    setLoading(btnRewrite, true);
    rewriteResultContainer.classList.add('hidden');
    const { apiUrl, provider, model } = getConfig();
    try {
        const response = await fetch(`${apiUrl}/api/rewrite`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, style, provider: provider || null, model: model || null })
        });
        if (!response.ok) { const e = await response.json(); throw new Error(e.detail || 'Errore server'); }
        const data = await response.json();
        rewriteResult.textContent = data.rewritten;
        rewriteResultContainer.classList.remove('hidden');
        showToast('Testo riscritto con successo!');
    } catch (err) {
        showToast(err.message, true);
    } finally {
        setLoading(btnRewrite, false);
    }
});

// ============================================================
// Translate
// ============================================================
btnTranslate.addEventListener('click', async () => {
    const text   = translateTextInput.value.trim();
    const target = translateToInput.value.trim();
    if (!text)   { showToast('Inserisci del testo da tradurre.', true); return; }
    if (!target) { showToast('Specifica la lingua di destinazione.', true); return; }
    setLoading(btnTranslate, true);
    translateResultContainer.classList.add('hidden');
    const { apiUrl, provider, model } = getConfig();
    const source = translateFromInput.value.trim();
    try {
        const response = await fetch(`${apiUrl}/api/translate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, target, source: source || null, provider: provider || null, model: model || null })
        });
        if (!response.ok) { const e = await response.json(); throw new Error(e.detail || 'Errore traduzione'); }
        const data = await response.json();
        translateResult.textContent = data.translated;
        translateResultContainer.classList.remove('hidden');
        showToast('Traduzione completata!');
    } catch (err) {
        showToast(err.message, true);
    } finally {
        setLoading(btnTranslate, false);
    }
});

// ============================================================
// Utilities
// ============================================================
function setLoading(button, isLoading) {
    const textSpan = button.querySelector('.btn-text');
    const loader   = button.querySelector('.loader');
    button.disabled = isLoading;
    if (isLoading) {
        textSpan.classList.add('hidden');
        loader.classList.remove('hidden');
    } else {
        textSpan.classList.remove('hidden');
        loader.classList.add('hidden');
    }
}

window.copyText = function(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    navigator.clipboard.writeText(el.textContent)
        .then(() => showToast('Copiato negli appunti!'))
        .catch(() => showToast('Errore durante la copia.', true));
};

// ============================================================
// Init
// ============================================================
fetchModels();
updateProviderBadge();
