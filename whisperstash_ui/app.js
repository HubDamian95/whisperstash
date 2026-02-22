const inputEl = document.getElementById('input');
const outputEl = document.getElementById('output');
const statusEl = document.getElementById('status');
const detectedEl = document.getElementById('detected');
const modeEl = document.getElementById('mode');
const integrityEl = document.getElementById('integrity');
const autoWrapEl = document.getElementById('autoWrap');
const copyOutputBtn = document.getElementById('copyOutput');
const clearInputBtn = document.getElementById('clearInput');

let timer = null;
let requestSeq = 0;

function setStatus(text, klass = '') {
  statusEl.textContent = text;
  statusEl.className = klass;
}

function scheduleTransform() {
  if (timer) clearTimeout(timer);
  timer = setTimeout(runTransform, 240);
}

async function runTransform() {
  const text = inputEl.value;
  const mode = modeEl.value;
  const integrity = integrityEl.checked;
  const auto_wrap = autoWrapEl.checked;
  const seq = ++requestSeq;

  if (!text) {
    outputEl.value = '';
    detectedEl.textContent = 'Detected: -';
    setStatus('Ready', '');
    return;
  }

  setStatus('Transforming...', '');

  try {
    const res = await fetch('/api/transform', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, mode, integrity, auto_wrap })
    });
    const data = await res.json();

    if (seq !== requestSeq) return;

    if (!res.ok || !data.ok) {
      throw new Error(data.error || `HTTP ${res.status}`);
    }

    outputEl.value = data.output || '';
    detectedEl.textContent = `Detected: ${data.mode || mode}`;
    setStatus('Done', 'status-ok');
  } catch (err) {
    if (seq !== requestSeq) return;
    setStatus(`Error: ${String(err.message || err)}`, 'status-err');
  }
}

inputEl.addEventListener('input', scheduleTransform);
modeEl.addEventListener('change', scheduleTransform);
integrityEl.addEventListener('change', scheduleTransform);
autoWrapEl.addEventListener('change', scheduleTransform);

copyOutputBtn.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(outputEl.value || '');
    setStatus('Output copied to clipboard', 'status-ok');
  } catch (_) {
    setStatus('Clipboard write failed', 'status-err');
  }
});

clearInputBtn.addEventListener('click', () => {
  inputEl.value = '';
  outputEl.value = '';
  detectedEl.textContent = 'Detected: -';
  setStatus('Ready', '');
  inputEl.focus();
});
