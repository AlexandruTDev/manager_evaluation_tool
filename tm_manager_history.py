import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re
import os
import numpy as np # For NaN values

# --- CONFIGURATION ---
DATA_DIRS = ["data/raw/23-24", "data/raw/24-25"]
OUTPUT_FILE = "data/raw/history/manager_volatility.csv"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9'
}

def get_manager_seed_list():
    """Reads tenure files and returns unique managers with > 10 matches."""
    managers = set()
    for d in DATA_DIRS:
        path = os.path.join(d, "manager_tenure.csv")
        if os.path.exists(path):
            df = pd.read_csv(path)
            # FILTER: Exclude interims (Matches > 10)
            qualified = df[df['Matches'] > 10]['Manager'].unique()
            managers.update(qualified)
    return sorted(list(managers))

def get_transfermarkt_url(manager_name):
    """Searches Transfermarkt for the manager and returns their profile URL."""
    search_url = f"https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche?query={manager_name}"
    try:
        response = requests.get(search_url, headers=HEADERS)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find the first result in the "Managers" section
        results = soup.select("table.items tbody tr")
        for row in results:
            link = row.select_one("a[href*='/profil/trainer/']")
            if link:
                return "https://www.transfermarkt.com" + link['href']
    except Exception as e:
        print(f"   ⚠️ Search failed for {manager_name}: {e}")
    return None

def get_profile_value(soup, label_pattern):
    """Helper to find a th with regex pattern and return the next td text."""
    try:
        # Find th containing the label
        target_th = soup.find("th", string=re.compile(label_pattern, re.IGNORECASE))
        if target_th:
            td = target_th.find_next_sibling("td")
            if td:
                return td.get_text(strip=True)
    except:
        pass
    return np.nan

def scrape_manager_profile(manager_name, url):
    """Extracts bio-data fields from the profile page."""
    try:
        response = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        data = {
            "Manager": manager_name,
            "Age": np.nan,
            "Avg_Tenure_Years": np.nan,
            "Coaching_Licence": np.nan,
            "Agent": np.nan,
            "Contract_Until": np.nan
        }
        
        # 1. Age (Label: "Date of birth/Age")
        raw_age = get_profile_value(soup, r"Date of birth/Age")
        if raw_age and isinstance(raw_age, str):
            # Extract number in parentheses: "27/01/1985 (40)" -> 40
            match = re.search(r"\((\d+)\)", raw_age)
            if match:
                data["Age"] = int(match.group(1))
            else:
                data["Age"] = raw_age # Fallback to full string if format differs
        
        # 2. Avg Tenure (Label: "Avg. term as coach")
        raw_tenure = get_profile_value(soup, r"Avg\. term as coach")
        if raw_tenure and isinstance(raw_tenure, str):
            match = re.search(r"([\d\.]+)", raw_tenure)
            if match:
                data["Avg_Tenure_Years"] = float(match.group(1))

        # 3. Coaching Licence (Label: "Coaching Licence")
        data["Coaching_Licence"] = get_profile_value(soup, r"Coaching Licence")

        # 4. Agent (Label: "Agent")
        data["Agent"] = get_profile_value(soup, r"Agent")

        # 5. Contract Until (Label: "Contract until")
        data["Contract_Until"] = get_profile_value(soup, r"Contract until")

        return data

    except Exception as e:
        print(f"   ❌ Error scraping {manager_name}: {e}")
        return None

# --- MAIN PIPELINE ---
if __name__ == "__main__":
    print("--- 🕵️ MANAGER BIO DATA SCRAPER ---")
    
    # 1. Get Seed List
    managers = get_manager_seed_list()
    print(f"Found {len(managers)} managers to scrape.")
    
    results = []
    
    # 2. Process Each Manager
    for i, name in enumerate(managers):
        print(f"[{i+1}/{len(managers)}] Processing: {name}...")
        
        # A. Find URL
        url = get_transfermarkt_url(name)
        if not url:
            print(f"   ❌ URL not found for {name}")
            continue
            
        # B. Scrape Data
        profile_data = scrape_manager_profile(name, url)
        
        if profile_data:
            print(f"   ✅ Scraped: Age={profile_data['Age']}, Tenure={profile_data['Avg_Tenure_Years']}y")
            results.append(profile_data)
        
        # C. Delay
        time.sleep(random.uniform(2, 4))
        
    # 3. Save
    if results:
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        df_out = pd.DataFrame(results)
        df_out.to_csv(OUTPUT_FILE, index=False)
        print(f"\n✅ Success! Saved {len(results)} profiles to {OUTPUT_FILE}")
    else:
        print("\n⚠️ No data extracted.")