import os
import html as htmllib
from functools import wraps

import requests
from flask import Flask, render_template_string, request, jsonify, session, redirect

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

# ==================== 설정 ====================
# 비밀값은 호스팅 서비스의 환경변수(Environment Variables)에 넣어주세요.
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
YOUR_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "7737429021")

# CHANGE_PIN: 각 사이트의 PIN을 바꿀 때 필요한 관리자용 6자리 코드
CHANGE_PIN = os.environ.get("CHANGE_PIN", "851215")

BG = "https://images.pexels.com/photos/30281995/pexels-photo-30281995.jpeg?auto=compress&cs=tinysrgb&w=1920"

# 사이트 3개 설정. 각 사이트는 탭(= 구글 드라이브 폴더)을 원하는 만큼 가질 수 있어요.
# 사이트 2, 3의 "folder"에 실제 폴더 ID를 넣으면 됩니다.
SITES = {
    "site1": {
        "name": "eco hcm 예약",
        "pin": os.environ.get("PIN_SITE1", "1234"),
        "bg": BG,
        "tabs": [
            {"label": "1번", "folder": "15cN-w5yjUTog-bXmDn8RGVTZzBDm6Uw_"},
            {"label": "2번", "folder": "1stNTBFJsKDiHymMFgAANcAZqwxpCom4y"},
        ],
    },
    "site2": {
        "name": "사이트 2",
        "pin": os.environ.get("PIN_SITE2", "1234"),
        "bg": BG,
        "tabs": [
            {"label": "1번", "folder": ""},
            {"label": "2번", "folder": ""},
        ],
    },
    "site3": {
        "name": "사이트 3",
        "pin": os.environ.get("PIN_SITE3", "1234"),
        "bg": BG,
        "tabs": [
            {"label": "1번", "folder": ""},
            {"label": "2번", "folder": ""},
        ],
    },
}

# 장바구니: carts[사이트][탭번호] = [{id, name}, ...]
carts = {sid: [[] for _ in s["tabs"]] for sid, s in SITES.items()}


# ==================== 공통 ====================
def login_required(f):
    """해당 사이트의 PIN을 통과한 세션만 허용"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        sid = kwargs.get("sid") or (request.get_json(silent=True) or {}).get("site") or request.args.get("site")
        if sid not in SITES or sid not in session.get("authed", []):
            return jsonify({"success": False, "message": "PIN 인증이 필요합니다."}), 401
        return f(*args, **kwargs)
    return wrapper


def find_cart(site, tab):
    try:
        return carts[site][int(tab)]
    except (KeyError, ValueError, IndexError, TypeError):
        return None


def get_drive_photos(folder_id):
    if not folder_id:
        return []
    try:
        response = requests.get(
            "https://www.googleapis.com/drive/v3/files",
            params={
                "q": f"'{folder_id}' in parents and (mimeType contains 'image/' or mimeType contains 'video/') and trashed=false",
                "fields": "files(id, name, mimeType)",
                "orderBy": "name",
                "key": GOOGLE_API_KEY,
            },
            timeout=10,
        )
        return response.json().get("files", [])
    except Exception as e:
        print("Drive 오류:", e)
        return []


# ==================== PIN 페이지 ====================
PIN_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ site.name }} - PIN 인증</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-950 text-white min-h-screen flex items-center justify-center p-4">
    <div class="bg-gray-900 p-12 rounded-3xl w-full max-w-md text-center">
        <a href="/" class="block text-left text-gray-400 hover:text-white mb-6">← 사이트 선택</a>
        <h1 class="text-4xl font-bold mb-4">🔒 {{ site.name }}</h1>
        <p class="text-gray-400 mb-10 text-lg">이 사이트의 4자리 PIN 번호를 입력해주세요</p>
        <input id="pinInput" type="password" maxlength="4" inputmode="numeric"
               class="w-full bg-gray-800 text-5xl text-center tracking-widest p-6 rounded-2xl focus:outline-none focus:ring-4 focus:ring-blue-500 mb-8"
               placeholder="••••" autofocus>
        <button onclick="checkPin()" class="w-full bg-blue-600 hover:bg-blue-700 py-6 rounded-2xl text-2xl font-bold">확인</button>
        <button onclick="goToChangePin()" class="mt-6 w-full text-blue-400 hover:text-blue-300 py-3 text-sm">PIN 번호 변경하기</button>
    </div>
    <script>
    const SID = {{ sid|tojson }};
    document.getElementById('pinInput').addEventListener('keydown', e => { if (e.key === 'Enter') checkPin(); });
    function post(url, body) {
        return fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}).then(r => r.json());
    }
    function checkPin() {
        post('/s/' + SID + '/check_pin', {pin: document.getElementById('pinInput').value.trim()}).then(data => {
            if (data.success) window.location.href = "/s/" + SID;
            else { alert("❌ PIN 번호가 틀렸습니다."); document.getElementById('pinInput').value = ''; }
        });
    }
    function goToChangePin() {
        const pin = prompt("PIN 변경 창에 들어가려면 6자리 PIN을 입력하세요:");
        if (!pin) return;
        post('/s/' + SID + '/check_change_pin', {pin: pin}).then(data => {
            if (data.success) window.location.href = "/s/" + SID + "/change_pin";
            else alert("❌ 6자리 PIN이 틀렸습니다.");
        });
    }
    </script>
</body>
</html>"""

