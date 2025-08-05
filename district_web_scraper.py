import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import urllib.robotparser
import pandas as pd
from scrape_validation import can_scrape

def school_district_scrape(url):
    '''
    function scraped school district websites

    returns:
    Str - the html of the school district website
    '''
    if can_scrape(url):
        pass


if __name__ == "__main__":
    tempUrl = "http://www.kcsd96.org"
    district_Html = school_district_scrape(tempUrl)



