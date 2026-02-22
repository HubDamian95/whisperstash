const ENC_RE = /ENC\[([A-Za-z0-9_\-=]+)\]/g;

function walkTextNodes(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const out = [];
  let node;
  while ((node = walker.nextNode())) {
    if (node.nodeValue && node.nodeValue.includes('ENC[')) {
      out.push(node);
    }
  }
  return out;
}

async function decryptNodeText(text) {
  return await new Promise((resolve) => {
    chrome.runtime.sendMessage({ type: 'unwrapText', text }, (resp) => {
      if (resp && resp.ok && typeof resp.text === 'string') {
        resolve(resp.text);
      } else {
        resolve(text);
      }
    });
  });
}

async function decryptPage() {
  const nodes = walkTextNodes(document.body);
  for (const node of nodes) {
    const original = node.nodeValue;
    ENC_RE.lastIndex = 0;
    if (!ENC_RE.test(original)) continue;
    const updated = await decryptNodeText(original);
    node.nodeValue = updated;
  }
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'decryptPage') {
    decryptPage()
      .then(() => sendResponse({ ok: true }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }
});