CHANGE_PIN_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ site.name }} - PIN 번호 변경</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-950 text-white min-h-screen flex items-center justify-center p-4">
    <div class="bg-gray-900 p-12 rounded-3xl w-full max-w-md text-center">
        <h1 class="text-4xl font-bold mb-8">🔑 {{ site.name }}<br>PIN 변경</h1>
        <p class="text-gray-400 mb-8">새로운 4자리 PIN 번호를 입력하세요</p>
        <input id="newPin" type="password" maxlength="4" inputmode="numeric"
               class="w-full bg-gray-800 text-5xl text-center tracking-widest p-6 rounded-2xl mb-8 focus:outline-none focus:ring-4 focus:ring-green-500"
               placeholder="••••" autofocus>
        <button onclick="changePin()" class="w-full bg-green-600 hover:bg-green-700 py-6 rounded-2xl text-2xl font-bold">PIN 번호 변경하기</button>
        <button onclick="window.location.href='/s/{{ sid }}'" class="mt-6 w-full text-gray-400 py-3">취소하고 돌아가기</button>
    </div>
    <script>
    const SID = {{ sid|tojson }};
    function changePin() {
        const newPin = document.getElementById('newPin').value.trim();
        if (!/^\\d{4}$/.test(newPin)) { alert("PIN은 정확히 4자리 숫자여야 합니다."); return; }
        fetch('/s/' + SID + '/update_pin', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({new_pin: newPin})})
        .then(r => r.json()).then(data => {
            if (data.success) { alert("✅ PIN 번호가 변경되었습니다!"); window.location.href = '/s/' + SID; }
            else alert("변경 실패");
        });
    }
    </script>
