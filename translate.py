import sys, time, random, json, os, requests, re
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup

FILE = sys.argv[1]

CACHE_PATH = "cache.json"
CACHE = json.load(open(CACHE_PATH)) if os.path.exists(CACHE_PATH) else {}

def save_cache():
    json.dump(CACHE, open(CACHE_PATH, "w"), ensure_ascii=False)

ENDPOINTS = [
    "https://translate.googleapis.com/translate_a/single",
    "https://clients5.google.com/translate_a/single",
]

def call_api(text):
    url = random.choice(ENDPOINTS)
    params = {"client":"gtx","sl":"auto","tl":"vi","dt":"t","q": text}
    r = requests.get(url, params=params, timeout=10)
    return "".join([x[0] for x in r.json()[0] if x[0]])

def translate(text):
    if text in CACHE:
        return CACHE[text]

    for _ in range(3):
        try:
            out = call_api(text)
            if out.strip() != text.strip():
                CACHE[text] = out
                time.sleep(0.6 + random.random())
                return out
        except:
            time.sleep(2)

    return text  # fail nhanh, không treo

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
    soup = BeautifulSoup(item.get_content().decode('utf-8', errors='ignore'), 'lxml')

    tags = soup.find_all(['p','h1','h2','h3','li'])
    texts = [t.get_text(strip=True) for t in tags if len(t.get_text(strip=True)) > 5]

    if not texts:
        return

    chunks = smart_chunk("\n".join(texts))

    translated = [translate(c) for c in chunks]
    lines = "\n".join(translated).split("\n")

    i = 0
    for t in tags:
        if t.get_text(strip=True) and i < len(lines):
            t.string = lines[i]
            i += 1

    item.set_content(str(soup).encode('utf-8'))

print(f"📖 Reading: {FILE}")

book = epub.read_epub(FILE)
items = [it for it in book.get_items() if it.get_type() == ITEM_DOCUMENT]

for item in items:
    process_item(item)

# 🔥 auto output name
base = os.path.splitext(FILE)[0]
OUT = base + "_Translated.epub"

epub.write_epub(OUT, book)
save_cache()

print(f"✅ DONE: {OUT}")
