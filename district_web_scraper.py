import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import pandas as pd
import random

df = pd.read_excel('dir_ed_entities.xls', sheet_name=1,usecols=['CountyName','RecType','FacilityName','Administrator','Website'])
school_districts_df = df[df["RecType"] == "Dist"]
