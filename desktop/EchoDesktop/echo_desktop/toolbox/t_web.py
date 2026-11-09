"""Live information from the internet. Every request goes through internet.py's guard (public addresses only, size and
time limits) and every answer is data for the AI, never instructions."""
from __future__ import annotations

import math
import re
import urllib.parse
from typing import Literal

from . import ToolError, fmt, tool

C = "web"


def I(op: str, **slots) -> str:
    from .. import internet
    return internet.info(op, {k: str(v) for k, v in slots.items() if v not in (None, "")}).text


def J(url: str, cache: int = 300, headers: dict = None):
    from .. import internet
    return internet.get_json(url, cache, headers)


def Q(s: str) -> str:
    return urllib.parse.quote(str(s).strip(), safe="")


def W(**kw):
    return tool(C, net=True, **kw)


# ---- weather & places
@W(ex={"city": "Vijayawada"}, keys="weather now current temperature outside")
def weather_now(city: str = "") -> str:
    """Current weather in a city (or where you are)."""
    return I("WEATHER_NOW", city=city)


@W(ex={"city": "Hyderabad", "day": "tomorrow"}, keys="forecast today tomorrow rain chance high low")
def weather_forecast(city: str = "", day: Literal["today", "tomorrow", "week", "weekend"] = "today") -> str:
    """Forecast for today, tomorrow, the week or the weekend."""
    return I({"today": "TODAY", "tomorrow": "TOMORROW", "week": "WEEK", "weekend": "WEEKEND"}[day], city=city)


@W(ex={"city": "Chennai"}, keys="hourly weather next hours")
def weather_hourly(city: str = "") -> str:
    """Weather for the next few hours."""
    return I("HOURLY", city=city)


@W(ex={"city": "Mumbai", "question": "umbrella"}, keys="umbrella jacket walk outside advice should i")
def weather_advice(question: Literal["umbrella", "jacket", "walk", "rain", "snow", "tonight", "hot_or_cold"], city: str = "") -> str:
    """Practical weather answers: do I need an umbrella or jacket, good for a walk, rain or snow coming, tonight's low."""
    return I({"umbrella": "UMBRELLA", "jacket": "JACKET", "walk": "WALK", "rain": "RAIN", "snow": "SNOW", "tonight": "TONIGHT", "hot_or_cold": "HOT_COLD"}[question], city=city)


@W(ex={"city": "Delhi", "what": "wind"}, keys="humidity wind uv feels like")
def weather_detail(what: Literal["humidity", "wind", "uv", "feels_like"], city: str = "") -> str:
    """Humidity, wind, UV index or feels-like temperature."""
    return I({"humidity": "HUMIDITY", "wind": "WIND", "uv": "UV", "feels_like": "FEELS"}[what], city=city)


@W(ex={"city": "Delhi"}, keys="air quality aqi pollution pm2.5 smog")
def air_quality(city: str = "") -> str:
    """Air quality (US AQI, PM2.5, PM10)."""
    return I("AQI", city=city)


@W(ex={"city": "Tokyo"}, keys="sunrise sunset daylight")
def sun_times(city: str = "") -> str:
    """Sunrise and sunset today."""
    return I("SUN", city=city)


@W(ex={"place": "Amaravati"}, keys="coordinates latitude longitude location geocode where is")
def find_place(place: str) -> str:
    """Latitude, longitude, country and time zone of a place."""
    d = J("https://geocoding-api.open-meteo.com/v1/search?count=3&language=en&format=json&name=" + Q(place.split(",")[0]), 86400)
    res = d.get("results") or []
    if not res:
        raise ToolError(f"I couldn't find {place}")
    return "\n".join(f"{r['name']}, {r.get('admin1', '')}, {r.get('country', '')}: {r['latitude']:.4f}, {r['longitude']:.4f} "
                     f"({r.get('timezone', '')}, population {r.get('population', 'n/a')})" for r in res)


def _coords(place):
    from .. import internet
    p = internet.geocode(place)
    return p.lat, p.lon, p.name