</body>
</html>"""


@app.route("/s/<sid>/check_pin", methods=["POST"])
def check_pin(sid):
    site = SITES.get(sid)
    if not site:
        return jsonify({"success": False}), 404
    data = request.get_json(silent=True) or {}
    if str(data.get("pin")) == site["pin"]:
        session["authed"] = sorted(set(session.get("authed", [])) | {sid})
        return jsonify({"success": True})
    return jsonify({"success": False})


@app.route("/s/<sid>/check_change_pin", methods=["POST"])
def check_change_pin(sid):
    if sid not in SITES:
        return jsonify({"success": False}), 404
    data = request.get_json(silent=True) or {}
    if str(data.get("pin")) == CHANGE_PIN:
        session["can_change_pin"] = sid
        return jsonify({"success": True})
    return jsonify({"success": False})


@app.route("/s/<sid>/change_pin")
def change_pin_page(sid):
    if sid not in SITES or session.get("can_change_pin") != sid:
        return redirect("/")
    return render_template_string(CHANGE_PIN_HTML, sid=sid, site=SITES[sid])


@app.route("/s/<sid>/update_pin", methods=["POST"])
def update_pin(sid):
    if sid not in SITES or session.get("can_change_pin") != sid:
        return jsonify({"success": False, "message": "권한이 없습니다."}), 403
    new_pin = str((request.get_json(silent=True) or {}).get("new_pin", ""))
    if len(new_pin) == 4 and new_pin.isdigit():
        SITES[sid]["pin"] = new_pin
        session.pop("can_change_pin", None)
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "PIN은 4자리 숫자여야 합니다."})


# ==================== 사이트 선택 (런처) ====================
LAUNCHER_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>사이트 선택</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-950 text-white min-h-screen">
<div class="max-w-5xl mx-auto p-6">
    <div class="flex justify-between items-center my-10">
        <h1 class="text-4xl font-bold">사이트 선택</h1>
        <a href="/logout" class="text-gray-400 hover:text-white">모두 잠그기</a>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        {% for sid, s in sites.items() %}
        <a href="/s/{{ sid }}" class="block bg-gray-900 hover:bg-gray-800 rounded-3xl overflow-hidden shadow-xl">
            <div class="h-40 bg-cover bg-center" style="background-image:url('{{ s.bg }}')"></div>
            <div class="p-6">
                <h2 class="text-2xl font-bold">{{ '🔓' if sid in authed else '🔒' }} {{ s.name }}</h2>
                <p class="text-gray-400 mt-2">{{ s.tabs|map(attribute='label')|join(', ') }}</p>
            </div>
        </a>
        {% endfor %}
    </div>
</div>
</body>
</html>"""


