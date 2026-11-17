#!/usr/bin/env python3
"""Raccoglie notizie da Bing News RSS (link diretti agli articoli) -> docs/news.json"""
import json, re, sys, html, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

KEEP_DAYS, MAX_PER_TOPIC = 14, 60
BLOCK = []   # siti da escludere (vuoto: nessuno)
def blocked(u): return any(d in u for d in BLOCK)
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
 ("ansa", "ANSA", "📰", ["ansa.it"], ['site:ansa.it']),
 ("corriere", "Corriere", "🗞️", ["corriere.it"],
   ['site:corriere.it ' + k for k in ["", "cronaca", "politica", "economia", "esteri", "sport", "milano", "cultura", "salute", "tecnologia", "spettacoli", "scuola", "ultime notizie"]]),
 ("cadorago", "Cadorago", "📍", [], ['Cadorago']),
 ("guanzate", "Guanzate", "📍", [], ['Guanzate']),
 ("noci", "Noci", "📍", [], ['Noci Bari', 'comune di Noci', 'Noci Puglia notizie']),
 ("info", "Informatica", "💻", [],
   ['informatica notizie', 'site:punto-informatico.it', 'site:hdblog.it', 'cybersecurity Italia', 'intelligenza artificiale novità', 'IBM i AS/400 novità']),
 ("fisco", "Fisco · 730", "🧾", ["agenziaentrate.gov.it", "fiscooggi.it", "finanze.gov.it", "mef.gov.it", "inps.it"],
   ['site:agenziaentrate.gov.it', 'site:fiscooggi.it', 'modello 730 novità', 'Irpef detrazioni novità', '730 precompilata']),
]

# feed RSS diretti (link diretti agli articoli); se falliscono resta la ricerca Bing
FEEDS = {
 "ansa": ["https://www.ansa.it/sito/ansait_rss.xml",
          "https://www.ansa.it/sito/notizie/cronaca/cronaca_rss.xml",
          "https://www.ansa.it/sito/notizie/politica/politica_rss.xml",
          "https://www.ansa.it/sito/notizie/economia/economia_rss.xml",
          "https://www.ansa.it/sito/notizie/mondo/mondo_rss.xml",
          "https://www.ansa.it/sito/notizie/sport/sport_rss.xml",
          "https://www.ansa.it/lombardia/notizie/lombardia_rss.xml"],
 "info": ["https://www.punto-informatico.it/feed/", "https://www.hdblog.it/feed/", "https://www.wired.it/feed/rss"],
 "corriere": ["https://xml2.corriereobjects.it/rss/homepage.xml", "https://www.corriere.it/rss/homepage.xml", "https://www.corriere.it/rss/cronache.xml", "https://www.corriere.it/rss/politica.xml", "https://www.corriere.it/rss/economia.xml", "https://www.corriere.it/rss/sport.xml"],
}
REQUIRE = {"noci": r"\bnoci\b", "cadorago": r"cadorago", "guanzate": r"guanzate"}
MAXN = {"ansa": 250, "corriere": 200, "info": 100}

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

IT = set("il lo la i gli le un una di del della dei delle da in con su per tra fra e è che non si al alla ai nel nella sul sulla come ma più dopo sono ha hanno questo questa".split())
EN = set("the of and to in for on with at by from is are was were be has have will this that after over about as it its an his her their new says".split())
OTHER = set("yang dan di untuk dengan pada dari ini itu adalah el los las del por para con una que su sus der die das und ist nicht mit le les des une pour dans est sur".split())
def foreign(text):
    w = re.findall(r"[a-zàèéìòù']+", text.lower())
    it = sum(x in IT for x in w); xx = sum(x in EN or x in OTHER for x in w)
    return xx >= 2 and xx > it

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
        if blocked(link): continue
        lang_en = (not off) and foreign(title + " " + clean(it.findtext("description"), 400))
        out.append({"t": title, "s": source, "u": link, "d": dt.isoformat(timespec="seconds"),
                    "o": off, "x": clean(it.findtext("description")), "l": lang_en})
    return out

def fetch_feed(url, domains, label):
    out = []
    root = ET.fromstring(get(url))
    for it in root.iter("item"):
        title = clean(it.findtext("title"), 300)
        link = (it.findtext("link") or "").strip()
        if not title or not link.startswith("http"): continue
        try: dt = parsedate_to_datetime(it.findtext("pubDate")).astimezone(timezone.utc)
        except Exception: continue
        out.append({"t": title, "s": label, "u": link, "d": dt.isoformat(timespec="seconds"),
                    "o": True, "x": clean(it.findtext("description")), "l": False})
    return out

def main():
    path = "docs/news.json"
    try: old = json.load(open(path, encoding="utf-8"))
    except Exception: old = {"topics": []}
    oldmap = {t["id"]: t.get("items", []) for t in old.get("topics", [])}
    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    result = []
    for tid, name, emoji, domains, queries in TOPICS:
        items = [i for i in oldmap.get(tid, []) if not blocked(i["u"]) and "news.google.com" not in i["u"] ]
        for fu in FEEDS.get(tid, []):
            try: items += fetch_feed(fu, domains, name)
            except Exception as e: print(f"! {tid} feed: {e}", file=sys.stderr)
        for q in queries:
            try: items += fetch(q, domains)
            except Exception as e: print(f"! {tid} [{q}]: {e}", file=sys.stderr)
        seen, uniq = {}, []
        for i in sorted(items, key=lambda x: not x["o"]):          # ufficiali per primi
            k = norm(i["t"])
            if k in seen: continue
            seen[k] = i; uniq.append(i)
        if tid in REQUIRE:
            uniq = [i for i in uniq if re.search(REQUIRE[tid], i["t"] + " " + i.get("x", ""), re.I)]
        uniq = [i for i in uniq if datetime.fromisoformat(i["d"]) >= cutoff]
        uniq.sort(key=lambda x: x["d"], reverse=True)
        result.append({"id": tid, "name": name, "emoji": emoji, "items": uniq[:MAXN.get(tid, MAX_PER_TOPIC)]})
    new = {"topics": result}
    changed = [t["items"] for t in result] != [t.get("items") for t in old.get("topics", [])]
    new["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds") if changed else old.get("updated")
    json.dump(new, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print({t["id"]: len(t["items"]) for t in result}, {t["id"]: sum(i["o"] for i in t["items"]) for t in result})

main()
