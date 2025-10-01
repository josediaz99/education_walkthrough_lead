# search_improvement_plans.py
import re
import asyncio
from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse, quote_plus, unquote, parse_qs
import random
from playwright.async_api import async_playwright
import subprocess
# --- Tunables --------------------------------------------------------------

SEARCH_VARIANTS = [
    'district improvement plan',
    'strategic plan',
    'improvement plan'
]

desired_docs = [
    r"\bdistrict improvement plan\b",
    r"\bstrategic plan\b",
    r"\bimprovement plan\b",
    r"\dip",
    r"\bboard minutes\b",
    r"\bschool board goals\b",
    r"\bcsip\b",
    r"\baccredidation self-study\b",
    r"\bcurrent goals\b"
]



MAX_SERP_PER_QUERY = 7     # keep this modest for speed
TOP_N_RESULTS = 5           # final results per district
VERIFY_TARGETS = True       # set this to false to skip verification step

# --- Helpers ---------------------------------------------------------------
def any_keyword(text: str) -> tuple [bool,str]:
    '''
    function takes in aomw twxt from the title, url, or description and returns if any of the the any of the plans are found in the title
    '''
    t = (text or "").lower()
    for desired_doc in desired_docs:
        if re.search(desired_doc, t):
            return True
    # allow looser match (strategic + plan within string)
    return ("strategic" in t and "plan" in t) or ("improvement" in t and "plan" in t)

def resolve_bing_redirect(url: str) -> str:
    p = urlparse(url)
    if p.netloc.lower().endswith("bing.com") and p.path.startswith("/ck/a"):
        qs = parse_qs(p.query)
        if "u" in qs and qs["u"]:
            # sometimes Bing double-encodes; unquote twice if needed
            target = unquote(qs["u"][0])
            maybe_twice = unquote(target)
            return maybe_twice if maybe_twice.startswith(("http://", "https://")) else target
    return url

def clean_host(u: str) -> str:
    u = resolve_bing_redirect(u)
    host = urlparse(u).netloc.lower()
    return re.sub(r"^www\d?\.", "", host)

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

def guess_filename_from_url(url: str) -> str:
    '''
    function will parse through url to determine a name based on relevant text in the url
    '''
    path = urlparse(url).path
    if not path:
        return None
    return unquote(path.split("/")[-1]) or None

def guess_aliases(district_name: str) -> List[str]:
    """
    Build a small alias set: full name, compressed name, 'SD <num>' if present, 
    number-only forms, and acronym+number forms.
    """
    name = district_name.strip()
    aliases = {name}

    # Drop common words to create a short alias
    short = re.sub(
        r"\b(school|public|unified|community|consolidated|elementary|high|unit|district|ccsd|usd|isd|cusd|cus|sd)\b",
        "",
        name,
        flags=re.I
    )
    short = re.sub(r"\s+", " ", short).strip()
    if short:
        aliases.add(short)

    # Pull digits (district number) if exist
    digits = re.findall(r"\b(\d{1,4})\b", name)
    for d in digits:
        aliases.add(f"sd {d}")
        aliases.add(f"district {d}")
        aliases.add(f"d {d}")
        aliases.add(f"dist {d}")
        aliases.add(d)

    # Acronym + number: Sprint Valley CCSD 99 → sv99
    parts = [w for w in re.split(r"\s+", short) if w.isalpha()]
    if parts:
        acronym = "".join(p[0].lower() for p in parts)
        if digits:
            for d in digits:
                aliases.add(acronym + d)
        else:
            aliases.add(acronym)

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

def score_candidate(item: Dict, name_aliases: List[str]) -> Tuple:
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
    host = clean_host(url)
   
    irrelevant_links = ["survey","facebook.com", "twitter.com", "x.com", "youtube.com", "instagram.com", "calendar.google.com","isbe.net","reportcard"]

    score = 0
    reasons = []

    for unwanted in irrelevant_links:
        if unwanted in (host + url +title):
            return 0, f"links to {unwanted}"

    print("Scoring candidate:", title, url, snippet, "\n")
    # File type
    if looks_like_pdf(url):
        score += 3
        reasons.append("PDF")
    
    if name_matches(title + " " + url, name_aliases):
        for name in name_aliases:
            if name in title or name in url or name in snippet:
                score += 1
                reasons.append("alias name " + name + " in"+ host)

    # checks if any of the plans we are searching for are listed in any of the link,title,description/snippet
    if any_keyword(title):
        score += 3
        reasons.append("title contains desired document")
    if any_keyword(url):
        score += 2
        reasons.append("url contains desired document")
    if any_keyword(snippet):
        score += 1
        reasons.append("snippet contains desired document")

    # searching for references to the school we are searching for 
    '''if name_matches(title, name_aliases) or name_matches(url, name_aliases):
        score += 1
        reasons.append("aliases match")
    else: # we want to make sure we are not getting links which dont contain a reference to the school we are searcing for
        score = 0
        reasons.append("aliases not found")'''

    # Penalize social media / calendar links
    
    
    return score, ", ".join(reasons)

# --- Quick verification ----------------------------------------------------