@app.route("/")
def home():
    return render_template_string(LAUNCHER_HTML, sites=SITES, authed=session.get("authed", []))


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ==================== 개별 사이트 ====================
SITE_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ site.name }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <style>
        .tab-active { border-bottom: 4px solid #3b82f6; font-weight: bold; color: white; }
        img { cursor: pointer; transition: transform 0.2s; }
        img:hover { transform: scale(1.05); }
        .cart-img { max-height: 180px; object-fit: cover; border-radius: 12px; }
        body {
            background-image: url('{{ site.bg }}');
            background-size: cover; background-position: center;
            background-attachment: fixed; background-repeat: no-repeat; min-height: 100vh;
        }
        .overlay { background-color: rgba(0, 0, 0, 0.82); min-height: 100vh; }
    </style>
</head>
<body class="text-white">
<div class="overlay">

<div class="max-w-7xl mx-auto p-6">
    <a href="/" class="text-gray-400 hover:text-white">← 사이트 선택</a>
    <h1 class="text-5xl font-bold text-center my-10 drop-shadow-2xl">{{ site.name }}</h1>

    <div class="flex justify-center border-b border-gray-700 mb-10 overflow-x-auto">
        {% for tab in site.tabs %}
        <button onclick="switchTab({{ loop.index0 }})" id="tab{{ loop.index0 }}"
                class="tab px-10 py-4 text-xl whitespace-nowrap {{ 'tab-active' if loop.first }}">{{ tab.label }}</button>
        {% endfor %}
    </div>

    {% for tab in site.tabs %}
    {% set ti = loop.index0 %}
    <div id="gallery{{ ti }}" class="{{ '' if loop.first else 'hidden' }}">
        {% if photos[ti] %}
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {% for photo in photos[ti] %}
            <div class="bg-gray-800 rounded-3xl overflow-hidden shadow-xl">
                <img src="https://drive.google.com/thumbnail?id={{ photo.id }}&sz=w800"
                     onclick="openLightbox(this, {{ ti }})" class="w-full h-64 object-cover">
                <div class="p-4"><p class="font-medium truncate">{{ photo.name }}</p></div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <p class="text-center text-gray-400 py-20">표시할 사진이 없습니다.</p>
        {% endif %}
    </div>
    {% endfor %}
</div>

<div class="fixed bottom-8 right-8 flex flex-col gap-3 z-40">
    {% for tab in site.tabs %}
    <button onclick="showCart({{ loop.index0 }})" class="bg-green-600 hover:bg-green-700 w-64 py-4 rounded-2xl text-lg font-bold shadow-2xl">{{ tab.label }} 장바구니 보기</button>
    {% endfor %}
</div>

<!-- 장바구니 모달 -->
<div id="cartModal" class="hidden fixed inset-0 bg-black/90 flex items-center justify-center z-50">
    <div class="bg-gray-800 rounded-3xl p-8 w-full max-w-2xl max-h-[85vh] overflow-auto">
        <h2 id="modalTitle" class="text-3xl font-bold mb-6"></h2>
        <div id="cartList" class="grid grid-cols-2 gap-4 mb-8"></div>
        <button onclick="goToReserve()" class="w-full bg-red-600 hover:bg-red-700 py-5 text-xl rounded-2xl font-bold">예약하기</button>
        <button onclick="hideCart()" class="mt-4 w-full text-gray-400 py-3">닫기</button>
    </div>
</div>

<!-- 예약 모달 -->
<div id="reserveModal" class="hidden fixed inset-0 bg-black/90 flex items-center justify-center z-50">
    <div class="bg-gray-800 rounded-3xl p-8 w-full max-w-md">
        <h2 class="text-3xl font-bold mb-6">예약 정보</h2>
        <input id="reserveDate" type="date" class="w-full p-4 bg-gray-700 rounded-2xl mb-4 text-white">
        <input id="reserveTgId" type="text" placeholder="Telegram ID 또는 @아이디" class="w-full p-4 bg-gray-700 rounded-2xl mb-6 text-white">
        <button id="submitBtn" onclick="submitReservation()" class="w-full bg-green-600 hover:bg-green-700 py-5 text-xl rounded-2xl font-bold">✅ 예약 전송하기</button>
        <button onclick="hideReserveModal()" class="mt-4 w-full text-gray-400 py-3">취소</button>
    </div>
</div>

<!-- 라이트박스 -->
<div id="lightbox" class="hidden fixed inset-0 bg-black/95 flex items-center justify-center z-[60]">
    <div class="relative max-w-5xl w-full px-4">
        <button onclick="closeLightbox()" class="absolute -top-12 right-4 text-white text-5xl hover:text-gray-300">&times;</button>
        <img id="lightboxImg" class="max-h-[80vh] mx-auto rounded-2xl shadow-2xl" src="">
        <button onclick="prevImage()" class="absolute left-8 top-1/2 -translate-y-1/2 bg-black/60 text-white text-5xl w-14 h-14 rounded-full flex items-center justify-center">&lt;</button>
        <button onclick="nextImage()" class="absolute right-8 top-1/2 -translate-y-1/2 bg-black/60 text-white text-5xl w-14 h-14 rounded-full flex items-center justify-center">&gt;</button>
        <button onclick="addCurrentToCart()" class="absolute bottom-8 right-8 bg-blue-600 hover:bg-blue-700 px-8 py-4 rounded-2xl text-lg font-bold flex items-center gap-2">
            <i class="fas fa-cart-plus"></i> 장바구니에 담기
        </button>
        <p id="lightboxCaption" class="text-center text-white mt-6 text-lg"></p>
    </div>
</div>

<script>
const SITE = {{ sid|tojson }};
const TABS = {{ site.tabs|map(attribute='label')|list|tojson }};
let currentPhotos = [], currentIndex = 0, currentTab = 0, isReserving = false;

function postJson(url, body) {
    return fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}).then(r => r.json());
}

