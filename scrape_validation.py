'''
general function to check for user permissions ot scrape a website based on the robots.txt file
'''

import requests
from urllib.parse import urljoin, urlparse

def get_blocked_urls(url):
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
        if response.status_code != 200:
            print("No robots.txt file found.")
            return []

        blocked_paths = []
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
                    blocked_paths.append(path)
            

        return blocked_paths

    except Exception as e:
        print(f"Error reading robots.txt: {e}")
        return []



if __name__ == "__main__":
    # Example usage
    url = "https://www.youtube.com"
    blocked = get_blocked_urls(url)
    print(f"Blocked paths for {url}: {blocked}")