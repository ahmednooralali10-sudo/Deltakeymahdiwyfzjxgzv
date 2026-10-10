"""
LootLabs / Loot-Link bypass — Flask API + Web UI for Vercel.
Single-file: HTML interface + bypass endpoint.
"""
import json
import random
import re
import threading
import time
import os
import base64
import hashlib
import uuid
import ast
import traceback
import zlib
from urllib.parse import urlparse

import requests
from flask import Flask, request, jsonify, Response

try:
    import brotli
except ImportError:
    brotli = None

from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

try:
    import websocket
except ImportError:
    websocket = None


app = Flask(__name__)


# ============================================================
# HTML INTERFACE (embedded)
# ============================================================
INDEX_HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LootLabs Bypass</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  :root {
    --bg: #0a0608;
    --panel: rgba(20, 12, 14, 0.72);
    --border: rgba(255, 60, 80, 0.28);
    --accent: #ff3c50;
    --accent-soft: #ff6b7d;
    --text: #f2eef0;
    --muted: #8a7f83;
    --success: #4ade80;
    --error: #ff5555;
  }
  html, body {
    height: 100%;
    background: var(--bg);
    color: var(--text);
    font-family: 'Cairo', system-ui, sans-serif;
    overflow-x: hidden;
  }
  body::before {
    content: '';
    position: fixed;
    inset: -40%;
    background:
      radial-gradient(circle at 20% 20%, rgba(255, 60, 80, 0.18), transparent 55%),
      radial-gradient(circle at 80% 80%, rgba(180, 20, 60, 0.22), transparent 55%),
      radial-gradient(circle at 50% 50%, rgba(90, 20, 40, 0.15), transparent 60%);
    animation: drift 24s ease-in-out infinite alternate;
    z-index: -1;
    filter: blur(40px);
  }
  @keyframes drift {
    0%   { transform: translate(0, 0) scale(1); }
    100% { transform: translate(4%, -3%) scale(1.15); }
  }

  .wrap {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }

  .card {
    width: 100%;
    max-width: 720px;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 36px 32px 28px;
    backdrop-filter: blur(20px) saturate(140%);
    -webkit-backdrop-filter: blur(20px) saturate(140%);
    box-shadow:
      0 0 0 1px rgba(255, 255, 255, 0.03) inset,
      0 30px 80px rgba(255, 20, 60, 0.08),
      0 8px 32px rgba(0, 0, 0, 0.55);
    position: relative;
    overflow: hidden;
  }
  .card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--accent), transparent);
    opacity: 0.7;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 6px;
  }
  .logo {
    width: 38px; height: 38px;
    border-radius: 10px;
    background: linear-gradient(135deg, var(--accent), #a01028);
    display: flex; align-items: center; justify-content: center;
    font-size: 20px;
    box-shadow: 0 0 24px rgba(255, 60, 80, 0.35);
  }
  h1 {
    font-size: 22px;
    font-weight: 800;
    letter-spacing: -0.3px;
  }
  h1 span { color: var(--accent); }
  .sub {
    color: var(--muted);
    font-size: 13px;
    margin-bottom: 24px;
    font-weight: 400;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 14px;
  }
  label {
    font-size: 12px;
    font-weight: 600;
    color: var(--muted);
    letter-spacing: 0.4px;
    text-transform: uppercase;
  }
  .input-row {
    position: relative;
    display: flex;
    gap: 10px;
  }
  textarea, input[type="text"] {
    flex: 1;
    background: rgba(0, 0, 0, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.06);
    color: var(--text);
    border-radius: 12px;
    padding: 14px 16px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    resize: none;
    transition: all 0.2s;
    outline: none;
    min-height: 52px;
    max-height: 140px;
    direction: ltr;
    text-align: left;
    line-height: 1.5;
  }
  textarea:focus, input[type="text"]:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(255, 60, 80, 0.12);
    background: rgba(0, 0, 0, 0.55);
  }
  textarea::placeholder {
    color: rgba(255, 255, 255, 0.2);
  }

  .btn {
    border: none;
    border-radius: 12px;
    padding: 14px 24px;
    font-family: inherit;
    font-size: 14px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.15s;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    white-space: nowrap;
  }
  .btn-primary {
    background: linear-gradient(135deg, var(--accent), #c41030);
    color: white;
    width: 100%;
    margin-top: 8px;
    box-shadow: 0 8px 24px rgba(255, 60, 80, 0.25);
  }
  .btn-primary:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 12px 32px rgba(255, 60, 80, 0.4);
    filter: brightness(1.1);
  }
  .btn-primary:active:not(:disabled) { transform: translateY(0); }
  .btn-primary:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  .btn-ghost {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--text);
    padding: 12px 18px;
  }
  .btn-ghost:hover { background: rgba(255, 255, 255, 0.1); }

  .spinner {
    width: 16px; height: 16px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    display: none;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .btn.loading .spinner { display: block; }
  .btn.loading .label { display: none; }
  .btn .label { display: inline; }

  .result {
    margin-top: 22px;
    border-radius: 12px;
    padding: 0;
    max-height: 0;
    overflow: hidden;
    transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    opacity: 0;
  }
  .result.show {
    max-height: 500px;
    opacity: 1;
    padding: 16px;
  }
  .result.success {
    background: rgba(74, 222, 128, 0.08);
    border: 1px solid rgba(74, 222, 128, 0.25);
  }
  .result.error {
    background: rgba(255, 85, 85, 0.08);
    border: 1px solid rgba(255, 85, 85, 0.25);
  }
  .result-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.4px;
    text-transform: uppercase;
  }
  .result.success .result-head { color: var(--success); }
  .result.error .result-head { color: var(--error); }
  .result-body {
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    line-height: 1.6;
    word-break: break-all;
    direction: ltr;
    text-align: left;
    color: var(--text);
    background: rgba(0, 0, 0, 0.3);
    padding: 12px;
    border-radius: 8px;
    max-height: 260px;
    overflow-y: auto;
  }
  .result-body::-webkit-scrollbar { width: 6px; }
  .result-body::-webkit-scrollbar-thumb {
    background: rgba(255, 60, 80, 0.4);
    border-radius: 3px;
  }

  .meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 8px;
    font-size: 11px;
    color: var(--muted);
    font-family: 'JetBrains Mono', monospace;
    direction: ltr;
  }

  .toast {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%) translateY(20px);
    background: rgba(20, 12, 14, 0.95);
    border: 1px solid var(--border);
    padding: 12px 20px;
    border-radius: 10px;
    font-size: 13px;
    opacity: 0;
    transition: all 0.25s;
    pointer-events: none;
    z-index: 1000;
    backdrop-filter: blur(10px);
  }
  .toast.show {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }

  .footer {
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    font-size: 11px;
    color: var(--muted);
    display: flex;
    justify-content: space-between;
  }

  @media (max-width: 520px) {
    .card { padding: 24px 20px 20px; border-radius: 16px; }
    h1 { font-size: 19px; }
  }
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <div class="brand">
      <div class="logo">🔓</div>
      <h1>LootLabs <span>Bypass</span></h1>
    </div>
    <p class="sub">الصق رابط LootLabs / Loot-Link وشوف النتيجة النهائية</p>

    <div class="field">
      <label for="url">الرابط</label>
      <div class="input-row">
        <textarea id="url" placeholder="https://loot-link.com/s?xxxxx&data=..." spellcheck="false"></textarea>
      </div>
    </div>

    <div class="input-row" style="margin-bottom: 6px;">
      <button class="btn btn-ghost" onclick="pasteFromClipboard()" type="button">📋 لصق</button>
      <button class="btn btn-ghost" onclick="document.getElementById('url').value=''" type="button">🗑 مسح</button>
    </div>

    <button id="submitBtn" class="btn btn-primary" onclick="runBypass()">
      <span class="spinner"></span>
      <span class="label">🚀 تخطي الرابط</span>
    </button>

    <div id="result" class="result">
      <div class="result-head">
        <span id="resultTitle">النتيجة</span>
        <button class="btn btn-ghost" style="padding: 4px 10px; font-size: 11px;" onclick="copyResult()">نسخ</button>
      </div>
      <div id="resultBody" class="result-body"></div>
      <div class="meta">
        <span id="resultMeta"></span>
      </div>
    </div>

    <div class="footer">
      <span>ALPHA XK build</span>
      <span id="status">جاهز</span>
    </div>
  </div>
