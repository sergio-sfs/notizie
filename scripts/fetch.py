#!/usr/bin/env python3
"""Raccoglie notizie da Google News RSS (solo titolo/fonte/data/link) -> docs/news.json"""
import json, re, sys, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

KEEP_DAYS, MAX_PER_TOPIC = 14, 60
GN = "https://news.google.com/rss/search?hl=it&gl=IT&ceid=IT:it&q="

# (id, nome, emoji, [(query, ufficiale)])  -- le fonti ufficiali hanno priorita'
TOPICS = [
 ("cantu", "Basket Cantù", "🏀", [
   ('site:pallacanestrocantu.com when:14d', True),
   ('"Pallacanestro Cantù" OR "Acqua S.Bernardo Cantù" when:7d', False)]),
 ("sinner", "Sinner", "🎾", [
   ('Jannik Sinner site:atptour.com OR site:fitp.it OR site:ubitennis.com when:14d', True),
   ('"Jannik Sinner" when:7d', False)]),
 ("como", "Como", "⚽", [
   ('site:comofootball.com when:14d', True),
   ('"Como 1907" OR "Como Fabregas" OR "Como calcio" when:7d', False)]),
 ("juve", "Juventus", "⚪⚫", [
   ('site:juventus.com when:14d', True),
   ('Juventus Serie A when:3d', False)]),
 ("fisco", "Fisco · 730", "🧾", [
   ('site:agenziaentrate.gov.it OR site:fiscooggi.it OR site:finanze.gov.it when:30d', True),
   ('(730 OR Irpef OR detrazioni OR precompilata) novità fisco when:7d', False)]),
]

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (notizie-app)"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()

def norm(t): return re.sub(r"\W+", " ", t.lower()).strip()[:90]

def fetch(query, official):
    out = []
    root = ET.fromstring(get(GN + urllib.parse.quote(query)))
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        src = it.find("source")
        source = (src.text if src is not None else "") or ""
        if source and title.endswith(" - " + source): title = title[: -len(source) - 3]
        try: dt = parsedate_to_datetime(it.findtext("pubDate")).astimezone(timezone.utc)
        except Exception: continue
        out.append({"t": title, "s": source, "u": it.findtext("link"),
                    "d": dt.isoformat(timespec="seconds"), "o": official})
    return out

def main():
    path = "docs/news.json"
    try: old = json.load(open(path, encoding="utf-8"))
    except Exception: old = {"topics": []}
    oldmap = {t["id"]: t.get("items", []) for t in old.get("topics", [])}
    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    result = []
    for tid, name, emoji, queries in TOPICS:
        items = list(oldmap.get(tid, []))
        for q, off in queries:
            try: items += fetch(q, off)
            except Exception as e: print(f"! {tid}: {e}", file=sys.stderr)
        seen, uniq = {}, []
        for i in sorted(items, key=lambda x: (not x["o"], x["d"]), reverse=False):
            k = norm(i["t"])
            if k in seen:                       # tieni la versione ufficiale
                if i["o"] and not seen[k]["o"]: seen[k].update(i)
                continue
            seen[k] = i; uniq.append(i)
        uniq = [i for i in uniq if datetime.fromisoformat(i["d"]) >= cutoff]
        uniq.sort(key=lambda x: x["d"], reverse=True)
        result.append({"id": tid, "name": name, "emoji": emoji, "items": uniq[:MAX_PER_TOPIC]})
    new = {"topics": result}
    if [t["items"] for t in new["topics"]] != [t.get("items") for t in old.get("topics", [])]:
        new["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    else:
        new["updated"] = old.get("updated")
    json.dump(new, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print({t["id"]: len(t["items"]) for t in result})

main()
