# search_improvement_plans.py
import re
import asyncio
from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse, quote_plus

from playwright.async_api import async_playwright

# --- Tunables --------------------------------------------------------------

SEARCH_VARIANTS = [
    '"district improvement plan"',
    '"school improvement plan"',
    '"strategic plan"',
    '"improvement plan"'
]

KEYWORD_PATTERNS = [
    r"\bdistrict improvement plan\b",
    r"\bschool improvement plan\b",
    r"\bstrategic plan\b",
    r"\bcontinuous improvement plan\b",
    r"\bimprovement plan\b"
]

ALLOW_HOST_HINTS = (
    "boarddocs", "finalsite", "sharpeschool", "blackboard",
    "core-docs", "coredocs", "sharepoint", "onedrive", "google.com",
    "drive.google.com", "docs.google.com", "s3.", "amazonaws.com",
    "box.com", "dropbox.com"
)

MAX_SERP_PER_QUERY = 12     # keep this modest for speed
TOP_N_RESULTS = 5           # final results per district
VERIFY_TARGETS = True       # quick HEAD/GET verify

# --- Helpers ---------------------------------------------------------------
def host_matches_base(host: str, base_domain: str) -> bool:
    # e.g., host: files.maywood89.org matches base_domain: maywood89.org
    return host == base_domain or host.endswith("." + base_domain)

def extract_domain(district_url: str) -> str:
    return urlparse(district_url).netloc.lower().lstrip("www.")

def guess_aliases(district_name: str) -> List[str]:
    """
    Build a small alias set: full name, compressed name, 'SD <num>' if present, and number-only forms.
    """
    name = district_name.strip()
    aliases = {name}

    # Drop common words to create a short alias
    short = re.sub(r"\b(school|public|unified|community|consolidated|elementary|high|unit|district)\b", "", name, flags=re.I)
    short = re.sub(r"\s+", " ", short).strip()
    if short:
        aliases.add(short)

    # Pull digits (district number) if exist
    digits = re.findall(r"\b(\d{1,4})\b", name)
    for d in digits:
        aliases.add(f"sd {d}")
        aliases.add(f"district {d}")
        aliases.add(d)

    # Common “DIST <num>” / “D <num>” styles
    for d in digits:
        aliases.add(f"d {d}")
        aliases.add(f"dist {d}")

    # Lowercase versions
    aliases_lower = {a.lower() for a in aliases}
    return list(aliases_lower)

def any_keyword(text: str) -> bool:
    t = (text or "").lower()
    for pat in KEYWORD_PATTERNS:
        if re.search(pat, t):
            return True
    # allow looser match (strategic + plan within string)
    return ("strategic" in t and "plan" in t) or ("improvement" in t and "plan" in t)

def name_matches(text: str, name_aliases: List[str]) -> bool:
    t = (text or "").lower()
    return any(a in t for a in name_aliases)

def host_from_url(u: str) -> str:
    return urlparse(u).netloc.lower().lstrip("www.")

def looks_like_pdf(url: str) -> bool:
    u = url.lower()
    return u.endswith(".pdf") or ".pdf" in u

def is_allowed_offdomain(host: str) -> bool:
    return any(hint in host for hint in ALLOW_HOST_HINTS)

# --- SERP scraping (Bing) --------------------------------------------------

