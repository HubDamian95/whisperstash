const statusEl = document.getElementById('status');
const authTokenEl = document.getElementById('authToken');

function setStatus(msg) {
  statusEl.textContent = msg;
}

document.getElementById('health').addEventListener('click', () => {
  const authToken = authTokenEl.value.trim();
  chrome.runtime.sendMessage({ type: 'health', authToken }, (resp) => {
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
  const authToken = authTokenEl.value.trim();
  chrome.tabs.sendMessage(tab.id, { type: 'decryptPage', authToken }, (resp) => {
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