</div>

<div id="toast" class="toast"></div>

<script>
  const $ = id => document.getElementById(id);
  let lastResult = '';

  function toast(msg) {
    const t = $('toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(t._t);
    t._t = setTimeout(() => t.classList.remove('show'), 2200);
  }

  async function pasteFromClipboard() {
    try {
      const text = await navigator.clipboard.readText();
      $('url').value = text.trim();
      toast('تم اللصق ✓');
    } catch {
      toast('ما قدرت أقرأ الحافظة');
    }
  }

  function showResult(success, text, meta = '') {
    const box = $('result');
    box.classList.remove('success', 'error');
    box.classList.add('show', success ? 'success' : 'error');
    $('resultTitle').textContent = success ? '✓ تم التخطي بنجاح' : '✗ فشل التخطي';
    $('resultBody').textContent = text;
    $('resultMeta').textContent = meta;
    lastResult = text;
  }

  async function copyResult() {
    if (!lastResult) return;
    try {
      await navigator.clipboard.writeText(lastResult);
      toast('تم النسخ ✓');
    } catch {
      toast('فشل النسخ');
    }
  }

  async function runBypass() {
    const url = $('url').value.trim();
    if (!url) { toast('الصق رابط أول'); return; }
    if (!/^https?:\/\//i.test(url)) { toast('الرابط غير صالح'); return; }

    const btn = $('submitBtn');
    btn.disabled = true;
    btn.classList.add('loading');
    $('status').textContent = 'يعالج...';
    const start = Date.now();

    try {
      const res = await fetch('/api/bypass', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });
      const data = await res.json();
      const dur = ((Date.now() - start) / 1000).toFixed(2);

      if (data.success && data.result) {
        showResult(true, data.result, `⏱ ${dur}s`);
        $('status').textContent = 'تم';
      } else {
        showResult(false, data.error || data.result || 'خطأ غير معروف', `⏱ ${dur}s`);
        $('status').textContent = 'فشل';
      }
    } catch (err) {
      showResult(false, 'Network error: ' + err.message, '');
      $('status').textContent = 'خطأ شبكة';
    } finally {
      btn.disabled = false;
      btn.classList.remove('loading');
    }
  }

  $('url').addEventListener('keydown', e => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) runBypass();
  });