async def fetch_bing_results(page, query: str, max_results: int = MAX_SERP_PER_QUERY) -> List[Dict[str, str]]:
    """
    Returns a list of {title, url, snippet, query}
    """
    print("fetching bing results for query:")
    q = f"https://www.bing.com/search?q={quote_plus(query)}&setlang=en-US"
    await page.goto(q, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(600)  # settle a bit

    # We target the result blocks: li.b_algo
    items_locator = page.locator("li.b_algo")
    count = await items_locator.count()
    out = []

    for i in range(min(count, max_results)):
        block = items_locator.nth(i)
        a = block.locator("h2 a")
        if await a.count() == 0:
            continue
        title = (await a.inner_text()).strip()
        print("Title found:", title)
        url = await a.get_attribute("href")
        if not url:
            continue
        # snippet
        snip = ""
        cap = block.locator(".b_caption p")
        if await cap.count() > 0:
            snip = (await cap.first.inner_text()).strip()

        out.append({"title": title, "url": url, "snippet": snip, "query": query})
    return out

# --- Scoring & filtering ---------------------------------------------------

def score_candidate(item: Dict[str, str], district_domain: str, name_aliases: List[str]) -> Tuple[int, str]:
    """
    Returns (score, why_string)
    """
    title = item.get("title", "")
    url = item.get("url", "")
    snippet = item.get("snippet", "")
    host = host_from_url(url)

    score = 0
    reasons = []

    # File type
    if looks_like_pdf(url):
        score += 3
        reasons.append("PDF")

    # Domain match or allowed off-domain with name match
    if host == district_domain:
        score += 2
        reasons.append("domain match")
    elif is_allowed_offdomain(host) and name_matches(title + " " + url + " " + snippet, name_aliases):
        score += 1
        reasons.append("trusted host + name match")

    # Keyword checks
    if any_keyword(title):
        score += 2
        reasons.append("title has keywords")
    if any_keyword(url):
        score += 1
        reasons.append("url has keywords")
    if any_keyword(snippet):
        score += 1
        reasons.append("snippet has keywords")

    # Name matches
    if name_matches(title, name_aliases) or name_matches(url, name_aliases):
        score += 1
        reasons.append("name match")

    # Penalties for clearly irrelevant hosts
    if any(bad in host for bad in ("facebook.com", "twitter.com", "x.com", "youtube.com", "instagram.com", "calendar.google.com")):
        score -= 2
        reasons.append("social/calendar")

    return score, ", ".join(reasons)

# --- Quick verification ----------------------------------------------------

async def quick_verify(playwright_request_ctx, url: str) -> Dict[str, Any]:
    """
    HEAD for PDFs; shallow GET for HTML; returns {'ok': bool, 'content_type': str, 'title': str}
    """
    info = {"ok": False, "content_type": None, "title": None}

    try:
        # HEAD first
        resp = await playwright_request_ctx.fetch(url, method="HEAD", max_redirects=5, timeout=15000, fail_on_status_code=False)
        ct = (resp.headers.get("content-type") or "").lower()
        info["content_type"] = ct

        if resp.status == 200:
            info["ok"] = True

        # If content-type says HTML, do a tiny GET to extract <title>
        if "text/html" in ct or (ct == "" and not looks_like_pdf(url)):
            resp_get = await playwright_request_ctx.fetch(url, method="GET", max_redirects=5, timeout=20000, fail_on_status_code=False)
            if resp_get.status in (200, 203, 204, 206):
                text = await resp_get.text()
                # only look for <title> (avoid heavy parsing)
                m = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.I | re.S)
                if m:
                    title_text = re.sub(r"\s+", " ", m.group(1)).strip()
                    info["title"] = title_text
                    info["ok"] = True
        return info
    except Exception:
        return info

# --- Main entry ------------------------------------------------------------