@W(ex={"place_a": "Hyderabad", "place_b": "Vijayawada"}, keys="distance between cities km how far")
def distance_between(place_a: str, place_b: str) -> str:
    """Straight-line distance between two places (roads are usually 20–40% longer)."""
    la, oa, na = _coords(place_a)
    lb, ob, nb = _coords(place_b)
    p1, p2 = math.radians(la), math.radians(lb)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(ob - oa) / 2) ** 2
    km = 6371 * 2 * math.asin(math.sqrt(a))
    return f"{na} to {nb}: {fmt(round(km))} km ({fmt(round(km * 0.621371))} miles) in a straight line."


@W(ex={"place": "Shimla"}, keys="elevation altitude height above sea level")
def elevation(place: str) -> str:
    """Height above sea level of a place."""
    lat, lon, name = _coords(place)
    d = J(f"https://api.open-meteo.com/v1/elevation?latitude={lat}&longitude={lon}", 86400)
    return f"{name} is about {fmt(round(d['elevation'][0]))} m above sea level."


@W(ex={"lat": 16.5062, "lon": 80.648}, keys="reverse geocode address from coordinates")
def address_from_coordinates(lat: float, lon: float) -> str:
    """Place name for coordinates (OpenStreetMap)."""
    d = J(f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=14&lat={lat}&lon={lon}", 86400)
    return d.get("display_name") or "No address found."


# ---- knowledge
@W(ex={"topic": "Alan Turing"}, keys="wikipedia who is what is summary encyclopedia")
def wikipedia_summary(topic: str) -> str:
    """Short Wikipedia summary of a person, place or thing."""
    return I("WIKI", q=topic)


@W(ex={"query": "Indian space missions", "limit": 5}, keys="wikipedia search articles")
def wikipedia_search(query: str, limit: int = 8) -> list:
    """Wikipedia article titles matching a search."""
    d = J(f"https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit={max(1, min(limit, 20))}&srsearch={Q(query)}", 3600)
    return [h["title"] for h in d.get("query", {}).get("search", [])]


@W(ex={}, keys="random wikipedia article learn something")
def wikipedia_random() -> str:
    """A random Wikipedia article summary."""
    return I("WIKI_RANDOM")


@W(ex={}, keys="on this day history today events")
def on_this_day() -> str:
    """What happened on this day in history."""
    return I("ON_THIS_DAY")


@W(ex={}, keys="wikipedia featured article today")
def wikipedia_featured() -> str:
    """Today's featured Wikipedia article."""
    from datetime import date
    t = date.today()
    d = J(f"https://en.wikipedia.org/api/rest_v1/feed/featured/{t.year}/{t.month:02d}/{t.day:02d}", 3600)
    tfa = d.get("tfa") or {}
    from ..internet import first_sentences
    return f"{tfa.get('normalizedtitle', 'No featured article')}: {first_sentences(tfa.get('extract', ''), 2)}"


@W(ex={"word": "serendipity"}, keys="define dictionary meaning definition")
def define_word(word: str) -> str:
    """Dictionary definition of an English word."""
    return I("DEFINE", word=word)


@W(ex={"word": "happy", "relation": "synonyms"}, keys="synonyms antonyms rhymes similar words thesaurus")
def related_words(word: str, relation: Literal["synonyms", "antonyms", "rhymes", "sounds_like", "means_like", "describing", "starts_with"] = "synonyms") -> str:
    """Synonyms, opposites, rhymes, sound-alikes, words for a meaning, describing words, or words starting with letters."""
    op = {"synonyms": "SYNONYMS", "antonyms": "ANTONYMS", "rhymes": "RHYMES", "sounds_like": "SOUNDS_LIKE", "means_like": "MEANS_LIKE",
          "describing": "ADJECTIVES", "starts_with": "STARTS_WITH"}[relation]
    return I(op, word=word, q=word)


@W(ex={"text": "good morning", "language": "hindi"}, keys="translate language translation")
def translate(text: str, language: str) -> str:
    """Translate English text into another language (Hindi, Telugu, Tamil, Spanish…)."""
    return I("TRANSLATE", q=text, lang=language)


@W(ex={"term": "yeet"}, keys="slang urban dictionary meaning")
def slang_meaning(term: str) -> str:
    """What a slang term means (Urban Dictionary; may be crude)."""
    d = J("https://api.urbandictionary.com/v0/define?term=" + Q(term), 86400)
    items = sorted(d.get("list") or [], key=lambda x: -(x.get("thumbs_up", 0) - x.get("thumbs_down", 0)))
    if not items:
        raise ToolError(f"no slang definition for {term}")
    return re.sub(r"[\[\]]", "", items[0]["definition"])[:500]


# ---- news & social
@W(ex={"topic": "technology"}, keys="news headlines latest today")
def news_headlines(topic: Literal["top", "world", "india", "business", "technology", "sports", "science", "health", "entertainment"] = "top") -> str:
    """Latest headlines (top stories or a topic)."""
    return I("NEWS") if topic == "top" else I("NEWS_TOPIC", topic=topic)


@W(ex={"query": "ISRO"}, keys="news about search topic")
def news_search(query: str) -> str:
    """Latest headlines about something."""
    return I("NEWS_ABOUT", q=query)


@W(ex={"url": "https://feeds.bbci.co.uk/news/rss.xml", "count": 5}, keys="rss feed atom read blog podcast")
def read_rss_feed(url: str, count: int = 10) -> list:
    """Latest items from any RSS/Atom feed."""
    from .. import internet
    items = internet.parse_rss_items(internet.request(url, cache_seconds=300).text(), max(1, min(count, 50)))
    return [f"{t} — {l}" for t, l, _ in items] or ["That feed has no items (or isn't a feed)."]


@W(ex={"feed": "top"}, keys="hacker news hn stories tech")
def hacker_news(feed: Literal["top", "new", "best", "ask", "show"] = "top") -> str:
    """Hacker News stories."""
    return I("HN_" + feed.upper())


@W(ex={"query": "rust async"}, keys="hacker news search discussions")
def hacker_news_search(query: str) -> list:
    """Search Hacker News stories."""
    d = J("https://hn.algolia.com/api/v1/search?tags=story&hitsPerPage=8&query=" + Q(query), 600)
    return [f"{h.get('title')} ({h.get('points', 0)} points) — https://news.ycombinator.com/item?id={h.get('objectID')}" for h in d.get("hits", [])]


@W(ex={"count": 5}, keys="lobsters tech links programming community hottest")
def lobsters_hot(count: int = 10) -> list:
    """Hottest stories on Lobsters (a programming link community)."""
    d = J("https://lobste.rs/hottest.json", 600)
    return [f"{s['title']} ({s.get('score', 0)} points, {', '.join(s.get('tags', []))})" for s in d[:max(1, min(count, 25))]]


@W(ex={"tag": "python", "count": 5}, keys="dev.to articles blog developers")
def dev_articles(tag: str = "", count: int = 8) -> list:
    """Popular DEV Community articles (optionally by tag)."""
    d = J(f"https://dev.to/api/articles?per_page={max(1, min(count, 30))}&top=7" + (f"&tag={Q(tag)}" if tag else ""), 600)
    return [f"{a['title']} — {a['url']}" for a in d]


# ---- money & markets
@W(ex={"code": "INR"}, keys="currency information country")
def currency_info(code: str) -> str:
    """Today's value of a currency against major ones."""
    d = J(f"https://open.er-api.com/v6/latest/{code.upper()}", 1800)
    r = d.get("rates") or {}
    return f"1 {code.upper()} = " + ", ".join(f"{r[c]:.4g} {c}" for c in ("USD", "EUR", "GBP", "INR", "AED", "JPY") if c in r and c != code.upper())


# ---- developer data
REGISTRIES = {"npm": "NPM", "pypi": "PYPI", "crates": "CRATES", "nuget": "NUGET", "rubygems": "GEMS", "pub": "PUB", "homebrew": "BREW", "maven": "MAVEN"}


@W(ex={"name": "requests", "registry": "pypi"}, keys="package version latest library npm pypi crates nuget")
def package_version(name: str, registry: Literal["npm", "pypi", "crates", "nuget", "rubygems", "pub", "homebrew", "maven"]) -> str:
    """Latest version (and summary) of a package on npm, PyPI, crates.io, NuGet, RubyGems, pub.dev, Homebrew or Maven."""
    return I(REGISTRIES[registry], q=name)


@W(ex={"query": "date picker react", "count": 5}, keys="npm search packages library find")
def npm_search(query: str, count: int = 8) -> list:
    """Search npm for packages."""
    d = J(f"https://registry.npmjs.org/-/v1/search?size={max(1, min(count, 25))}&text=" + Q(query), 600)
    return [f"{o['package']['name']} {o['package'].get('version', '')} — {o['package'].get('description', '')[:100]}" for o in d.get("objects", [])]


@W(ex={"name": "react"}, keys="npm package details dependencies license downloads")
def npm_package_details(name: str) -> dict:
    """npm package details: version, license, dependencies, homepage, weekly downloads."""
    d = J(f"https://registry.npmjs.org/{name.strip().lower()}/latest", 600)
    try:
        dl = J(f"https://api.npmjs.org/downloads/point/last-week/{name.strip().lower()}", 3600).get("downloads")
    except Exception:
        dl = None
    return {"name": d.get("name"), "version": d.get("version"), "license": d.get("license"), "description": d.get("description"),
            "dependencies": list((d.get("dependencies") or {}).keys())[:40], "homepage": d.get("homepage"), "weekly_downloads": dl}


@W(ex={"name": "fastapi"}, keys="pypi package details requires python license")
def pypi_package_details(name: str) -> dict:
    """PyPI package details: version, Python needed, license, dependencies, links."""
    i = J(f"https://pypi.org/pypi/{name.strip()}/json", 600).get("info", {})
    return {"name": i.get("name"), "version": i.get("version"), "summary": i.get("summary"), "requires_python": i.get("requires_python"),
            "license": (i.get("license") or "")[:80] or i.get("license_expression"), "dependencies": (i.get("requires_dist") or [])[:40],
            "links": i.get("project_urls")}


@W(ex={"name": "python"}, keys="docker image tags versions")
def docker_image_tags(name: str) -> str:
    """Latest tags of an official Docker image."""
    return I("DOCKER", q=name)


@W(ex={"repo": "microsoft/vscode"}, keys="github repository stars forks info")
def github_repo(repo: str) -> str:
    """GitHub repository stats (stars, forks, issues, language, last push). 'owner/name' or a search term."""
    return I("GH_REPO", q=repo)


@W(ex={"repo": "python/cpython"}, keys="github latest release version tag")
def github_latest_release(repo: str) -> str:
    """Latest release of a GitHub repository."""
    return I("GH_RELEASE", q=repo)


@W(ex={"user": "torvalds"}, keys="github user profile developer")
def github_user(user: str) -> str:
    """A GitHub user's profile."""
    return I("GH_USER", q=user)


@W(ex={"query": "mcp server python", "count": 5}, keys="github search repositories projects find")
def github_search(query: str, count: int = 8, language: str = "") -> list:
    """Search GitHub repositories (most stars first)."""
    q = query + (f" language:{language}" if language else "")
    d = J(f"https://api.github.com/search/repositories?sort=stars&per_page={max(1, min(count, 20))}&q=" + Q(q), 600)
    return [f"{r['full_name']} ★{r['stargazers_count']:,} — {(r.get('description') or '')[:100]}" for r in d.get("items", [])]


@W(ex={"repo": "psf/requests", "count": 5}, keys="github issues bugs open")
def github_issues(repo: str, state: Literal["open", "closed", "all"] = "open", count: int = 10) -> list:
    """Recent issues of a GitHub repository."""
    if "/" not in repo:
        raise ToolError("use owner/name, like psf/requests")
    d = J(f"https://api.github.com/repos/{repo.strip()}/issues?state={state}&per_page={max(1, min(count, 30))}", 300)
    return [f"#{i['number']} {i['title']}{' (PR)' if 'pull_request' in i else ''}" for i in d]


@W(ex={"repo": "psf/requests"}, keys="github readme project description docs")
def github_readme(repo: str, max_chars: int = 4000) -> str:
    """A GitHub repository's README text."""
    from .. import internet
    d = J(f"https://api.github.com/repos/{repo.strip()}/readme", 600)
    import base64
    return base64.b64decode(d.get("content", "")).decode("utf-8", errors="replace")[:max_chars]


@W(keys="github file source code read raw")
def github_file(repo: str, path: str, branch: str = "") -> str:
    """Read a file from a public GitHub repository."""
    import base64
    d = J(f"https://api.github.com/repos/{repo.strip()}/contents/{path.strip('/')}" + (f"?ref={Q(branch)}" if branch else ""), 600)
    if isinstance(d, list):
        return "That's a folder: " + ", ".join(x["name"] for x in d)
    return base64.b64decode(d.get("content", "")).decode("utf-8", errors="replace")[:20000]


@W(ex={"query": "python list comprehension", "count": 5}, keys="stack overflow questions answers programming help")
def stackoverflow_search(query: str, count: int = 6) -> list:
    """Top Stack Overflow questions for a problem."""
    d = J(f"https://api.stackexchange.com/2.3/search/advanced?order=desc&sort=relevance&site=stackoverflow&pagesize={max(1, min(count, 20))}&q=" + Q(query), 600)
    import html
    return [f"{html.unescape(i['title'])} ({i.get('score', 0)} votes{', answered' if i.get('is_answered') else ''}) — {i['link']}" for i in d.get("items", [])]


@W(ex={"service": "github"}, keys="is it down status outage service")
def service_status(service: str) -> str:
    """Official status of a service (GitHub, OpenAI, Anthropic, Discord, Cloudflare, npm, PyPI, Zoom, Notion… 57 services)."""
    from ..internet import STATUS_PAGES
    s = service.strip().lower()
    if s not in STATUS_PAGES:
        raise ToolError("services I can check: " + ", ".join(sorted(STATUS_PAGES)))
    return I("STATUS", svc=s)


@W(ex={"site": "python.org"}, keys="website down up working check online")
def website_status(site: str) -> str:
    """Is a website up? Status code and response time."""
    return I("SITE_UP", q=site)


@W(ex={"url": "https://example.com"}, keys="http headers server response")
def http_headers(url: str) -> str:
    """Notable HTTP response headers of a site."""
    return I("HEADERS", q=url)


@W(ex={"site": "google.com"}, keys="ssl tls certificate expiry https")
def ssl_certificate(site: str) -> str:
    """When a site's HTTPS certificate expires and who issued it."""
    return I("SSL_EXPIRY", q=site)


@W(ex={"host": "wikipedia.org"}, keys="dns lookup resolve ip address domain")
def dns_lookup(host: str) -> str:
    """IP addresses a domain name resolves to."""
    return I("DNS", q=host)


@W(ex={}, keys="my public ip address external")
def my_public_ip() -> str:
    """This connection's public IP address."""
    return I("MY_IP")


@W(ex={"ip": "8.8.8.8"}, keys="ip address location owner lookup")
def ip_lookup(ip: str) -> str:
    """Where an IP address is and who runs it."""
    return I("IP_INFO", q=ip)


@W(ex={"domain": "example.com"}, keys="domain whois registered expiry available")
def domain_info(domain: str) -> str:
    """Whether a domain is registered, since when, and when it expires."""
    return I("DOMAIN", q=domain)


@W(ex={"url": "http://github.com"}, keys="expand short link redirect where does it go")
def expand_link(url: str) -> str:
    """Where a (short) link really goes."""
    return I("EXPAND_URL", q=url)


@W(keys="shorten link url short")
def shorten_link(url: str) -> str:
    """Make a short link (is.gd)."""
    return I("SHORTEN", q=url)


@W(ex={"url": "https://www.python.org"}, keys="page title description meta open graph preview")
def page_metadata(url: str) -> dict:
    """A web page's title, description, preview image and language."""
    from .. import internet
    r = internet.request(url, max_bytes=600_000)
    h = r.text()

    def meta(*names):
        for n in names:
            m = re.search(rf'<meta[^>]+(?:name|property)=["\']{re.escape(n)}["\'][^>]+content=["\']([^"\']*)', h, re.I) or \
                re.search(rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:name|property)=["\']{re.escape(n)}["\']', h, re.I)
            if m:
                return m.group(1)
        return None
    title = re.search(r"<title[^>]*>(.*?)</title>", h, re.S | re.I)
    lang = re.search(r"<html[^>]+lang=[\"']([^\"']+)", h, re.I)
    import html as _h
    return {"url": r.url, "title": _h.unescape(title.group(1).strip()) if title else None, "description": meta("description", "og:description"),
            "image": meta("og:image"), "site_name": meta("og:site_name"), "language": lang.group(1) if lang else None}


@W(ex={"url": "https://www.python.org"}, keys="page links list urls on page")
def page_links(url: str, filter_text: str = "") -> list:
    """Links on a web page (optionally only those whose text or URL contains some words)."""
    from .. import internet
    links = internet.read_page(url, 1000, want_links=True)["links"]
    f = filter_text.lower()
    return [f"{t}: {u}" for t, u in links if not f or f in t.lower() or f in u.lower()][:80]


@W(ex={"url": "https://docs.python.org/3/"}, keys="page headings outline structure sections")
def page_headings(url: str) -> list:
    """The headings (outline) of a web page."""
    from .. import internet
    r = internet.request(url, max_bytes=1_500_000)
    import html as _h
    return [f"{'  ' * (int(l) - 1)}{_h.unescape(re.sub(r'<[^>]+>', '', t)).strip()}" for l, t in re.findall(r"<h([1-4])[^>]*>(.*?)</h\1>", r.text(), re.S | re.I) if t.strip()][:80]


@W(ex={"url": "python.org"}, keys="archive wayback machine old version snapshot")
def wayback_snapshot(url: str) -> str:
    """The closest saved copy of a page on the Internet Archive's Wayback Machine."""
    d = J("https://archive.org/wayback/available?url=" + Q(url), 3600)
    s = (d.get("archived_snapshots") or {}).get("closest")
    return f"Saved copy from {s['timestamp'][:4]}-{s['timestamp'][4:6]}-{s['timestamp'][6:8]}: {s['url']}" if s else "No saved copy."


@W(ex={"site": "github.com"}, keys="robots txt crawling allowed")
def robots_txt(site: str) -> str:
    """A site's robots.txt rules."""
    from .. import internet
    host = re.sub(r"^https?://", "", site.strip()).split("/")[0]
    return internet.request(f"https://{host}/robots.txt", max_bytes=50_000).text()[:4000]


@W(ex={"query": "how tall is mount everest"}, keys="search web results snippets")
def web_search_results(query: str) -> str:
    """Top web results (titles and snippets) for a search."""
    return I("SEARCH_READ", q=query)


@W(ex={"name": "indian railways"}, keys="official website find url")
def official_website(name: str) -> str:
    """The official website of an organisation, product or place."""
    from .. import internet
    hits = internet.search(name + " official website", 3)
    return "\n".join(f"{h.title}: {h.url}" for h in hits) or "Nothing found."


@W(ex={"topic": "indian constitution"}, keys="pdf document find download")
def find_pdf(topic: str) -> list:
    """Find PDF documents about a topic."""
    from .. import internet
    hits = [h for h in internet.search(topic + " filetype:pdf", 8) if ".pdf" in h.url.lower()]
    return [f"{h.title}: {h.url}" for h in hits] or ["No PDFs found."]


# ---- research & reading
@W(ex={"query": "large language models", "count": 3}, keys="research papers arxiv science academic")
def arxiv_search(query: str, count: int = 5) -> list:
    """Research papers on arXiv."""
    from .. import internet
    xml = internet.request(f"https://export.arxiv.org/api/query?max_results={max(1, min(count, 20))}&search_query=all:{Q(query)}", cache_seconds=3600).text()
    return [f"{t} — {l}" for t, l, _ in internet.parse_rss_items(xml, count)]


@W(ex={"doi": "10.1038/nature14539"}, keys="doi paper citation reference lookup")
def doi_lookup(doi: str) -> str:
    """Title, authors, journal and year for a DOI."""
    d = J("https://api.crossref.org/works/" + Q(doi.strip().removeprefix("https://doi.org/")), 86400).get("message", {})
    authors = ", ".join(f"{a.get('given', '')} {a.get('family', '')}".strip() for a in (d.get("author") or [])[:4])
    year = ((d.get("issued") or {}).get("date-parts") or [[None]])[0][0]
    return f"{(d.get('title') or ['?'])[0]} — {authors}. {(d.get('container-title') or [''])[0]} ({year})."


@W(ex={"title": "the hobbit"}, keys="book author published")
def book_info(title: str) -> str:
    """Who wrote a book and when it was first published."""
    return I("BOOK", q=title)


@W(ex={"author": "R K Narayan"}, keys="books by author list")
def books_by_author(author: str) -> str:
    """Well-known books by an author."""
    return I("AUTHOR_BOOKS", q=author)


@W(ex={"dish": "biryani"}, keys="recipe ingredients cook how to make")
def recipe(dish: str = "") -> str:
    """A recipe with ingredients (random if no dish given)."""
    return I("RECIPE_FOR", q=dish) if dish else I("RECIPE_RANDOM")


@W(ex={}, keys="mocktail drink non alcoholic recipe")
def mocktail_idea() -> str:
    """A non-alcoholic drink recipe."""
    return I("MOCKTAIL")


@W(ex={"barcode": "8901058851298"}, keys="barcode food product nutrition ingredients packet")
def food_product(barcode: str) -> str:
    """Product name, brand, ingredients and nutrition grade from a food barcode (Open Food Facts)."""
    d = J(f"https://world.openfoodfacts.org/api/v2/product/{re.sub(r'\\D', '', barcode)}.json?fields=product_name,brands,nutriscore_grade,ingredients_text,quantity", 86400)
    p = d.get("product")
    if not p:
        raise ToolError("that barcode isn't in Open Food Facts")
    grade = str(p.get("nutriscore_grade") or "").upper()
    grade = grade if len(grade) == 1 else "not rated"                       # Open Food Facts says "unknown" / "not-applicable"
    ingredients = re.sub(r"\s+([,:;.])", r"\1", " ".join(str(p.get("ingredients_text") or "not listed").split()))
    qty = f" ({p['quantity']})" if p.get("quantity") else ""
    return (f"{p.get('product_name') or 'Unnamed product'} by {p.get('brands') or 'an unknown brand'}{qty}; Nutri-Score {grade}. "
            f"Ingredients: {ingredients[:300]}")


# ---- entertainment
@W(ex={"query": "lata mangeshkar", "kind": "song"}, keys="songs music podcasts apps itunes search")
def music_search(query: str, kind: Literal["song", "album", "podcast", "audiobook"] = "song", count: int = 8) -> list:
    """Find songs, albums, podcasts or audiobooks (Apple's catalogue)."""
    ent = {"song": "song", "album": "album", "podcast": "podcast", "audiobook": "audiobook"}[kind]
    d = J(f"https://itunes.apple.com/search?country=IN&limit={max(1, min(count, 25))}&entity={ent}&term=" + Q(query), 3600)
    return [f"{r.get('trackName') or r.get('collectionName')} — {r.get('artistName')}" + (f" ({r['releaseDate'][:4]})" if r.get("releaseDate") else "") for r in d.get("results", [])]


@W(ex={"name": "panchayat"}, keys="tv show series info episodes")
def tv_show(name: str) -> str:
    """About a TV series: network, years, rating, summary."""
    d = J("https://api.tvmaze.com/singlesearch/shows?q=" + Q(name), 86400)
    from ..internet import first_sentences
    summary = re.sub(r"<[^>]+>", "", d.get("summary") or "")
    net = (d.get("network") or d.get("webChannel") or {}).get("name", "")
    return f"{d['name']} ({(d.get('premiered') or '')[:4]}–{(d.get('ended') or '')[:4] or 'now'}, {net}), rating {(d.get('rating') or {}).get('average') or 'n/a'}. {first_sentences(summary, 2)}"


@W(ex={"country": "IN"}, keys="tv schedule tonight what's on television")
def tv_schedule(country: str = "IN") -> list:
    """Today's TV schedule highlights in a country (two-letter code)."""
    d = J(f"https://api.tvmaze.com/schedule?country={country.upper()[:2]}", 3600)
    return [f"{e.get('airtime', '')} {e['show']['name']} — {e.get('name', '')}" for e in d[:30]]


@W(ex={}, keys="formula 1 f1 standings drivers championship")
def f1_standings() -> list:
    """Current Formula 1 drivers' championship."""
    d = J("https://api.jolpi.ca/ergast/f1/current/driverStandings.json", 3600)
    lists = d["MRData"]["StandingsTable"]["StandingsLists"]
    if not lists:
        raise ToolError("no standings yet")
    return [f"{s['position']}. {s['Driver']['givenName']} {s['Driver']['familyName']} ({s['Constructors'][0]['name']}) {s['points']} pts" for s in lists[0]["DriverStandings"][:10]]


@W(ex={}, keys="formula 1 f1 next race grand prix when")
def f1_next_race() -> str:
    """The next Formula 1 race and when it starts."""
    d = J("https://api.jolpi.ca/ergast/f1/current/next.json", 3600)
    races = d["MRData"]["RaceTable"]["Races"]
    if not races:
        return "No more races this season."
    r = races[0]
    return f"{r['raceName']} at {r['Circuit']['circuitName']}, {r['date']} {r.get('time', '')[:5]} UTC."


@W(ex={}, keys="joke funny laugh")
def joke() -> str:
    """A fresh joke (ask for the punchline with the answer)."""
    from .. import internet
    a = internet.info("JOKE", {})
    return f"{a.text} … {a.pending}" if a.pending else a.text


@W(ex={}, keys="quote inspiration motivation famous")
def inspiring_quote() -> str:
    """An inspiring quote."""
    return I("QUOTE")


@W(ex={}, keys="advice tip life")
def random_advice() -> str:
    """A random piece of advice."""
    return I("ADVICE")


@W(ex={}, keys="fact trivia useless fun")
def random_fact() -> str:
    """A random (useless but true-ish) fact."""
    return I("USELESS_FACT")


@W(ex={}, keys="cat fact animals")
def cat_fact() -> str:
    """A fact about cats."""
    return I("CAT_FACT")


@W(ex={}, keys="trivia quiz question game")
def trivia_question() -> str:
    """A multiple-choice trivia question (answer included at the end)."""
    from .. import internet
    a = internet.info("TRIVIA", {})
    return f"{a.text} (Answer: {a.pending})"


@W(ex={"animal": "dog"}, keys="cute dog cat picture photo random")
def animal_picture(animal: Literal["dog", "cat"] = "dog") -> str:
    """Link to a random dog or cat picture."""
    from .. import internet
    return internet.info("DOG_PHOTO" if animal == "dog" else "CAT_PHOTO", {}).open_url


# ---- space & earth
@W(ex={}, keys="iss space station location where")
def space_station_location() -> str:
    """Where the International Space Station is right now."""
    return I("ISS")


@W(ex={}, keys="astronauts people in space")
def people_in_space() -> str:
    """Who is in space right now."""
    return I("ASTRONAUTS")


@W(ex={}, keys="earthquake latest seismic")
def earthquakes_today() -> str:
    """Significant earthquakes in the last day."""
    return I("QUAKES")


@W(ex={}, keys="nasa astronomy picture of the day space photo apod")
def nasa_picture_of_the_day() -> str:
    """NASA's astronomy picture of the day."""
    from .. import internet
    a = internet.info("APOD", {})
    return f"{a.text} {a.open_url or ''}".strip()


@W(ex={"country": "Germany"}, keys="public holidays country upcoming")
def public_holidays(country: str) -> str:
    """Upcoming public holidays in a country (most countries; not India's lunar festivals)."""
    return I("HOLIDAYS", country=country)


@W(ex={"city": "Hyderabad", "days": 3}, keys="air quality forecast aqi tomorrow pollution")
def air_quality_forecast(city: str = "", days: int = 3) -> list:
    """Daily peak US AQI forecast for the next days."""
    from .. import internet
    p = internet.geocode(city) if city else internet.where_am_i()
    d = J(f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={p.lat}&longitude={p.lon}&hourly=us_aqi&forecast_days={max(1, min(days, 5))}&timezone=auto", 1800)
    h = d.get("hourly", {})
    by_day = {}
    for t, v in zip(h.get("time", []), h.get("us_aqi", [])):
        if v is not None:
            by_day[t[:10]] = max(by_day.get(t[:10], 0), v)
    return [f"{day}: peak AQI {round(v)} ({internet.aqi_words(v)})" for day, v in by_day.items()]


@W(ex={"text": "https://echo.example/app"}, keys="qr code make generate image link")
def qr_code_link(text: str, size: int = 300) -> str:
    """A link to a QR code image for some text or a URL (open it to view, save or print)."""
    s = max(100, min(size, 1000))
    return f"https://api.qrserver.com/v1/create-qr-code/?size={s}x{s}&data=" + Q(text)
