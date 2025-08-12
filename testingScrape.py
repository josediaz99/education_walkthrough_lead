import os
import asyncio
import requests
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()
OLLAMA_URL = os.getenv("OLLAMA_URL")
MODEL_NAME = os.getenv("MODEL_NAME")

def ask_ollama(prompt):
    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        headers={"Content-Type": "application/json"},
        json={
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False
        }
    )
    return response.json()["response"]

async def scrape_with_agent():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        search_url = "https://www.maywood89.org/"
        await page.goto(search_url)

        print("Page title:", await page.title())
        content = await page.content()
        print("Page content snippet:", content[:500])

        # Ask the LLM what to do next based on the page content
        llm_response = ask_ollama(f"I see this page content:\n\n{content}\n\nWhat link should I click to find board meeting minutes?")
        print("\n[LLM Suggestion]:", llm_response)

        await browser.close()

asyncio.run(scrape_with_agent())