async def quick_verify(playwright_request_ctx, url: str) -> Dict[str, Any]:
    """
    this functions takes in the url and some context we need to verify get the information and we return some information for our candidates 
    this function also generates a title for the documents when there is none to be retrieved
    return
    info: {ok: bool, content_type: (ex. pdf/html). title}
    """
    info = {"ok": False, "content_type": None, "title": None}

    try:
        # HEAD first
        resp = await playwright_request_ctx.fetch(url, method="HEAD", max_redirects=5, timeout=15000, fail_on_status_code=False)
        ct = (resp.headers.get("content-type") or "").lower()
        info["content_type"] = ct

        print("checking for status for ",url )
        if resp.status == 200:
            info["ok"] = True
            print('status ok')

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
        
        # If it's a PDF
        if "/pdf" in ct or looks_like_pdf(url):
            # Try to get filename from headers
            disp = resp.headers.get("content-disposition", "")
            m = re.search(r'filename="?([^"]+)"?', disp, flags=re.I)
            if m:
                info["title"] = m.group(1)
            else:
                # fallback: filename from URL path
                info["title"] = guess_filename_from_url(url)

            info["ok"] = resp.status == 200

        return info
    except Exception:
        return info

# --- Main entry ------------------------------------------------------------

async def search_dip_for_district(district_name: str, state = None) -> List[Dict]:
    """
    this function queries for district documents and returns a list of possible candidates in a list of dictionaries ordered by the score
    Returns: list of dicts:
      {
        "title": str,
        "url": str,
        "snippet": str,
        "score": int,
        "why": str,
        "found_by_query": str,
      }
    """
        
    print("creating " + district_name + " to aliases: ")
    name_aliases = guess_aliases(district_name)

    if not name_aliases:
        raise ValueError("something went wrong with creating aliases")
    else:
        print("name aliases: " + str(name_aliases) + "\n")
    

  
    async with async_playwright() as p:
        users = [
            # Chrome
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.119 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.119 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.119 Safari/537.36",

            # Firefox
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13.5; rv:125.0) Gecko/20100101 Firefox/125.0",
            "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",

            # Safari
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",

            # Edge
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.119 Safari/537.36 Edg/124.0.2478.67",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.119 Safari/537.36 Edg/124.0.2478.67",
        ]
        
        seen_urls = set()
        candidates: List[Dict[str, Any]] = []

        async def do_round(variant):
                """
                queries for documents based on varients and stores them as a dict while preventing being blocked through revolving user agents
                args:
                    variant: str
                        str - the type of document we are searching for
                """
                rand_user_agent = random.choice(users) #prevent being blocked by bing
                print("Using random user agent: " + rand_user_agent + "\n")
                browser = await p.chromium.launch(headless=False, args=["--no-sandbox"])
                context = await browser.new_context(
                    user_agent=(rand_user_agent),
                    viewport={"width": 1366, "height": 900}
                )
                page = await context.new_page()

                # API-like HTTP context for quick verification
                req_ctx = await p.request.new_context()

                # Construct query
                if state:
                    q = f'{state} {district_name} {variant}'
                else:
                    q = f'{district_name} {variant}'

                serp = await fetch_bing_results(page, q, MAX_SERP_PER_QUERY)
                for item in serp:
                    url = item["url"]
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    # search for desired documents in title/url/snippet
                    if not (any_keyword(item["title"]) or any_keyword(item["url"]) or any_keyword(item["snippet"]) or name_matches(item["title"],name_aliases) or name_matches(item["url"],name_aliases) or name_matches(item["snippet"],name_aliases)):
                        continue

                    #add some context to each link
                    host = host_from_url(url)
                    if name_matches(item["title"] + " " + item["url"] + " " + item["snippet"], name_aliases) :
                        
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
                            "verified_content_type": None,
                            'req_ctx': req_ctx,
                            'snippet': item["snippet"]
                        })
                        await browser.close()
                        await req_ctx.dispose()

        
        #get more results if pdf list is too short
        for v in SEARCH_VARIANTS:   
            await do_round(v)

        # De-dup by URL and keep best score
        best_by_url: Dict[str, Dict] = {}
        for c in candidates:
            u = c["url"]
            if u not in best_by_url or c["score"] > best_by_url[u]["score"]:
                best_by_url[u] = c

        results = list(best_by_url.values())
        # Quick verification step
        if VERIFY_TARGETS and results:
            tasks = [quick_verify(r['req_ctx'], r["url"]) for r in results]
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
        print(f"Found {len(results)} candidates")
        

        return results[:15]

    """
    usses ollama llm to create a response
    """
    
# --- Example usage ---------------------------------------------------------

if __name__ == "__main__":
    import pandas as pd

    async def main():
        district_df = pd.read_excel("dir_ed_entities.xls",sheet_name=1, usecols=['FacilityName','RecType'])
        district_df = district_df[district_df['RecType']=='Dist']
        district_name = district_df['FacilityName'].sample(n=1).values[0]

        print('searching for district: \n')
        print(district_name + "\n")
        hits = await search_dip_for_district(district_name,state="Illinois")
        for i, h in enumerate(hits, 1):
            print(f"{i}. [{h['score']}] {h['title']}\n   {h['url']}\n   why: {h['why']}\n   verified={h['verified']} type={h['verified_content_type']}\n")

    asyncio.run(main())