function switchTab(n) {
    TABS.forEach((_, i) => {
        document.getElementById('tab' + i).classList.toggle('tab-active', i === n);
        document.getElementById('gallery' + i).classList.toggle('hidden', i !== n);
    });
    currentTab = n;
}

function openLightbox(img, tab) {
    currentTab = tab;
    currentPhotos = Array.from(document.querySelectorAll('#gallery' + tab + ' img'));
    currentIndex = currentPhotos.indexOf(img);
    showCurrentImage();
    document.getElementById('lightbox').classList.remove('hidden');
}
function showCurrentImage() {
    const img = currentPhotos[currentIndex];
    document.getElementById('lightboxImg').src = img.src.replace('&sz=w800', '&sz=w1200');
    document.getElementById('lightboxCaption').textContent = img.parentElement.querySelector('p').textContent || '';
}
function prevImage() { currentIndex = (currentIndex - 1 + currentPhotos.length) % currentPhotos.length; showCurrentImage(); }
function nextImage() { currentIndex = (currentIndex + 1) % currentPhotos.length; showCurrentImage(); }
function closeLightbox() { document.getElementById('lightbox').classList.add('hidden'); }

function addCurrentToCart() {
    const img = currentPhotos[currentIndex];
    const m = img.src.match(/id=([a-zA-Z0-9_-]+)/);
    if (m) addToCart(currentTab, m[1], document.getElementById('lightboxCaption').textContent);
}
function addToCart(tab, id, name) {
    postJson('/add_to_cart', {site: SITE, tab: tab, id: id, name: name}).then(d => alert(d.message));
}

function showCart(tab) {
    currentTab = tab;
    fetch('/get_cart?site=' + SITE + '&tab=' + tab).then(r => r.json()).then(items => {
        document.getElementById('modalTitle').textContent = TABS[tab] + ' 장바구니 (' + items.length + '장)';
        const box = document.getElementById('cartList');
        box.innerHTML = '';
        items.forEach((item, index) => {
            const div = document.createElement('div');
            div.className = 'bg-gray-700 p-3 rounded-2xl relative';
            div.innerHTML = '<img class="cart-img w-full"><p class="mt-2 text-center truncate"></p>' +
                '<button class="absolute top-2 right-2 bg-red-600 hover:bg-red-700 text-white w-8 h-8 rounded-full flex items-center justify-center text-xl font-bold">×</button>';
            div.querySelector('img').src = 'https://drive.google.com/thumbnail?id=' + encodeURIComponent(item.id) + '&sz=w400';
            div.querySelector('p').textContent = item.name;
            div.querySelector('button').onclick = () => removeFromCart(index, tab);
            box.appendChild(div);
        });
        document.getElementById('cartModal').classList.remove('hidden');
    });
}
function removeFromCart(index, tab) {
    if (!confirm("이 사진을 장바구니에서 삭제하시겠습니까?")) return;
    postJson('/remove_from_cart', {site: SITE, tab: tab, index: index}).then(d => { alert(d.message); showCart(tab); });
}

function hideCart() { document.getElementById('cartModal').classList.add('hidden'); }
function goToReserve() { hideCart(); document.getElementById('reserveModal').classList.remove('hidden'); resetReserveButton(); }
function hideReserveModal() { document.getElementById('reserveModal').classList.add('hidden'); resetReserveButton(); }
function resetReserveButton() {
    isReserving = false;
    const btn = document.getElementById('submitBtn');
    btn.disabled = false; btn.textContent = '✅ 예약 전송하기';
}