async def search_dip_for_district(
    district_name: str,
    district_url: str,
    pdf_only_first: bool = True,
    top_n: int = TOP_N_RESULTS
) -> List[Dict[str, Any]]:
    """
    Returns: list of dicts:
      {
        "title": str,
        "url": str,
        "host": str,
        "filetype": "pdf"|"html"|"unknown",
        "score": int,
        "why": str,
        "found_by_query": str,
        "verified": bool,
        "verified_title": Optional[str],
        "verified_content_type": Optional[str],
      }
    """
    print("extracting domain from url")
    district_domain = extract_domain(district_url)
    if not district_domain:
        raise ValueError(f"Could not extract domain from URL: {district_url}")
    else:
        print('district domain: ' + district_domain)
        
    print("shortening " + district_name + " to aliases")
    name_aliases = guess_aliases(district_name)
    if not name_aliases:
        raise ValueError("something went wrong with creating aliases")
    else:
        print("name aliases: " + str(name_aliases))
    

    print("going into playwright to seach for results")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"),
            viewport={"width": 1366, "height": 900}
        )
        page = await context.new_page()

        # API-like HTTP context for quick verification
        req_ctx = await p.request.new_context()

        seen_urls = set()
        candidates: List[Dict[str, Any]] = []

        async def do_round(pdf_only: bool):
            for v in SEARCH_VARIANTS:
                q = f'{district_name} {v}'
                if pdf_only:
                    q = f'{q} filetype:pdf'
                    print(f"Searching (PDF only): {q}")

                serp = await fetch_bing_results(page, q, MAX_SERP_PER_QUERY)
                for item in serp:
                    url = item["url"]
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    # First-pass filter: must have keyword somewhere
                    if not (any_keyword(item["title"]) or any_keyword(item["url"]) or any_keyword(item["snippet"])):
                        continue

                    # Keep if (a) host matches district or (b) title/url/snippet match a name alias
                    host = host_from_url(url)
                    if (host == district_domain) or name_matches(item["title"] + " " + item["url"] + " " + item["snippet"], name_aliases) or is_allowed_offdomain(host):
                        sc, why = score_candidate(item, district_domain, name_aliases)
                        if sc <= 0:
                            continue
                        candidates.append({
                            "title": item["title"].strip(),
                            "url": url,
                            "host": host,
                            "filetype": "pdf" if looks_like_pdf(url) else ("html" if url.lower().endswith((".htm", ".html", "/")) else "unknown"),
                            "score": sc,
                            "why": why,
                            "found_by_query": item["query"],
                            "verified": False,
                            "verified_title": None,
                            "verified_content_type": None
                        })

        # Round 1: PDF-only (fast path to the actual plan files)
        if pdf_only_first:
            await do_round(pdf_only=True)

        # Round 2: General (HTML allowed) if still thin
        if len(candidates) < top_n:
            await do_round(pdf_only=False)

        # De-dup by URL and keep best score
        best_by_url: Dict[str, Dict[str, Any]] = {}
        for c in candidates:
            u = c["url"]
            if u not in best_by_url or c["score"] > best_by_url[u]["score"]:
                best_by_url[u] = c

        results = list(best_by_url.values())
        # Quick verification step
        if VERIFY_TARGETS and results:
            tasks = [quick_verify(req_ctx, r["url"]) for r in results]
            verifs = await asyncio.gather(*tasks, return_exceptions=True)
            for r, info in zip(results, verifs):
                if isinstance(info, dict):
                    r["verified"] = bool(info.get("ok"))
                    r["verified_content_type"] = info.get("content_type")
                    if info.get("title"):
                        r["verified_title"] = info["title"]
                        # small bonus if verified title has keywords
                        if any_keyword(info["title"]):
                            r["score"] += 1
                            r["why"] = (r["why"] + ", verified title has keywords").strip(", ")

        # Sort by score descending and trim
        results.sort(key=lambda x: x["score"], reverse=True)
        await browser.close()
        await req_ctx.dispose()

        return results[:top_n]




#--- unfinished --------------------------------------------------------------


# the previous verify 
def verifyLinks(districtList, districtName) -> dict:
    '''
    function validates if the links found from the initial scrape are valid to the school districh which we are currently looking for
    args:
        DistrictList: tuple
            tuple - list of links to top results from initial scrape
    returns: dict
        dict - dictionary for the most likely link to the improvement plans for the district or none if no valid links are found
    '''
    for district in districtList:
        districtName = re.sub(r'[^a-zA-Z]','', districtName)
        if districtName in district['title'] or districtName in district['url']:
            print("contains district name")
        
        





# --- Example usage ---------------------------------------------------------

if __name__ == "__main__":
    async def main():
        district_name = "Maywood School District 89"
        district_url = "https://www.maywood89.org/"
        print('going into the search for district function')
        hits = await search_dip_for_district(district_name, district_url, pdf_only_first=True, top_n=5)
        for i, h in enumerate(hits, 1):
            print(f"{i}. [{h['score']}] {h['title']}\n   {h['url']}\n   why: {h['why']}\n   verified={h['verified']} ct={h['verified_content_type']} vt={h['verified_title']}\n")

    asyncio.run(main())
