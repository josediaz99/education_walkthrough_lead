# search_improvement_plans.py
import re
import asyncio
from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse, quote_plus
import random
from playwright.async_api import async_playwright

# --- Tunables --------------------------------------------------------------

SEARCH_VARIANTS = [
    'district improvement plan',
    'strategic plan',
    'improvement plan'
]

desired_docs = [
    r"\bdistrict improvement plan\b",
    r"\bstrategic plan\b",
    r"\bimprovement plan\b"
]

ALLOW_HOST_HINTS = (
    "boarddocs", "finalsite", "sharpeschool", "blackboard",
    "core-docs", "coredocs", "sharepoint", "onedrive", "google.com",
    "drive.google.com", "docs.google.com", "s3.", "amazonaws.com",
    "box.com", "dropbox.com"
)

MAX_SERP_PER_QUERY = 15     # keep this modest for speed
TOP_N_RESULTS = 5           # final results per district
VERIFY_TARGETS = True       # quick HEAD/GET verify

# --- Helpers ---------------------------------------------------------------
def any_keyword(text: str) -> bool:
    '''
    function takes in aomw twxt from the title, url, or description and returns if any of the the any of the plans are found in the title
    '''
    t = (text or "").lower()
    for desired_doc in desired_docs:
        if re.search(desired_doc, t):
            return True
    # allow looser match (strategic + plan within string)
    return ("strategic" in t and "plan" in t) or ("improvement" in t and "plan" in t)

def name_matches(text: str, name_aliases: List[str]) -> bool:
    """
    returns if the texts contains the names of any of the aliases"""
    t = (text or "").lower()
    return any(a in t for a in name_aliases)

def host_from_url(u: str) -> str:
    """returns a cleaned up host from a url"""
    return urlparse(u).netloc.lower().lstrip("www.")

def looks_like_pdf(url: str) -> bool:
    """checks if the url contains or ends in pdf"""
    u = url.lower()
    return u.endswith(".pdf") or ".pdf" in u

def is_allowed_offdomain(host: str) -> bool:
    return any(hint in host for hint in ALLOW_HOST_HINTS)


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

# --- search plans through bing  --------------------------------------------------

async def fetch_bing_results(page, query: str, max_results: int = MAX_SERP_PER_QUERY) -> List[Dict[str, str]]:
    """
    Returns a list of {title, url, snippet, query}
    """
    print("fetching bing results for query:")
    q = f"https://www.bing.com/search?q={quote_plus(query)}&setlang=en-US"
    await page.goto(q, wait_until="domcontentloaded", timeout=300000)
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

def score_candidate(item: Dict[str, str], name_aliases: List[str]) -> Tuple[int, str]:
    """
    functions takes a district and its information and returns a score for meeting requirements
    - pdf
    
    args:
        item: dict
            dict - dictionary with keys: title, url, snippet
        name_aliases: list
            list - list of name aliases for the district
    Returns (score, why_string)
    """
    title = item.get("title", "")
    url = item.get("url", "")
    snippet = item.get("snippet", "")
    host = host_from_url(url)

    score = 0
    reasons = []
    print("Scoring candidate:", title, url)
    # File type
    if looks_like_pdf(url):
        score += 3
        reasons.append("PDF")

    # Domain match or allowed off-domain with name match
    '''
    if host == district_domain:
        score += 2
        reasons.append("domain match")
    '''
    
    if name_matches(title + " " + url + " " + snippet, name_aliases):
        for name in name_aliases:
            if name in host:
                score += 1
                reasons.append("alias name " + name+ " in found")

    # Keyword checks
    if any_keyword(title):
        score += 3
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

    # Penalize social media / calendar links     
    if any(bad in host for bad in ("facebook.com", "twitter.com", "x.com", "youtube.com", "instagram.com", "calendar.google.com")):
        score -= 5
        reasons.append("social-media/calendar")

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

async def search_dip_for_district(district_name: str, top_n: int = TOP_N_RESULTS) -> List[Dict]:
    """
    Returns: list of dicts:
      {
        "title": str,
        "url": str,
        "score": int,
        "why": str,
        "found_by_query": str,
      }
    """
        
    print("creating " + district_name + " to aliases")
    name_aliases = guess_aliases(district_name)

    if not name_aliases:
        raise ValueError("something went wrong with creating aliases")
    else:
        print("name aliases: " + str(name_aliases))
    

  
    async with async_playwright() as p:
        users = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
                 "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
                 "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
                 "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
                 "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
                 "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:130.0) Gecko/20100101 Firefox/130.0",
                 "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"]

        rand_user_agent = random.choice(users)
        browser = await p.chromium.launch(headless=False, args=["--no-sandbox"])
        context = await browser.new_context(
            user_agent=(rand_user_agent),
            viewport={"width": 1366, "height": 900}
        )
        page = await context.new_page()

        # API-like HTTP context for quick verification
        req_ctx = await p.request.new_context()

        seen_urls = set()
        candidates: List[Dict[str, Any]] = []

        async def do_round():
            for v in SEARCH_VARIANTS:
                q = f'{district_name} {v}'

                serp = await fetch_bing_results(page, q, MAX_SERP_PER_QUERY)
                for item in serp:
                    url = item["url"]
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    # search for keywords in title/url/snippet
                    if not (any_keyword(item["title"]) or any_keyword(item["url"]) or any_keyword(item["snippet"])):
                        continue

                    #add some contect to each link
                    host = host_from_url(url)
                    if name_matches(item["title"] + " " + item["url"] + " " + item["snippet"], name_aliases) or is_allowed_offdomain(host):
                        sc, why = score_candidate(item, name_aliases)
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

        
        
        #get more results if pdf list is too short
        
        await do_round()

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
        print(f"Found {len(results)} candidates, returning top {top_n}")
        await browser.close()
        await req_ctx.dispose()

        return results[:top_n]



# --- Example usage ---------------------------------------------------------

if __name__ == "__main__":
    async def main():
        district_name = "Maywood School District 89"
        print('going into the search for district function')
        hits = await search_dip_for_district(district_name,top_n=5)
        for i, h in enumerate(hits, 1):
            print(f"{i}. [{h['score']}] {h['title']}\n   {h['url']}\n   why: {h['why']}\n   verified={h['verified']} type={h['verified_content_type']}\n")

    asyncio.run(main())
