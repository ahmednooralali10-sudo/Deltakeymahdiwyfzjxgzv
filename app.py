"""
LootLabs / Loot-Link bypass — Flask API for Vercel.
Single-file serverless handler. All logic ported from original CLI.
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
from flask import Flask, request, jsonify

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
    return jsonify({
        "name": "LootLabs Bypass API",
        "usage": "POST /api/bypass with JSON {url: 'https://loot-link.com/...'}",
        "built_by": "ALPHA XK",
    })


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


# For local testing
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
