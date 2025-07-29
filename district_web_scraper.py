import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import urllib.robotparser
import pandas as pd

def school_district_scrape(url):
    '''
    function scraped school district websites

    returns:
    Str - the html of the school district website
    '''
    if can_scrape(url):
        pass

def can_scrape(url):
    '''
    function checks if the user has persmission to scrape the website based on the robots.txt file.

    args:
    url: str - the url of the website to check for permission

    returns:
    bool - False if scraping is not allowed, True otherwise
    '''
    try:
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

        #get to the robots.txt file if it exists
        robots_url = urljoin(base_url, '/robots.txt')
        response = requests.get(robots_url,timeout=5)

        #if there isnt a page then we return True
        if response.status_code == 404:
            print("there is no robots.txt file")
            return True
        
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()

        return rp.can_fetch("*", url)
    
    except Exception as e:
        return True


if __name__ == "__main__":
    tempUrl = "http://www.kcsd96.org"
    district_Html = school_district_scrape(tempUrl)