</script>
</body>
</html>"""


# ============================================================
# DEBUG (silent logger — collects into buffer)
# ============================================================
class SilentDebug:
    def __init__(self):
        self.lines = []

    def _log(self, level, msg):
        line = f"[{level}] {msg}"
        self.lines.append(line)
        try:
            print(line, flush=True)
        except Exception:
            pass

    def info(self, m):    self._log("INFO", m)
    def warn(self, m):    self._log("WARN", m)
    def error(self, m):   self._log("ERROR", m)
    def success(self, m): self._log("OK", m)
    def custom(self, *a): self._log("CUSTOM", " ".join(str(x) for x in a))


debug = SilentDebug()


# ============================================================
# CF_Boom FALLBACK
# ============================================================
class CF_Boom:
    @staticmethod
    def getSession(url, proxy=None, verify=False):
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
        })
        if proxy:
            s.proxies = {"http": proxy, "https": proxy}
        return s

    @staticmethod
    def getResidentialProxy():
        return os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")

    @staticmethod
    def wildcard_search(text, pattern):
        match = re.search(r"document\.session\s*=\s*['\"]([^'\"]+)['\"]", text)
        return match.group(1) if match else None

    @staticmethod
    def decodeResp(response):
        if not hasattr(response, "content"):
            return str(response)
        content = response.content
        encoding = response.headers.get("content-encoding", "").lower()
        if encoding == "br" and brotli is not None:
            try:
                content = brotli.decompress(content)
            except Exception:
                pass
        elif encoding in ("gzip", "deflate"):
            try:
                if "gzip" in encoding:
                    content = zlib.decompress(content, zlib.MAX_WBITS | 32)
                else:
                    content = zlib.decompress(content)
            except Exception:
                pass
        return content.decode("utf-8", errors="ignore")


# ============================================================
# UTILS
# ============================================================
def cln_url(u):
    return re.sub(r'<.*|".*', "", u)


def ext_info(response, pattern):
    match = re.search(pattern, response)
    return cln_url(match.group(1)) if match else None


def get_cdn_tid(content, url=None, delay=None):
    try:
        if content:
            soup = BeautifulSoup(content, "html.parser")
            for script in soup.find_all("script"):
                if script.string and "domain:" in script.string:
                    cd = re.search(r"cd: ([^']*),", script.string)
                    domain = re.search(r"domain: '([^']*)'", script.string)
                    key = re.search(r"key: '([^']*)'", script.string)
                    if cd and domain and key:
                        return (domain.group(1), cd.group(1), key.group(1), {"active": False})

            cdn = ext_info(content, r"p\['CDN_DOMAIN'\]\s*=\s*'([^']*)'")
            tid = ext_info(content, r"p\['TID'\]\s*=\s*(\d+)")
            key = ext_info(content, r"p\['KEY'\]\s*=\s*\"([^\"]*)\"")
            tir = ext_info(content, r"p\['TIER_ID'\]\s*=\s*['\"]([^'\"]+)['\"];")
            nta = ext_info(content, r"p\['NUM_OF_TASKS'\]\s*=\s*['\"]([^'\"]+)['\"];")
            ofr = ext_info(content, r"p\['OFFER'\]\s*=\s*['\"]([^'\"]+)['\"]")
            if cdn and tid and key:
                return (cdn, tid, key, {"active": True, "ntasks": nta, "tier": tir, "offer": ofr})
        return (None, None, None, {"active": True, "ntasks": None, "tier": None, "offer": None})
    except Exception as e:
        debug.error(f"get_cdn_tid error: {e}")
        return (None, None, None, {"active": True, "ntasks": None, "tier": None, "offer": None})


def decrypt_data(encoded_data, key_length=5):
    try:
        base64_decoded = base64.b64decode(encoded_data)
        key, encrypted_content = base64_decoded[:key_length], base64_decoded[key_length:]
        decrypted_data = bytes(b ^ key[i % key_length] for i, b in enumerate(encrypted_content))
        return decrypted_data.decode("utf-8").strip()
    except Exception as e:
        debug.error(f"Decryption error: {e}")
        return encoded_data.strip()


def transform_uuid(uuid_str):
    uppercase = [c for c in uuid_str if c.isupper()]
    key_str = "".join(uppercase[:4]) if uppercase else "KEY1"
    uuid_bytes = uuid_str.encode("utf-8")
    key_bytes = key_str.encode("utf-8")
    xor_result = bytes(uuid_bytes[i] ^ key_bytes[i % len(key_bytes)] for i in range(len(uuid_bytes)))
    return base64.b64encode(xor_result).decode("utf-8")


def botd_create(session_uuid):
    transformed = transform_uuid(session_uuid)
    aes_key = hashlib.sha256(transformed.encode()).digest()
    iv = os.urandom(12)
    timestamp = int(time.time() * 1000)
    botd = {
        "bot": False,
        "timestamp": timestamp,
        "webGLSolution": {
            "uuid": session_uuid,
            "nonce": random.randint(1, 3000),
            "time": random.randint(100, 5000),
        },
    }
    plaintext = json.dumps(botd, separators=(",", ":")).encode()
    encryptor = AESGCM(aes_key)
    ciphertext = encryptor.encrypt(iv, plaintext, None)
    encrypted = base64.b64encode(iv + ciphertext).decode()
    botd["encrypted"] = encrypted
    return json.dumps(botd, separators=(",", ":"))


def getParameters(raw_string):
    if raw_string.strip().endswith(";"):
        raw_string = raw_string.strip()[:-1]
    raw_string = raw_string.replace("false", "False").replace("true", "True").replace("null", "None")
    data = ast.literal_eval(raw_string)
    return {
        "tc_domain": data[29],
        "websocket_domain": data[9],
    }


# ============================================================
# CORE — WEBSOCKET BYPASS
# ============================================================
def canserbero(session, server, syncer, urid, p_key, tid, session_id, isLLBS, task_id, TLeft, APUrl):
    if websocket is None:
        debug.error("websocket-client not installed")
        return None

    catnumber = task_id
    numbers = [int(urid[-5:]) % 3] + [i for i in range(3) if i != int(urid[-5:]) % 3]
    debug.info(f"Trying servers: {numbers}")

    proxy_dict = getattr(session, "proxies", {}) or {}
    proxy_url = proxy_dict.get("https") or proxy_dict.get("http")
    proxy_kwargs = {}
    if proxy_url:
        try:
            parsed = urlparse(proxy_url)
            proxy_kwargs = {
                "http_proxy_host": parsed.hostname,
                "http_proxy_port": parsed.port or 80,
            }
            if parsed.username and parsed.password:
                proxy_kwargs["http_proxy_auth"] = (parsed.username, parsed.password)
        except Exception:
            proxy_kwargs = {}

    for nmb in numbers:
        current_server = f"{nmb}.{server}"
        ws = None

        try:
            threading.Thread(
                target=lambda s=current_server: session.post(
                    f"https://{s}/st?uid={urid}&cat={catnumber}", timeout=5
                ),
                daemon=True,
            ).start()
        except Exception:
            pass

        try:
            if APUrl:
                threading.Thread(
                    target=lambda: session.get(f"https:{APUrl}", timeout=5),
                    daemon=True,
                ).start()
        except Exception:
            pass

        try:
            url = (f"wss://{current_server}/c?"
                   f"uid={urid}&cat={catnumber}&key={p_key}"
                   f"&session_id={session_id}&is_loot={isLLBS}&tid={tid}")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
            cookie_str = "; ".join([f"{k}={v}" for k, v in session.cookies.items()])
            if cookie_str:
                headers["Cookie"] = cookie_str

            debug.custom("AdMaven", f"WS connecting: {current_server} ({catnumber})")

            ws = websocket.create_connection(
                url,
                timeout=8,
                header=headers,
                origin=f"https://{urlparse('https://' + server).hostname}",
                **proxy_kwargs,
            )
            ws.settimeout(8)
            ws.send("0")

            max_wait = 15
            start_time = time.time()
            ping_interval = 3
            last_ping = time.time()

            while time.time() - start_time < max_wait:
                try:
                    ws.settimeout(1)
                    message = ws.recv()
                    if isinstance(message, bytes):
                        message = message.decode("utf-8")
                    if isinstance(message, str) and message.startswith("r:"):
                        payload = message[2:]
                        result = decrypt_data(payload)
                        debug.success(f"OK on {current_server}")
                        try:
                            ws.close()
                        except Exception:
                            pass
                        return result
                    last_ping = time.time()
                except websocket.WebSocketTimeoutException:
                    if time.time() - last_ping >= ping_interval:
                        try:
                            ws.send("0")
                            last_ping = time.time()
                        except Exception:
                            break
                    continue
                except Exception as e:
                    debug.warn(f"WS recv error: {e}")
                    break

            debug.warn(f"No response from {current_server}")
        except websocket.WebSocketException as e:
            debug.error(f"WS error on {current_server}: {e}")
        except Exception as e:
            debug.error(f"Canserbero error on {current_server}: {e}")
        finally:
            if ws:
                try:
                    ws.close()
                except Exception:
                    pass

    debug.error("All servers exhausted")
    return None


# ============================================================
# MAIN BYPASS FLOW
# ============================================================
def OG_getDest(url):
    hostname = urlparse(url).hostname
    try:
        try:
            session = CF_Boom.getSession(
                f"https://{hostname}",
                CF_Boom.getResidentialProxy(),
                False,
            )
        except Exception:
            session = requests.Session()

        initial = session.get(url, timeout=10)
        sess_uuid = CF_Boom.wildcard_search(initial.text, "<script>document.session = '*'</script>")
        if not sess_uuid:
            return "bypass fail! Session UUID not found"
        debug.info(f"Session UUID: {sess_uuid}")

        cdn, tid, key, GisLLBS = get_cdn_tid(initial.text, url, 1)
        if not all([cdn, tid, key]):
            return "bypass fail! CDN/TID/KEY not found"

        isLLBS = GisLLBS.get("active", False)
        isLLBS_str = "1" if isLLBS else "0"

        content = CF_Boom.decodeResp(
            session.get(f"https://{cdn}/?tid={tid}&params_only=1", timeout=10)
        )
        params = getParameters(content)
        SYNCER = params.get("tc_domain")

        if not SYNCER:
            return "bypass fail! tc_domain not found"

        if isLLBS and sess_uuid:
            try:
                threading.Thread(
                    target=lambda: session.post(
                        f"https://{hostname}/verify",
                        json={"session": sess_uuid},
                        timeout=8,
                    ),
                    daemon=True,
                ).start()
            except Exception:
                pass

        mess_session = str(random.randint(100000000000000000, 999999999999999999))
        botd_payload = botd_create(sess_uuid)

        TCData = {
            "tid": int(tid),
            "bl": [18, 2, 33, 7, 21, 49],
            "session": mess_session,
            "max_tasks": 1,
            "design_id": 114,
            "cur_url": str(url),
            "doc_ref": "",
            "num_of_tasks": "1",
            "is_loot": isLLBS,
            "rkey": key,
            "cookie_id": str(random.randint(100000000, 999999999)),
            "botd": botd_payload,
            "botds": sess_uuid,
            "offer": "0",
            "tier_id": 4,
            "taboola_user_sync": "",
            "fid": -1,
            "clid": str(uuid.uuid4()),
        }

        rawr = session.post(f"https://{SYNCER}/tc", json=TCData, timeout=10)
        debug.info(f"TC status: {rawr.status_code}")

        if rawr.status_code == 428:
            return "bypass fail! 428 — patched?"

        if rawr.status_code != 200:
            return f"bypass fail! TC status {rawr.status_code}"

        try:
            TCP = rawr.json()
            if isinstance(TCP, list):
                if not TCP:
                    return "bypass fail! Empty TC response"
                TCP = TCP[0]

            task_id = TCP.get("task_id", 0)
            urid = TCP.get("urid")
            TLeft = TCP.get("auto_complete_seconds")
            APUrl = TCP.get("action_pixel_url", "")

            if not urid:
                return "bypass fail! No urid"

            daserver = params.get("websocket_domain")
            if not daserver:
                return "bypass fail! No websocket_domain"

            result = canserbero(
                session, daserver, SYNCER, urid, key, tid,
                mess_session, isLLBS_str, task_id, TLeft, APUrl,
            )
            if result:
                return result
            return "bypass fail! Canserbero returned no valid info"
        except Exception as e:
            debug.error(f"TC parse error: {traceback.format_exc()}")
            return f"bypass fail! TC parse error: {e}"

    except Exception as e:
        debug.error(f"OG_getDest error: {traceback.format_exc()}")
        return f"bypass fail! {str(e)}"


# ============================================================
# FLASK ROUTES
# ============================================================
@app.route("/", methods=["GET"])
def index():
    return Response(INDEX_HTML, mimetype="text/html")


@app.route("/api/bypass", methods=["POST", "OPTIONS"])
def bypass_endpoint():
    global debug
    debug = SilentDebug()

    if request.method == "OPTIONS":
        resp = app.make_default_options_response()
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp

    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}

    url = (data.get("url") or "").strip()
    if not url or not re.match(r"^https?://", url, re.I):
        return jsonify({"success": False, "error": "Invalid URL"}), 400

    start = time.time()
    try:
        result = OG_getDest(url)
    except Exception as e:
        result = f"bypass fail! {e}"

    dur = round(time.time() - start, 2)
    success = not (result or "").lower().startswith("bypass fail")

    response = jsonify({
        "success": success,
        "result": result if success else None,
        "error": None if success else result,
        "duration": dur,
        "logs": debug.lines[-30:],
    })
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
