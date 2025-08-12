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
        robots_url = urljoin(base_url, '/robots.txt')

        response = requests.get(robots_url, timeout=5)
        if response.status_code == 404:
            print("No robots.txt file found.")
            return True, []

        disallowed_paths = []
        applies = False

        for line in response.text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if line.lower().startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip()
                applies = (agent == "*")
            elif applies and line.lower().startswith("disallow:"):
                path = line.split(":", 1)[1].strip()
                if path:
                    disallowed_paths.append(path)
            elif line.lower().startswith("user-agent:") and applies:
                # Reached a new user-agent, stop recording
                applies = False

        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()

        is_allowed = rp.can_fetch("*", url)

        return is_allowed, disallowed_paths

    except Exception as e:
        print(f"Error reading robots.txt: {e}")
        return True, []



if __name__ == "__main__":
    # Example usage
    url = "https://www.youtube.com"
    allowed, non_paths = can_scrape(url)
    if allowed:
        print(f"Scraping is allowed for {url}. blocked paths: {non_paths}")
    else:
        print(f"Scraping is not allowed for {url}")