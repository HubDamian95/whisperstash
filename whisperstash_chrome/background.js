const API = 'http://127.0.0.1:8765';

function buildHeaders(authToken) {
  const headers = { 'Content-Type': 'application/json' };
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }
  return headers;
}

async function post(path, payload, authToken) {
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: buildHeaders(authToken),
    body: JSON.stringify(payload)
  });
  return await res.json();
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      if (msg.type === 'health') {
        const res = await fetch(`${API}/health`, { headers: buildHeaders(msg.authToken) });
        const data = await res.json();
        sendResponse(data);
        return;
      }

      if (msg.type === 'decryptToken') {
        const data = await post('/decrypt', { token: msg.token }, msg.authToken);
        sendResponse(data);
        return;
      }

      if (msg.type === 'unwrapText') {
        const data = await post('/unwrap', { text: msg.text }, msg.authToken);
        sendResponse(data);
        return;
      }

      sendResponse({ ok: false, error: 'unknown message type' });
    } catch (err) {
      sendResponse({ ok: false, error: String(err) });
    }
  })();

  return true;
});
