import sys, time, random, json, os, requests, re
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup

FILE = sys.argv[1]

CACHE_PATH = "cache.json"
STATE_PATH = "state.json"

CACHE = json.load(open(CACHE_PATH)) if os.path.exists(CACHE_PATH) else {}
STATE = json.load(open(STATE_PATH)) if os.path.exists(STATE_PATH) else {"done": []}

def save_all():
    json.dump(STATE, open(STATE_PATH, "w"))
    json.dump(CACHE, open(CACHE_PATH, "w"), ensure_ascii=False)

ENDPOINTS = [
    "https://translate.googleapis.com/translate_a/single",
    "https://clients5.google.com/translate_a/single",
]

def call_api(text):
    url = random.choice(ENDPOINTS)
    params = {
        "client": "gtx",
        "sl": "auto",
        "tl": "vi",
        "dt": "t",
        "q": text
    }
    r = requests.get(url, params=params, timeout=10)
    return "".join([x[0] for x in r.json()[0] if x[0]])

def translate(text):
    if text in CACHE:
        return CACHE[text]

    for i in range(3):  # retry nhẹ
        try:
            result = call_api(text)
            if result.strip() != text.strip():
                CACHE[text] = result
                time.sleep(0.5 + random.random())
                return result
        except:
            time.sleep(2)

    return text  # fail thì giữ nguyên (không treo)

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

def process_item(item):
    name = item.get_name()
    if name in STATE["done"]:
        return

    soup = BeautifulSoup(item.get_content().decode('utf-8', errors='ignore'), 'lxml')

    tags = soup.find_all(['p','h1','h2','h3','li'])
    texts = [t.get_text(strip=True) for t in tags if len(t.get_text(strip=True)) > 5]

    if not texts:
        return

    chunks = smart_chunk("\n".join(texts))

    translated = []
    for c in chunks:
        translated.append(translate(c))

    lines = "\n".join(translated).split("\n")

    i = 0
    for t in tags:
        if t.get_text(strip=True) and i < len(lines):
            t.string = lines[i]
            i += 1

    item.set_content(str(soup).encode('utf-8'))

    STATE["done"].append(name)
    save_all()

print(f"📖 Reading: {FILE}")

book = epub.read_epub(FILE)

items = [it for it in book.get_items() if it.get_type() == ITEM_DOCUMENT]

for item in items:
    process_item(item)

OUT = FILE.replace(".epub", "_TiengViet.epub")
epub.write_epub(OUT, book)

print(f"✅ DONE: {OUT}")