function submitReservation() {
    if (isReserving) return;
    const date = document.getElementById('reserveDate').value;
    const tgId = document.getElementById('reserveTgId').value || "미입력";
    if (!date) { alert("날짜를 선택해주세요!"); return; }
    isReserving = true;
    const btn = document.getElementById('submitBtn');
    btn.disabled = true; btn.textContent = '⏳ 예약 처리 중...';

    fetch('/get_cart?site=' + SITE + '&tab=' + currentTab).then(r => r.json()).then(photos => {
        if (!photos.length) { alert("장바구니가 비어 있습니다."); resetReserveButton(); return; }
        return postJson('/reserve', {site: SITE, tab: currentTab, photos: photos, date: date, tg_id: tgId}).then(d => {
            if (d.status === 'ok') { alert("✅ 예약이 Telegram으로 전송되었습니다!"); hideReserveModal(); }
            else { alert(d.message || "전송 중 오류가 발생했습니다."); resetReserveButton(); }
        });
    }).catch(() => { alert("전송 중 오류가 발생했습니다."); resetReserveButton(); });
}
</script>
</div>
</body>
</html>"""


@app.route("/s/<sid>")
def site_page(sid):
    site = SITES.get(sid)
    if not site:
        return redirect("/")
    if sid not in session.get("authed", []):
        return render_template_string(PIN_HTML, sid=sid, site=site)
    photos = [get_drive_photos(t["folder"]) for t in site["tabs"]]
    return render_template_string(SITE_HTML, sid=sid, site=site, photos=photos)


# ====================== API ======================
@app.route("/add_to_cart", methods=["POST"])
@login_required
def add_to_cart():
    data = request.get_json(silent=True) or {}
    cart = find_cart(data.get("site"), data.get("tab"))
    if cart is None:
        return jsonify({"status": "error", "message": "잘못된 요청입니다."}), 400
    photo_id, name = data.get("id"), data.get("name")
    if any(item["id"] == photo_id for item in cart):
        return jsonify({"status": "duplicate", "message": "⚠️ 이미 추가된 사진입니다!"})
    cart.append({"id": photo_id, "name": name})
    return jsonify({"status": "ok", "message": f"✅ {name}을(를) 장바구니에 담았습니다!"})


@app.route("/get_cart")
@login_required
def get_cart():
    cart = find_cart(request.args.get("site"), request.args.get("tab"))
    return jsonify(cart if cart is not None else [])


@app.route("/remove_from_cart", methods=["POST"])
@login_required
def remove_from_cart():
    data = request.get_json(silent=True) or {}
    cart = find_cart(data.get("site"), data.get("tab"))
    try:
        index = int(data.get("index", -1))
    except (TypeError, ValueError):
        index = -1
    if cart is not None and 0 <= index < len(cart):
        removed = cart.pop(index)
        return jsonify({"status": "ok", "message": f"🗑️ {removed['name']}을(를) 삭제했습니다."})
    return jsonify({"status": "error", "message": "삭제할 수 없습니다."})


@app.route("/reserve", methods=["POST"])
@login_required
def reserve():
    data = request.get_json(silent=True) or {}
    site_id = data.get("site")
    cart = find_cart(site_id, data.get("tab"))
    if cart is None:
        return jsonify({"status": "error", "message": "잘못된 요청입니다."}), 400

    site = SITES[site_id]
    tab_label = site["tabs"][int(data.get("tab"))]["label"]
    photos = data.get("photos", [])
    esc = htmllib.escape
    names = "\n".join(esc(str(p.get("name", ""))) for p in photos)
    msg = (
        f"📩 <b>새 예약 들어왔습니다!</b> ({esc(site['name'])} / {esc(tab_label)})\n\n"
        f"📅 날짜: {esc(str(data.get('date')))}\n"
        f"👤 고객 Telegram: {esc(str(data.get('tg_id')))}\n"
        f"🖼️ 미디어 ({len(photos)}개):\n{names}"
    )

    api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    try:
        requests.post(f"{api}/sendMessage",
                      json={"chat_id": YOUR_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
        for p in photos:
            requests.post(f"{api}/sendPhoto",
                          json={"chat_id": YOUR_CHAT_ID,
                                "photo": f"https://drive.google.com/uc?id={p.get('id')}",
                                "caption": p.get("name", "")}, timeout=10)
    except Exception as e:
        print("Telegram 오류:", e)
        return jsonify({"status": "error", "message": "Telegram 전송에 실패했습니다."}), 502

    cart.clear()
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
