'''
general function to check for user permissions ot scrape a website based on the robots.txt file
'''

import requests
from urllib.parse import urljoin, urlparse
import urllib.robotparser


def can_scrape(url):
    '''
    function takes in a url which checks if the user has persmission to scrape the website based on the robots.txt file and returns a list of urls which are not allowed to be scraped

    args:
    url: str - the url of the website to check for permission

    returns:
    tuple:
        bool - False if scraping is not allowed, True otherwise
        list - returns a list of urls that are not allowed to be scraped
    '''
    try:
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

        #get to the robots.txt file if it exists
        robots_url = urljoin(base_url, '/robots.txt')
        response = requests.get(robots_url,timeout=5)

        #if there isnt a page then we return True with an empty list 
        if response.status_code == 404:
            print("there is no robots.txt file")
            return True,[]
        
        #check what we cannot scrape
        disallowed_paths = []
        lines = response.text.splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("user-agent:"):
                current_user_agent = line.split(":", 1)[1].strip()
                applies_to_us = current_user_agent == "*"
            elif applies_to_us and line.lower().startswith("disallow:"):
                path = line.split(":", 1)[1].strip()
                if path:
                    disallowed_paths.append(path)

        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        is_allowed = rp.can_fetch("*", url)

        return is_allowed, disallowed_paths
    
    except Exception as e:
        return True,[]
