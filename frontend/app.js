// ---- Sidebar Navigation ----
const menuItems = document.querySelectorAll('.menu-item');
const featurePanels = document.querySelectorAll('.feature-panel');
const panelTitle = document.getElementById('panel-title');
const panelSubtitle = document.getElementById('panel-subtitle');

const panelMeta = {
    'summarize-section': {
        title: 'Sintesi Testi',
        subtitle: 'Inserisci o incolla un testo per estrarre un riassunto conciso.'
    },
    'describe-section': {
        title: 'Descrizione Immagini',
        subtitle: 'Carica un\'immagine per ottenere una descrizione dettagliata generata dall\'AI.'
    },
    'rewrite-section': {
        title: 'Riscrittura Testi',
        subtitle: 'Riscrivi un testo seguendo uno stile o delle istruzioni personalizzate.'
    }
};

menuItems.forEach(item => {
    item.addEventListener('click', () => {
        const targetId = item.dataset.tab;

        // Update active state on menu items
        menuItems.forEach(mi => mi.classList.remove('active'));
        item.classList.add('active');

        // Show the target panel, hide others
        featurePanels.forEach(panel => {
            if (panel.id === targetId) {
                panel.classList.remove('hidden');
            } else {
                panel.classList.add('hidden');
            }
        });

        // Update header title/subtitle
        if (panelMeta[targetId]) {
            panelTitle.textContent = panelMeta[targetId].title;
            panelSubtitle.textContent = panelMeta[targetId].subtitle;
        }
    });
});

// DOM Elements
const apiUrlInput = document.getElementById('api-url');
const providerSelect = document.getElementById('provider-select');
const modelSelect = document.getElementById('model-select');

// ---- Model loader ----
async function fetchModels() {
    const apiUrl = apiUrlInput.value.trim().replace(/\/$/, '');
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
        const data = await res.json();
        const models = data.models || [];
        modelSelect.innerHTML = '<option value="">(Default provider)</option>';
        models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m;
            modelSelect.appendChild(opt);
        });
    } catch (e) {
        modelSelect.innerHTML = '<option value="">(Default provider)</option>';
        console.warn('Could not load models:', e.message);
    } finally {
        modelSelect.disabled = false;
    }
}

// Reload models when provider or API URL changes
providerSelect.addEventListener('change', fetchModels);
apiUrlInput.addEventListener('change', fetchModels);

// Initial load
fetchModels();

// Summarize elements
const textInput = document.getElementById('text-input');
const charCount = document.getElementById('char-count');
const btnSummarize = document.getElementById('btn-summarize');
const summarizeResultContainer = document.getElementById('summarize-result-container');
const summarizeResult = document.getElementById('summarize-result');

// Describe elements
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const uploadPrompt = document.getElementById('upload-prompt');
const previewContainer = document.getElementById('preview-container');
const imagePreview = document.getElementById('image-preview');
const btnRemoveImage = document.getElementById('btn-remove-image');
const btnDescribe = document.getElementById('btn-describe');
const describeResultContainer = document.getElementById('describe-result-container');
const describeResult = document.getElementById('describe-result');

// Rewrite elements
const rewriteTextInput = document.getElementById('rewrite-text-input');
const rewriteStyleInput = document.getElementById('rewrite-style-input');
const btnRewrite = document.getElementById('btn-rewrite');
const rewriteResultContainer = document.getElementById('rewrite-result-container');
const rewriteResult = document.getElementById('rewrite-result');

// Toast Element
const toast = document.getElementById('toast');
const toastMessage = document.getElementById('toast-message');
const toastClose = document.getElementById('toast-close');

let toastTimer = null;

function dismissToast() {
    toast.classList.add('hidden');
    if (toastTimer) {
        clearTimeout(toastTimer);
        toastTimer = null;
    }
}

toastClose.addEventListener('click', dismissToast);

// Toast notification helper
// Errors persist until the user presses ✕; successes auto-dismiss after 6s.
function showToast(message, isError = false) {
    // Cancel any previous auto-dismiss
    if (toastTimer) {
        clearTimeout(toastTimer);
        toastTimer = null;
    }

    toastMessage.textContent = message;
    toast.style.borderLeftColor = isError ? 'var(--danger)' : 'var(--accent)';
    toast.classList.remove('hidden');

    if (!isError) {
        toastTimer = setTimeout(dismissToast, 6000);
    }
}

let selectedFile = null;

// Character counter
textInput.addEventListener('input', () => {
    charCount.textContent = textInput.value.length;
});

// Drag & Drop handlers
dropZone.addEventListener('click', () => {
    fileInput.click();
});

fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
});

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
        handleFiles(e.dataTransfer.files);
    }
});

