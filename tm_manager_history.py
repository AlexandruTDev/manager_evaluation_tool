import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re
import os
import numpy as np

# --- CONFIGURATION ---
DATA_DIRS = ["data/raw/23-24", "data/raw/24-25"]
OUTPUT_FILE = "data/raw/history/manager_volatility.csv"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9'
}

def get_manager_seed_list():
    managers = set()
    for d in DATA_DIRS:
        path = os.path.join(d, "manager_tenure.csv")
        if os.path.exists(path):
            df = pd.read_csv(path)
            qualified = df[df['Matches'] > 10]['Manager'].unique()
            managers.update(qualified)
    return sorted(list(managers))

def get_transfermarkt_url(manager_name):
    search_url = f"https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche?query={manager_name}"
    try:
        response = requests.get(search_url, headers=HEADERS)
        soup = BeautifulSoup(response.content, 'html.parser')
        results = soup.select("table.items tbody tr")
        for row in results:
            link = row.select_one("a[href*='/profil/trainer/']")
            if link:
                return "https://www.transfermarkt.com" + link['href']
    except Exception as e:
        print(f"   ⚠️ Search failed for {manager_name}: {e}")
    return None

def get_profile_value(soup, label_pattern):
    """Extracts Bio Data from the 'Personal Details' box."""
    try:
        # Based on your HTML: <table class="auflistung"> ... <th>Label</th> <td>Value</td>
        target_th = soup.find("th", string=re.compile(label_pattern, re.IGNORECASE))
        if target_th:
            td = target_th.find_next_sibling("td")
            if td:
                return td.get_text(strip=True)
    except:
        pass
    return np.nan

def parse_career_history(soup):
    """
    Parses the history table (id='yw2').
    - Separates 'Club' and 'Role' using stripped_strings.
    - Strict 'Manager' role check.
    - Excludes U23/Youth teams.
    """
    total_matches = 0
    weighted_points = 0
    
    # [FIX] Target the specific history grid by ID from your HTML
    history_grid = soup.find("div", id="yw2")
    if not history_grid:
        return 0, 0.0

    table = history_grid.find("table", class_="items")
    if not table:
        return 0, 0.0

    # Iterate through rows in tbody
    rows = table.select("tbody tr")
    
    for row in rows:
        cols = row.find_all("td")
        
        # [FIX] Ignore 'colspan' rows (e.g. "Assistant Manager of...")
        # Your HTML shows these have fewer columns or a colspan attribute
        if len(cols) < 6: 
            continue

        # --- COLUMN 1: Club & Role ---
        # The HTML is: <td class="hauptlink"> <a...>Club</a> <br> Role </td>
        # .stripped_strings yields a generator: ["Chelsea", "Manager"]
        cell_strings = list(cols[1].stripped_strings)
        
        if len(cell_strings) < 2:
            continue # Needs at least Club and Role

        club_name = cell_strings[0] # e.g., "Chelsea"
        role_name = cell_strings[-1] # e.g., "Manager" (taking the last element is safest)

        # --- FILTER 1: SENIOR CLUBS ONLY ---
        # Maresca had "Man City U23". We exclude this.
        if any(x in club_name for x in ["U23", "U21", "U19", "U18", "Youth", "Reserve", "Primavera"]):
            continue

        # --- FILTER 2: STRICT MANAGER ROLE ---
        # Must be exactly "Manager". 
        # This excludes "Assistant Manager", "Technical Coach", etc.
        if role_name != "Manager":
            continue

        # --- EXTRACT DATA ---
        try:
            # Based on your HTML structure:
            # Col 4 (Index 4): Matches (e.g. "92")
            # Col 5 (Index 5): PPM (e.g. "1.97")
            
            matches_text = cols[4].get_text(strip=True)
            ppm_text = cols[5].get_text(strip=True).replace(',', '.')
            
            # Clean matches (remove non-digits if any)
            if matches_text.replace('.', '').isdigit():
                matches = int(float(matches_text))
            else:
                matches = 0
                
            # Clean PPM
            if ppm_text.replace('.', '', 1).isdigit():
                ppm = float(ppm_text)
            else:
                ppm = 0.0
            
            if matches > 0:
                total_matches += matches
                weighted_points += (matches * ppm)
                
        except Exception:
            continue
            
    career_ppm = round(weighted_points / total_matches, 2) if total_matches > 0 else 0.0
    return total_matches, career_ppm

def scrape_manager_profile(manager_name, url):
    try:
        response = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        data = {
            "Manager": manager_name,
            "Age": np.nan,
            "Avg_Tenure_Years": np.nan,
            "Coaching_Licence": np.nan,
            "Agent": np.nan,
            "Contract_Until": np.nan,
            "Total_Matches": 0,
            "Career_PPM": 0.0
        }
        
        # 1. Header Bio Data (Personal Details Box)
        raw_age = get_profile_value(soup, r"Date of birth/Age")
        if raw_age:
            match = re.search(r"\((\d+)\)", str(raw_age))
            data["Age"] = int(match.group(1)) if match else raw_age
        
        raw_tenure = get_profile_value(soup, r"Avg\. term as coach")
        if raw_tenure:
            match = re.search(r"([\d\.]+)", str(raw_tenure))
            if match:
                data["Avg_Tenure_Years"] = float(match.group(1))

        data["Coaching_Licence"] = get_profile_value(soup, r"Coaching Licence")
        data["Agent"] = get_profile_value(soup, r"Agent")
        data["Contract_Until"] = get_profile_value(soup, r"Contract until")
        
        # 2. Career History (Using ID yw2)
        matches, ppm = parse_career_history(soup)
        data["Total_Matches"] = matches
        data["Career_PPM"] = ppm

        return data

    except Exception as e:
        print(f"   ❌ Error scraping {manager_name}: {e}")
        return None

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    print("--- 🕵️ MANAGER VOLATILITY SCRAPER (V6 - HTML ALIGNED) ---")
    managers = get_manager_seed_list()
    # managers = managers[:5] # Test Mode
    
    results = []
    for i, name in enumerate(managers):
        print(f"[{i+1}/{len(managers)}] Processing: {name}...")
        url = get_transfermarkt_url(name)
        if url:
            profile = scrape_manager_profile(name, url)
            if profile:
                print(f"   ✅ {name}: {profile['Total_Matches']} Matches | {profile['Career_PPM']} PPM")
                results.append(profile)
        time.sleep(random.uniform(2, 4))
        
    if results:
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        df_out = pd.DataFrame(results)
        df_out.to_csv(OUTPUT_FILE, index=False)
        print(f"\n✅ Success! Saved HTML-aligned profiles to {OUTPUT_FILE}")
    else:
        print("\n⚠️ No data extracted.")