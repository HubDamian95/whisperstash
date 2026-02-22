const statusEl = document.getElementById('status');

function setStatus(msg) {
  statusEl.textContent = msg;
}

document.getElementById('health').addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'health' }, (resp) => {
    if (resp && resp.ok) {
      setStatus('Server reachable.');
    } else {
      setStatus(`Server error: ${resp?.error || 'not reachable'}`);
    }
  });
});

document.getElementById('decrypt').addEventListener('click', async () => {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  const tab = tabs[0];
  if (!tab?.id) {
    setStatus('No active tab.');
    return;
  }
  chrome.tabs.sendMessage(tab.id, { type: 'decryptPage' }, (resp) => {
    if (chrome.runtime.lastError) {
      setStatus(`Tab error: ${chrome.runtime.lastError.message}`);
      return;
    }
    if (resp && resp.ok) {
      setStatus('Page decrypted.');
    } else {
      setStatus(`Decrypt failed: ${resp?.error || 'unknown'}`);
    }
  });
});