function handleFiles(files) {
    if (files.length === 0) return;
    const file = files[0];
    
    if (!file.type.startsWith('image/')) {
        showToast('Per favore, carica solo file d\'immagine.', true);
        return;
    }
    
    selectedFile = file;
    
    // Set preview
    const reader = new FileReader();
    reader.onload = (e) => {
        imagePreview.src = e.target.result;
        uploadPrompt.classList.add('hidden');
        previewContainer.classList.remove('hidden');
        btnDescribe.disabled = false;
    };
    reader.readAsDataURL(file);
}

// Remove image
btnRemoveImage.addEventListener('click', (e) => {
    e.stopPropagation(); // prevent triggering dropZone click
    resetImageUpload();
});

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

// Summarize API Call
btnSummarize.addEventListener('click', async () => {
    const text = textInput.value.trim();
    if (!text) {
        showToast('Inserisci del testo da riassumere.', true);
        return;
    }
    
    setLoading(btnSummarize, true);
    summarizeResultContainer.classList.add('hidden');
    
    try {
        const apiUrl = apiUrlInput.value.trim().replace(/\/$/, "");
        const provider = providerSelect.value;
        const model = modelSelect.value;
        
        const response = await fetch(`${apiUrl}/api/summarize`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                text: text,
                provider: provider || null,
                model: model || null
            })
        });
        
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || 'Impossibile connettersi al server aicmd.');
        }
        
        const data = await response.json();
        summarizeResult.textContent = data.summary;
        summarizeResultContainer.classList.remove('hidden');
        showToast('Riassunto generato con successo!');
    } catch (err) {
        showToast(err.message, true);
        console.error(err);
    } finally {
        setLoading(btnSummarize, false);
    }
});

// Describe API Call
btnDescribe.addEventListener('click', async () => {
    if (!selectedFile) {
        showToast('Seleziona prima un\'immagine.', true);
        return;
    }
    
    setLoading(btnDescribe, true);
    describeResultContainer.classList.add('hidden');
    
    try {
        const apiUrl = apiUrlInput.value.trim().replace(/\/$/, "");
        const provider = providerSelect.value;
        const model = modelSelect.value;
        
        const formData = new FormData();
        formData.append('file', selectedFile);
        if (provider) formData.append('provider', provider);
        if (model) formData.append('model', model);
        
        const response = await fetch(`${apiUrl}/api/describe`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || 'Impossibile descrivere l\'immagine.');
        }
        
        const data = await response.json();
        describeResult.textContent = data.description;
        describeResultContainer.classList.remove('hidden');
        showToast('Descrizione completata!');
    } catch (err) {
        showToast(err.message, true);
        console.error(err);
    } finally {
        setLoading(btnDescribe, false);
    }
});

// Rewrite API Call
btnRewrite.addEventListener('click', async () => {
    const text = rewriteTextInput.value.trim();
    const style = rewriteStyleInput.value.trim();
    if (!text) {
        showToast('Inserisci del testo da riscrivere.', true);
        return;
    }
    if (!style) {
        showToast('Specifica lo stile o l\'istruzione per la riscrittura.', true);
        return;
    }
    
    setLoading(btnRewrite, true);
    rewriteResultContainer.classList.add('hidden');
    
    try {
        const apiUrl = apiUrlInput.value.trim().replace(/\/$/, "");
        const provider = providerSelect.value;
        const model = modelSelect.value;
        
        const response = await fetch(`${apiUrl}/api/rewrite`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                text: text,
                style: style,
                provider: provider || null,
                model: model || null
            })
        });
        
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || 'Impossibile connettersi al server aicmd.');
        }
        
        const data = await response.json();
        rewriteResult.textContent = data.rewritten;
        rewriteResultContainer.classList.remove('hidden');
        showToast('Testo riscritto con successo!');
    } catch (err) {
        showToast(err.message, true);
        console.error(err);
    } finally {
        setLoading(btnRewrite, false);
    }
});

// Loading states
function setLoading(button, isLoading) {
    const textSpan = button.querySelector('.btn-text');
    const loader = button.querySelector('.loader');
    
    if (isLoading) {
        button.disabled = true;
        textSpan.classList.add('hidden');
        loader.classList.remove('hidden');
    } else {
        button.disabled = false;
        textSpan.classList.remove('hidden');
        loader.classList.add('hidden');
    }
}

// Copy to Clipboard utility
window.copyText = function(elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    navigator.clipboard.writeText(element.textContent)
        .then(() => {
            showToast('Copiato negli appunti!');
        })
        .catch(err => {
            showToast('Errore durante la copia.', true);
            console.error(err);
        });
};
