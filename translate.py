import sys, time, random, json, os, requests
import ebooklib
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup
from tqdm import tqdm

# =====================
# INPUT
# =====================
FILE = sys.argv[1]

CACHE_PATH = "cache.json"
STATE_PATH = "state.json"

CACHE = json.load(open(CACHE_PATH)) if os.path.exists(CACHE_PATH) else {}
STATE = json.load(open(STATE_PATH)) if os.path.exists(STATE_PATH) else {"done": []}

def save_all():
    json.dump(CACHE, open(CACHE_PATH, "w"), ensure_ascii=False)
    json.dump(STATE, open(STATE_PATH, "w"))

# =====================
# API CONFIG
# =====================
GOOGLE_ENDPOINTS = [
    "https://translate.googleapis.com/translate_a/single",
    "https://clients5.google.com/translate_a/single",
]

LIBRE_ENDPOINTS = [
    "https://libretranslate.de/translate",
    "https://translate.argosopentech.com/translate"
]

fail_streak = 0

# =====================
# UTILS
# =====================
def is_vietnamese(text):
    vi = "àáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ"
    return any(c in text.lower() for c in vi)

# =====================
# GOOGLE
# =====================
def call_google(text):
    url = random.choice(GOOGLE_ENDPOINTS)
    params = {"client":"gtx","sl":"auto","tl":"vi","dt":"t","q": text}

    r = requests.get(url, params=params, timeout=8)
    return "".join([x[0] for x in r.json()[0] if x[0]])

# =====================
# LIBRE
# =====================
def call_libre(text):
    for url in LIBRE_ENDPOINTS:
        try:
            res = requests.post(
                url,
                json={
                    "q": text,
                    "source": "auto",
                    "target": "vi",
                    "format": "text"
                },
                timeout=10
            )

            data = res.json()
            out = data.get("translatedText", "")

            if out and out.strip() != text.strip():
                return out

        except:
            continue

    return None

# =====================
# TRANSLATE (HYBRID)
# =====================
def translate_chunk(text):
    global fail_streak

    if text in CACHE:
        return CACHE[text]

    t = text.strip()
    if not t:
        return t

    # 🥇 GOOGLE FIRST
    for attempt in range(2):
        try:
            out = call_google(t)

            if out and out.strip() != t and is_vietnamese(out):
                CACHE[t] = out
                fail_streak = 0
                time.sleep(0.2 + random.random()*0.3)
                return out

            raise Exception("bad google")

        except:
            time.sleep(0.5 + attempt)

    # 🛟 LIBRE FALLBACK
    print("⚠️ Google fail → Libre")

    for attempt in range(2):
        out = call_libre(t)

        if out:
            CACHE[t] = out
            fail_streak = 0
            time.sleep(0.3 + random.random()*0.3)
            return out

        time.sleep(1 + attempt)

    fail_streak += 1
    return None

# =====================
# CHUNK ENGINE
# =====================
def build_chunks(tags, max_len=1200):
    chunks = []
    current = []
    length = 0

    for idx, tag in enumerate(tags):
        text = tag.get_text(strip=True)

        if length + len(text) > max_len and current:
            chunks.append(current)
            current = []
            length = 0

        current.append((idx, text))
        length += len(text)

    if current:
        chunks.append(current)

    return chunks

# =====================
# PROCESS
# =====================
def process_item(item):
    name = item.get_name()

    if name in STATE["done"]:
        return

    soup = BeautifulSoup(item.get_content().decode("utf-8", errors="ignore"), "lxml")

    tags = [t for t in soup.find_all(["p","h1","h2","h3","li"])
            if len(t.get_text(strip=True)) > 5]

    if not tags:
        STATE["done"].append(name)
        save_all()
        return

    chunks = build_chunks(tags)

    vi_count = 0
    total = 0

    for chunk in chunks:

        texts = [t[1] for t in chunk]
        joined = "\n".join(texts)

        result = translate_chunk(joined)

        # retry chunk fail
        if result is None:
            print("🔁 retry chunk...")
            result = translate_chunk(joined)

        # fallback cuối
        if result is None:
            result = "[VI?]\n" + joined

        lines = result.split("\n")

        # map chính xác
        for i, (idx, _) in enumerate(chunk):
            if i < len(lines):
                tags[idx].string = lines[i]

                if is_vietnamese(lines[i]):
                    vi_count += 1
                total += 1

    ratio = vi_count / max(total,1)
    print(f"{name} → {ratio:.0%}")

    item.set_content(str(soup).encode("utf-8"))

    STATE["done"].append(name)
    save_all()

# =====================
# MAIN
# =====================
print("📖 Loading:", FILE)

book = epub.read_epub(FILE)

items = [it for it in book.get_items()
         if it.get_type() == ITEM_DOCUMENT]

print(f"Found {len(items)} sections")

for item in tqdm(items):
    process_item(item)

OUT = FILE.replace(".epub", "_Translated.epub")
epub.write_epub(OUT, book)

print("✅ DONE:", OUT)
