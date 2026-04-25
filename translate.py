import sys, time, random, json, os, requests, warnings, re
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings('ignore', category=XMLParsedAsHTMLWarning)

FILE = sys.argv[1]

CACHE_PATH = "cache.json"
STATE_PATH = "state.json"

CACHE = json.load(open(CACHE_PATH)) if os.path.exists(CACHE_PATH) else {}
STATE = json.load(open(STATE_PATH)) if os.path.exists(STATE_PATH) else {"done": [], "fail": []}

def save_all():
    json.dump(STATE, open(STATE_PATH, "w"))
    json.dump(CACHE, open(CACHE_PATH, "w"), ensure_ascii=False)

# -------------------------
# 🌐 ENDPOINTS
# -------------------------
ENDPOINTS = [
    "https://translate.googleapis.com/translate_a/single",
    "https://clients5.google.com/translate_a/single",
    "https://clients6.google.com/translate_a/single",
]

fail_streak = 0
FAIL_LIMIT = 10

def call_api(url, text):
    params = {"client":"gtx","sl":"auto","tl":"vi","dt":"t","q": text}
    r = requests.get(url, params=params, timeout=10)
    return "".join([x[0] for x in r.json()[0] if x[0]])

# -------------------------
# 🔍 CHECK CHẤT LƯỢNG
# -------------------------
def is_bad_translation(src, out):
    if not out or len(out.strip()) < 2:
        return True
    if out.strip() == src.strip():
        return True

    eng_ratio = sum(c.isascii() for c in out) / max(len(out),1)
    return eng_ratio > 0.85

# -------------------------
# 🚀 TRANSLATE BLOCK (ANTI-TREO)
# -------------------------
def translate_block(text):
    global fail_streak

    t = text.strip()
    if not t or len(t) < 2:
        return text

    if t in CACHE:
        return CACHE[t]

    MAX_RETRY = 3  # 🔥 fail nhanh

    for attempt in range(MAX_RETRY):
        try:
            url = random.choice(ENDPOINTS)
            result = call_api(url, t)

            if not is_bad_translation(t, result):
                CACHE[t] = result
                fail_streak = 0
                time.sleep(0.6 + random.random())
                return result

            raise Exception("bad")

        except:
            wait = 2 + random.random()
            print(f"⚠️ retry {attempt+1}, wait {wait:.1f}s")
            time.sleep(wait)
            fail_streak += 1

    # 🔥 không treo — skip luôn
    print("❌ skip đoạn:", t[:60])
    return f"[SKIP]{t}"

# -------------------------
# 🧠 CHUNK
# -------------------------
def smart_chunk(text, max_len=1200):
    sents = re.split(r'(?<=[.!?])\s+', text)
    chunks, cur = [], ""
    for s in sents:
        if len(cur) + len(s) > max_len:
            chunks.append(cur.strip())
            cur = s
        else:
            cur += " " + s
    if cur:
        chunks.append(cur.strip())
    return chunks

SKIP = ['nav','toc','cover','copyright','acknowledgment','about',
        'author','index','biblio','dedication','colophon','halftitle']

def should_skip(name):
    return any(k in name.lower() for k in SKIP)

# -------------------------
# 🔍 CHECK CHAPTER
# -------------------------
def check_quality(soup):
    text = soup.get_text()
    if not text:
        return False
    eng_ratio = sum(c.isascii() for c in text) / len(text)
    return eng_ratio < 0.8

# -------------------------
# 🚀 PROCESS CHAPTER (ANTI-TREO)
# -------------------------
def process_item(item):
    global fail_streak

    name = item.get_name()

    if name in STATE["done"]:
        return

    start_time = time.time()

    soup = BeautifulSoup(item.get_content().decode('utf-8', errors='ignore'), 'lxml')

    tags = soup.find_all(['p','h1','h2','h3','h4','li','blockquote'])
    texts = [t.get_text(strip=True) for t in tags if len(t.get_text(strip=True)) > 5]

    if not texts:
        return

    chunks = smart_chunk("\n".join(texts))
    translated = []

    for c in chunks:

        # ⏱️ timeout tránh treo
        if time.time() - start_time > 120:
            print(f"⏱ skip chapter timeout: {name}")
            STATE["fail"].append(name)
            return

        if fail_streak >= FAIL_LIMIT:
            print("🛑 nhiều lỗi → nghỉ 60s")
            time.sleep(60)
            fail_streak = 0

        translated.append(translate_block(c))

    lines = "\n".join(translated).split("\n")

    i = 0
    for t in tags:
        if t.get_text(strip=True) and i < len(lines):
            t.string = lines[i]
            i += 1

    # 🔍 check chất lượng
    if not check_quality(soup):
        print(f"⚠️ chất lượng kém: {name}")
        STATE["fail"].append(name)
        return

    item.set_content(str(soup).encode('utf-8'))

    STATE["done"].append(name)
    save_all()

# -------------------------
# 🚀 MAIN
# -------------------------
print(f"📖 Reading: {FILE}")

book = epub.read_epub(FILE)

items = [it for it in book.get_items()
         if it.get_type() == ITEM_DOCUMENT and not should_skip(it.get_name())]

print(f"📚 Found {len(items)} chapters | done {len(STATE['done'])}")

for item in items:
    process_item(item)

print("🔍 FINAL CHECK...")
print(f"⚠️ failed: {len(STATE['fail'])}")

OUT = FILE.replace(".epub", "_TiengViet.epub")
epub.write_epub(OUT, book)

print(f"✅ DONE: {OUT}")
