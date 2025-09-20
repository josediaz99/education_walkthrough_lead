import requests
import pandas as pd
from scrape_validation import get_blocked_urls
import os
import asyncio
import re
import time
from collections import deque
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from searchThroughQuery import search_dip_for_district, verifyLinks
load_dotenv()
OLLAMA_URL = os.getenv("OLLAMA_URL")
MODEL_NAME = os.getenv("MODEL_NAME")

async def school_district_scrape(url, districtName):
    '''
    function scrapes school district websites to find board meeting minutes improvement plans and other relavent documents

    returns:
    
    '''
    print("Starting scrape for URL:", url)
    dip_links = await search_dip_for_district(districtName, url, pdf_only_first=True, top_n=5)
    if dip_links:
        print("District improvement plan links found now verifying...")
        verified_link = verifyLinks(dip_links, districtName)
        if verified_link is not None:
            print("Verified Link:", verified_link)
            return verified_link
    
    blocked = None
    docs = []
    docs = initial_scrape(url)
    if docs is None:
        print("No documents found in initial search.")
        blocked = get_blocked_urls(url)
        if blocked is not None:
            print("Blocked URLs:", blocked)
        else:
            print("No blocked URLs found.")
        district_web_scraper(url,blocked)

    

def district_web_scraper(url,districtName,blocked):
    '''
    function scrapes school district websites to find board meeting minutes improvement plans and other relavent documents

    returns:
    
    '''
   
    if dip_links is None:
        pass
    else:
        verified_link = verifyLinks(dip_links, districtName)
        if verified_link is not None:
            print("Verified Link:", verified_link)
        else:
            print("No verified link found.")
    return



if __name__ == "__main__":
    tempUrl = "https://www.maywood89.org/"
    
    import asyncio
    asyncio.run(school_district_scrape(tempUrl, "maywood89"))
    



