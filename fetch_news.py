#!/usr/bin/env python3
"""Rail News: sirf bharosemand sources se khabrein kheench kar news.json banata hai (sirf stdlib)."""
import json, os, re, sys, time, html, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

GN = "https://news.google.com/rss/search?q={}&hl=en-IN&gl=IN&ceid=IN:en"


def gn(domain):
    return GN.format("site:%s%%20when:2d" % domain)


# Sirf yahi sources allowed hain. naam -> (allowed domains, seedhe RSS feeds, fallback feed)
# Reuters, ANI aur National Geographic ke kaam karne wale public RSS nahi hain,
# isliye unke liye Google News RSS (site filter) use hota hai.
SOURCES = {
    "BBC": (("bbc.co.uk", "bbc.com"),
            ["https://feeds.bbci.co.uk/news/world/rss.xml",
             "https://feeds.bbci.co.uk/news/rss.xml",
             "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml"], gn("bbc.com")),
    "The Hindu": (("thehindu.com",),
                  ["https://www.thehindu.com/news/national/feeder/default.rss",
                   "https://www.thehindu.com/news/international/feeder/default.rss",
                   "https://www.thehindu.com/business/feeder/default.rss"], gn("thehindu.com")),
    "Reuters": (("reuters.com",), [], gn("reuters.com")),
    "ANI": (("aninews.in",), [], gn("aninews.in")),
    "Al Jazeera": (("aljazeera.com",), ["https://www.aljazeera.com/xml/rss/all.xml"], gn("aljazeera.com")),
    "NDTV": (("ndtv.com",),
             ["https://feeds.feedburner.com/ndtvnews-top-stories",
              "https://feeds.feedburner.com/ndtvnews-latest"], gn("ndtv.com")),
    "New York Times": (("nytimes.com",),
                       ["https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
                        "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"], gn("nytimes.com")),
    "National Geographic": (("nationalgeographic.com",), [], gn("nationalgeographic.com")),
}
RETENTION_DAYS = 92  # 3 mahine: isse purani khabrein hi hatti hain
ARCHIVE = "archive"
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")
TRIES = 3
TIMEOUT = 15
HEADERS = {"User-Agent": "Mozilla/5.0 (RailNewsBot)"}
FB_NS = "{http://rssnamespace.org/feedburner/ext/1.0}origLink"


def clean(s):
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    return re.sub(r"\s+", " ", s).strip()


def norm(title):
    return re.sub(r"\W+", " ", title.lower()).strip()


def host_ok(domains, url):
    host = (urlparse(url or "").hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in domains)


def fetch(url):
    """Retry + backoff ke saath feed laata hai."""
    last = None
    for i in range(TRIES):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return ET.fromstring(r.read())
        except Exception as e:
            last = e
            if i < TRIES - 1:
                time.sleep(2 ** i)
    raise last


def parse(source, domains, root, google):
    out, now = [], datetime.now(timezone.utc)
    for it in root.iter("item"):
        title = clean(it.findtext("title"))
        link = (it.findtext(FB_NS) or it.findtext("link") or "").strip()
        if not title or not link:
            continue
        if google:
            s = it.find("source")
            if s is None or not host_ok(domains, s.get("url")):
                continue  # trusted domain ka na ho to hata do
            label = clean(s.text)
            if label and title.endswith(" - " + label):
                title = title[: -len(label) - 3]
            text = ""
        else:
            if not host_ok(domains, link):
                continue
            text = clean(it.findtext("description"))[:150]
        try:
            d = parsedate_to_datetime(it.findtext("pubDate"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
        except Exception:
            d = now
        d = d.astimezone(timezone.utc)
        if d > now + timedelta(days=1):
            d = now
        if now - d > timedelta(days=RETENTION_DAYS):
            continue
        out.append({"source": source, "title": title, "text": text, "url": link, "date": d.isoformat()})
    return out


def collect(name):
    domains, feeds, fallback = SOURCES[name]
    items, errs = [], []
    for url in feeds:
        try:
            items += parse(name, domains, fetch(url), False)
        except Exception as e:
            errs.append("%s: %s" % (url, e))
    if not items:  # seedhe feeds se kuch nahi mila to Google News fallback
        try:
            items = parse(name, domains, fetch(fallback), True)
        except Exception as e:
            errs.append("%s: %s" % (fallback, e))
    return name, items, errs


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, data):
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(path + ".tmp", path)  # atomic write


def main():
    os.makedirs(ARCHIVE, exist_ok=True)
    now = datetime.now(timezone.utc)

    # purana archive: koi khabar delete nahi hoti (sirf RETENTION_DAYS se purani files)
    days = {}
    for fn in os.listdir(ARCHIVE):
        if DAY_RE.match(fn):
            days[fn[:-5]] = read_json(os.path.join(ARCHIVE, fn), [])
    seen_u = {n["url"] for arr in days.values() for n in arr}
    seen_t = {(n["source"], norm(n["title"])) for arr in days.values() for n in arr}

    with ThreadPoolExecutor(max_workers=len(SOURCES)) as ex:  # sab sources ek saath
        results = list(ex.map(collect, SOURCES))

    status, touched, fetched_total, error_total = {}, set(), 0, 0
    for name, items, errs in results:
        new = 0
        for n in items:
            tk = (n["source"], norm(n["title"]))
            if n["url"] in seen_u or tk in seen_t:
                continue
            seen_u.add(n["url"])
            seen_t.add(tk)
            day = n["date"][:10]
            days.setdefault(day, []).append(n)
            touched.add(day)
            new += 1
        fetched_total += len(items)
        error_total += len(errs)
        status[name] = {"ok": bool(items) or not errs, "fetched": len(items), "new": new, "errors": errs[:2]}
        print("%-20s fetched %3d, new %3d%s" % (name, len(items), new,
                                               "  WARN: %d error" % len(errs) if errs else ""))

    if fetched_total == 0:  # error ho ya na ho, 0 khabar matlab kuch gadbad hai: chupke se hara mat dikhao
        print("Koi bhi source se khabar nahi mili (errors: %d), archive badla nahi gaya." % error_total, file=sys.stderr)
        sys.exit(1)

    for day in touched:
        days[day].sort(key=lambda n: n["date"], reverse=True)
        write_json(os.path.join(ARCHIVE, day + ".json"), days[day])

    cutoff = (now - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
    for day in [d for d in days if d < cutoff]:  # sirf 3 mahine se purani files
        os.remove(os.path.join(ARCHIVE, day + ".json"))
        del days[day]

    manifest_days = sorted((d for d in days if days[d]), reverse=True)
    old = read_json("news.json", {})
    if touched or old.get("days") != manifest_days:
        write_json("news.json", {"updated": now.isoformat() if touched else old.get("updated"),
                                 "retention_days": RETENTION_DAYS, "status": status, "days": manifest_days})
        print("OK: %d nayi khabrein, %d din ka archive." % (sum(s["new"] for s in status.values()), len(manifest_days)))
    else:
        print("Koi nayi khabar nahi.")


if __name__ == "__main__":
    main()
