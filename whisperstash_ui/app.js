const inputEl = document.getElementById('input');
const outputEl = document.getElementById('output');
const statusEl = document.getElementById('status');
const detectedEl = document.getElementById('detected');
const modeEl = document.getElementById('mode');
const integrityEl = document.getElementById('integrity');
const autoWrapEl = document.getElementById('autoWrap');
const copyOutputBtn = document.getElementById('copyOutput');
const clearInputBtn = document.getElementById('clearInput');

const fileOpEl = document.getElementById('fileOp');
const fileInputEl = document.getElementById('fileInput');
const fileOutputEl = document.getElementById('fileOutput');
const fileIntegrityEl = document.getElementById('fileIntegrity');
const runFileOpBtn = document.getElementById('runFileOp');
const filesResultEl = document.getElementById('filesResult');

const batchOpEl = document.getElementById('batchOp');
const batchInDirEl = document.getElementById('batchInDir');
const batchOutDirEl = document.getElementById('batchOutDir');
const batchIncludeEl = document.getElementById('batchInclude');
const batchExcludeEl = document.getElementById('batchExclude');
const batchDryRunEl = document.getElementById('batchDryRun');
const batchIntegrityEl = document.getElementById('batchIntegrity');
const runBatchOpBtn = document.getElementById('runBatchOp');
const batchResultEl = document.getElementById('batchResult');

const runDoctorBtn = document.getElementById('runDoctor');
const runKeyStatusBtn = document.getElementById('runKeyStatus');
const toolsResultEl = document.getElementById('toolsResult');

let timer = null;
let requestSeq = 0;

function setStatus(text, klass = '') {
  statusEl.textContent = text;
  statusEl.className = klass;
}

function parsePatterns(text) {
  return (text || '')
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean);
}

async function postJson(path, payload) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {})
  });
  const data = await res.json();
  if (!res.ok || !data.ok) {
    throw new Error(data.error || `HTTP ${res.status}`);
  }
  return data;
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
    setStatus('Ready');
    return;
  }

  setStatus('Transforming...');

  try {
    const data = await postJson('/api/transform', { text, mode, integrity, auto_wrap });
    if (seq !== requestSeq) return;
    outputEl.value = data.output || '';
    detectedEl.textContent = `Detected: ${data.mode || mode}`;
    setStatus('Done', 'status-ok');
  } catch (err) {
    if (seq !== requestSeq) return;
    setStatus(`Error: ${String(err.message || err)}`, 'status-err');
  }
}

function initTabs() {
  const tabs = Array.from(document.querySelectorAll('.tab'));
  const panels = Array.from(document.querySelectorAll('.panel'));

  for (const tab of tabs) {
    tab.addEventListener('click', () => {
      for (const t of tabs) t.classList.remove('active');
      for (const p of panels) p.classList.remove('active');
      tab.classList.add('active');
      const id = tab.dataset.tab;
      document.getElementById(`tab-${id}`).classList.add('active');
    });
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
  setStatus('Ready');
  inputEl.focus();
});

runFileOpBtn.addEventListener('click', async () => {
  const op = fileOpEl.value;
  const payload = {
    in_file: fileInputEl.value.trim(),
    out_file: fileOutputEl.value.trim(),
    integrity: fileIntegrityEl.checked
  };
  const route = op === 'file-encrypt' ? '/api/file-encrypt' : op === 'file-decrypt' ? '/api/file-decrypt' : '/api/b64-to-enc';
  setStatus('Running file operation...');
  try {
    const data = await postJson(route, payload);
    filesResultEl.textContent = `OK\nOutput: ${data.output_file}`;
    setStatus('File operation complete', 'status-ok');
  } catch (err) {
    filesResultEl.textContent = `Error\n${String(err.message || err)}`;
    setStatus('File operation failed', 'status-err');
  }
});

runBatchOpBtn.addEventListener('click', async () => {
  const isEncrypt = batchOpEl.value === 'batch-encrypt';
  const route = isEncrypt ? '/api/batch-encrypt' : '/api/batch-decrypt';
  const payload = {
    in_dir: batchInDirEl.value.trim(),
    out_dir: batchOutDirEl.value.trim(),
    include: parsePatterns(batchIncludeEl.value),
    exclude: parsePatterns(batchExcludeEl.value),
    dry_run: batchDryRunEl.checked,
    integrity: batchIntegrityEl.checked
  };
  setStatus('Running batch operation...');
  try {
    const data = await postJson(route, payload);
    const lines = data.logs || [];
    batchResultEl.textContent = [`Processed: ${data.count}`, ...lines].join('\n');
    setStatus('Batch operation complete', 'status-ok');
  } catch (err) {
    batchResultEl.textContent = `Error\n${String(err.message || err)}`;
    setStatus('Batch operation failed', 'status-err');
  }
});

runDoctorBtn.addEventListener('click', async () => {
  setStatus('Running doctor...');
  try {
    const data = await postJson('/api/doctor', {});
    toolsResultEl.textContent = data.output || '(no output)';
    if (data.exit_code === 0) {
      setStatus('Doctor passed', 'status-ok');
    } else {
      setStatus('Doctor found issues', 'status-err');
    }
  } catch (err) {
    toolsResultEl.textContent = `Error\n${String(err.message || err)}`;
    setStatus('Doctor failed', 'status-err');
  }
});

runKeyStatusBtn.addEventListener('click', async () => {
  setStatus('Checking key status...');
  try {
    const data = await postJson('/api/key-status', {});
    toolsResultEl.textContent = `Default key set: ${data.is_set}\nPath: ${data.path}`;
    setStatus('Key status loaded', 'status-ok');
  } catch (err) {
    toolsResultEl.textContent = `Error\n${String(err.message || err)}`;
    setStatus('Key status failed', 'status-err');
  }
});

initTabs();
