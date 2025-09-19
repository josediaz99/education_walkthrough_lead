'''
file is meant to access school digger api and return the list of shool district given a state
'''
import requests
import json
from dotenv import load_dotenv
import os
#------------we will make calls only to the too which will return mutiple school districts-------------------------
url = "https://api.schooldigger.com/v2.3/districts"

#------------list of states in the us-------------------------
states = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]

#------------load the api key and app id from the .env file-------------------------
load_dotenv()

API_key = os.getenv("SCHOOLDIGGER_APP_KEY")  # replace with your actual API key
APP_ID = os.getenv("SCHOOLDIGGER_APP_ID")  # replace with your actual APP ID

if not APP_ID:#check if we retrieved the api key and id from our .env file
    raise ValueError("No APP ID set for SchoolDigger API")
else:
        print("APP ID successfully loaded")
if not API_key:#check if we retrieved the api key and id from our .env file
    raise ValueError("No API key set for SchoolDigger API")
else:
        print("API key successfully loaded")

#------------function to get the list of school districts given a state-------------------------

def get_school_districts(state) -> list[dict]:
    """this function will return a list of school district information given a state

    Args:
        state (String): state name to search for school districts
    Returns:
        stateDistricts (list[dict]): lift of school district in the json format returned by the api
    """
    important_fields = ["districtID", "districtName", "state", "city", "zip", "phone", "url", "lowGrade", "highGrade", "numberTotalSchools"]
    stateDistricts: list[dict] = []
    
    page = 1
    max_page = 50 #50 is the suggested max
    
    while True:
        params = {
            "st":state,
            "page": page,
            "perPage": max_page,
            "appID":APP_ID,
            "appKey":API_key,
        }

        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()  # Raise an error for bad status codes
        data = response.json()

        rows = data.get("districtList") 

        for r in rows:
            filtered_row = {key: r[key] for key in important_fields if key in r}
            filtered_row["street"] = r["address"]["street"]
            filtered_row["city"] = r["address"]["city"]
            filtered_row["state"] = r["address"]["state"]
            filtered_row["zip"] = r["address"]["zip"]
            filtered_row["countyName"] = r["county"]["countyName"]
            stateDistricts.append(filtered_row)

        if len(rows) < max_page:
            print("All data retrieved")
            break
        page += 1
        
    return stateDistricts
    

if __name__ == "__main__":
    import random 
    random_state = random.choice(states)
    
    print(f"Random state selected: {random_state}")
    districts = get_school_districts(random_state)
    
    for d in districts:
        print(d)
    
    