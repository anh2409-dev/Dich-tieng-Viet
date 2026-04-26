import sys
import time
import random
import json
import os
import zipfile
import shutil
import tempfile
import requests
import ebooklib
import warnings

from ebooklib import epub
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from tqdm import tqdm

warnings.filterwarnings(“ignore”, category=XMLParsedAsHTMLWarning)

FILE       = sys.argv[1]
CACHE_PATH = “cache.json”
STATE_PATH = “state.json”

CACHE = json.load(open(CACHE_PATH)) if os.path.exists(CACHE_PATH) else {}
STATE = json.load(open(STATE_PATH)) if os.path.exists(STATE_PATH) else {“done”: []}

def save_state():
json.dump(STATE, open(STATE_PATH, “w”))
json.dump(CACHE, open(CACHE_PATH, “w”), ensure_ascii=False)

ENDPOINTS = [
“https://translate.googleapis.com/translate_a/single”,
“https://clients5.google.com/translate_a/single”,
“https://clients6.google.com/translate_a/single”,
]

USER_AGENTS = [
“Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36”,
“Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/123.0 Safari/537.36”,
“Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1”,
]

fail_streak = 0
total_ok    = 0
total_fail  = 0

VI_CHARS = set(“àáâãèéêìíòóôõùúýăđơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỷỹỵ”
“ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝĂĐƠƯẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼẾỀỂỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪỬỮỰỲỶỸỴ”)

def is_vietnamese(text):
return any(c in VI_CHARS for c in text)

def call_google(text):
params  = {“client”: “gtx”, “sl”: “auto”, “tl”: “vi”, “dt”: “t”, “q”: text}
headers = {
“User-Agent”: random.choice(USER_AGENTS),
“Referer”: “https://translate.google.com/”,
}
r = requests.get(random.choice(ENDPOINTS), params=params, headers=headers, timeout=12)
r.raise_for_status()
return “”.join([x[0] for x in r.json()[0] if x[0]])

def translate(text):
global fail_streak, total_ok, total_fail
t = text.strip()
if not t or len(t) < 2:
return text
if t in CACHE:
return CACHE[t]
if fail_streak >= 3:
wait = 30 + random.randint(15, 45)
print(“Cooldown {}s…”.format(wait), flush=True)
time.sleep(wait)
fail_streak = 0
for attempt in range(6):
try:
result = call_google(t)
if not result or result.strip() == t.strip():
raise Exception(“blocked”)
CACHE[t]    = result
fail_streak = 0
total_ok   += 1
time.sleep(0.4 + random.random() * 0.8)
return result
except Exception:
time.sleep(2 + attempt * 3 + random.random() * 2)
fail_streak += 1
total_fail  += 1
return text

SKIP = [“nav”, “toc”, “cover”, “copyright”, “acknowledgment”, “about”,
“author”, “index”, “biblio”, “dedication”, “colophon”, “halftitle”]

def should_skip(name):
return any(k in name.lower() for k in SKIP)

def process_item(item):
name = item.get_name()
if name in STATE[“done”]:
return
soup = BeautifulSoup(item.get_content().decode(“utf-8”, errors=“ignore”), “lxml”)
tags = [t for t in soup.find_all([“p”, “h1”, “h2”, “h3”, “h4”, “li”, “blockquote”])
if len(t.get_text(strip=True)) > 5]
if not tags:
STATE[“done”].append(name)
save_state()
return
vi_count = 0
for tag in tags:
result = translate(tag.get_text(strip=True))
tag.string = result
if is_vietnamese(result):
vi_count += 1
ratio = vi_count / len(tags)
status = “OK” if ratio >= 0.5 else “WARN”
print(”[{}] {}: {}/{} ({:.0f}%)”.format(status, name.split(”/”)[-1], vi_count, len(tags), ratio * 100), flush=True)
item.set_content(str(soup).encode(“utf-8”))
STATE[“done”].append(name)
save_state()

print(“File: {}”.format(FILE))
book  = epub.read_epub(FILE)
items = [it for it in book.get_items()
if it.get_type() == ebooklib.ITEM_DOCUMENT
and not should_skip(it.get_name())]
print(“Found {} files, done: {}”.format(len(items), len(STATE[“done”])))

for item in tqdm(items, desc=“Translating”):
process_item(item)

print(“OK: {} | Fail: {}”.format(total_ok, total_fail))

print(“Packaging…”)
tmp = tempfile.mkdtemp()
with zipfile.ZipFile(FILE, “r”) as z:
z.extractall(tmp)
for item in book.get_items():
path = os.path.join(tmp, item.get_name())
if os.path.exists(path):
open(path, “wb”).write(item.get_content())

out = FILE.replace(”.epub”, “_TiengViet.epub”)
with zipfile.ZipFile(out, “w”, zipfile.ZIP_DEFLATED) as zout:
mimetype = os.path.join(tmp, “mimetype”)
if os.path.exists(mimetype):
zout.write(mimetype, “mimetype”, compress_type=zipfile.ZIP_STORED)
for root, _, fnames in os.walk(tmp):
for fn in fnames:
if fn == “mimetype”:
continue
full = os.path.join(root, fn)
zout.write(full, os.path.relpath(full, tmp))
shutil.rmtree(tmp)
print(“Done: {}”.format(out))
