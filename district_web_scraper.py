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

load_dotenv()
OLLAMA_URL = os.getenv("OLLAMA_URL")
MODEL_NAME = os.getenv("MODEL_NAME")

def school_district_scrape(url):
    '''
    function scrapes school district websites to find board meeting minutes improvement plans and other relavent documents

    returns:
    
    '''
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

    


def initial_scrape(url):
    '''
    function saerches for school district with common tags to search for improvement plans

    returns:improvement plan
    
    '''

def district_web_scraper(url,blocked):
    '''
    function scrapes school district websites to find board meeting minutes improvement plans and other relavent documents

    returns:
    
    '''
    docs = []
    docs = initial_scrape(url)
    if docs is None:
        pass

    return



if __name__ == "__main__":
    tempUrl = "https://www.maywood89.org/"
    

    school_district_scrape(tempUrl)
    



