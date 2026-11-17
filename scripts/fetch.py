#!/usr/bin/env python3
"""Raccoglie notizie da Bing News RSS (link diretti agli articoli) -> docs/news.json"""
import json, re, sys, html, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

KEEP_DAYS, MAX_PER_TOPIC = 14, 60
BING = "https://www.bing.com/news/search?format=rss&setlang=it&cc=IT&count=50&q="

# (id, nome, emoji, domini ufficiali, [query])
TOPICS = [
 ("cantu", "Basket Cantù", "🏀", ["pallacanestrocantu.com"],
   ['site:pallacanestrocantu.com', '"Pallacanestro Cantù"', '"Acqua S.Bernardo Cantù"']),
 ("sinner", "Sinner", "🎾", ["atptour.com", "fitp.it", "wimbledon.com", "rolandgarros.com", "usopen.org", "ausopen.com", "atpfinals.com"],
   ['site:atptour.com Sinner', 'site:fitp.it Sinner', '"Jannik Sinner"', 'Sinner tennis']),
 ("como", "Como", "⚽", ["comofootball.com"],
   ['site:comofootball.com', '"Como 1907"', 'Como Fabregas']),
 ("juve", "Juventus", "⚪⚫", ["juventus.com"],
   ['site:juventus.com', 'Juventus Serie A', 'Juventus calcio notizie']),
 ("fisco", "Fisco · 730", "🧾", ["agenziaentrate.gov.it", "fiscooggi.it", "finanze.gov.it", "mef.gov.it", "inps.it"],
   ['site:agenziaentrate.gov.it', 'site:fiscooggi.it', 'modello 730 novità', 'Irpef detrazioni novità', '730 precompilata']),
]

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; notizie-app)"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()

def norm(t): return re.sub(r"\W+", " ", t.lower()).strip()[:90]

def real_url(link):
    """Bing avvolge i link: estrae quello vero dal parametro url=."""
    p = urllib.parse.urlparse(link)
    if p.hostname and p.hostname.endswith("bing.com"):
        u = urllib.parse.parse_qs(p.query).get("url")
        if u: return u[0]
    return link

def clean(s, n=220):
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "…"

def fetch(query, official_domains):
    out = []
    root = ET.fromstring(get(BING + urllib.parse.quote(query)))
    for it in root.iter("item"):
        title = clean(it.findtext("title"), 300)
        link = real_url((it.findtext("link") or "").strip())
        if not title or not link.startswith("http"): continue
        source = ""
        for ch in it:
            if ch.tag.split("}")[-1] == "Source": source = (ch.text or "").strip()
        host = (urllib.parse.urlparse(link).hostname or "").lower()
        if not source: source = host.removeprefix("www.")
        try: dt = parsedate_to_datetime(it.findtext("pubDate")).astimezone(timezone.utc)
        except Exception: continue
        off = any(host == d or host.endswith("." + d) for d in official_domains)
        out.append({"t": title, "s": source, "u": link, "d": dt.isoformat(timespec="seconds"),
                    "o": off, "x": clean(it.findtext("description"))})
    return out

def main():
    path = "docs/news.json"
    try: old = json.load(open(path, encoding="utf-8"))
    except Exception: old = {"topics": []}
    oldmap = {t["id"]: t.get("items", []) for t in old.get("topics", [])}
    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    result = []
    for tid, name, emoji, domains, queries in TOPICS:
        items = [i for i in oldmap.get(tid, []) if "news.google.com" not in i["u"]]
        for q in queries:
            try: items += fetch(q, domains)
            except Exception as e: print(f"! {tid} [{q}]: {e}", file=sys.stderr)
        seen, uniq = {}, []
        for i in sorted(items, key=lambda x: not x["o"]):          # ufficiali per primi
            k = norm(i["t"])
            if k in seen: continue
            seen[k] = i; uniq.append(i)
        uniq = [i for i in uniq if datetime.fromisoformat(i["d"]) >= cutoff]
        uniq.sort(key=lambda x: x["d"], reverse=True)
        result.append({"id": tid, "name": name, "emoji": emoji, "items": uniq[:MAX_PER_TOPIC]})
    new = {"topics": result}
    changed = [t["items"] for t in result] != [t.get("items") for t in old.get("topics", [])]
    new["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds") if changed else old.get("updated")
    json.dump(new, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print({t["id"]: len(t["items"]) for t in result}, {t["id"]: sum(i["o"] for i in t["items"]) for t in result})

main()
