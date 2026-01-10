import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re
import os
import numpy as np
# No 'json' import needed, using native str() for clean CSV output

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
            # Filter for established managers (>10 matches)
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
    try:
        target_th = soup.find("th", string=re.compile(label_pattern, re.IGNORECASE))
        if target_th:
            td = target_th.find_next_sibling("td")
            if td:
                return td.get_text(strip=True)
    except:
        pass
    return np.nan

def scrape_trophies_detailed(profile_url):
    """
    Scrapes trophies by anchoring on '.erfolg_table_saison'.
    Returns: (Count, Python_String_List)
    """
    try:
        success_url = profile_url.replace("/profil/", "/erfolge/")
        response = requests.get(success_url, headers=HEADERS)
        if response.status_code != 200: return 0, "[]"
        
        soup = BeautifulSoup(response.content, 'html.parser')
        boxes = soup.select("div.box")
        
        trophy_list = []
        total_trophies = 0
        
        for box in boxes:
            # 1. Validation: Must have a success image to be a trophy box
            if not box.select_one(".erfolg_bild_box"):
                continue
                
            # 2. Extract Name & Count from Header
            header = box.select_one(".content-box-headline")
            if not header: continue
            
            header_text = header.get_text(strip=True)
            
            count = 1
            name = header_text
            
            # Regex for "2x Title" vs "1x Title"
            match = re.search(r"^(\d+)x\s+(.*)", header_text)
            if match:
                count = int(match.group(1))
                name = match.group(2)
            else:
                match_1x = re.search(r"^1x\s+(.*)", header_text)
                if match_1x:
                    name = match_1x.group(1)

            total_trophies += count
            
            # 3. Extract Details (The Fix)
            # Instead of looking for tables/classes, find the Season Cells directly
            wins = []
            
            # Find all cells with class 'erfolg_table_saison' inside this box
            season_cells = box.select(".erfolg_table_saison")
            
            for cell in season_cells:
                # 3a. Get Season
                season = cell.get_text(strip=True)
                
                # 3b. Get Club (It's in the same row)
                parent_row = cell.find_parent("tr")
                if parent_row:
                    cols = parent_row.find_all("td")
                    # Club is usually the last column
                    if cols:
                        club = cols[-1].get_text(strip=True)
                        wins.append({"season": season, "club": club})
            
            trophy_list.append({
                "name": name,
                "count": count,
                "wins": wins
            })
            
        # Return as simple string representation (Single Quotes)
        # e.g., "[{'name': 'Title', ...}]"
        return total_trophies, str(trophy_list)

    except Exception as e:
        print(f"Error scraping trophies: {e}")
        return 0, "[]"

def parse_career_history(soup):
    total_matches = 0
    weighted_points = 0
    
    # Target history grid by ID (yw2 usually)
    history_grid = soup.find("div", id="yw2")
    if not history_grid: return 0, 0.0
    
    table = history_grid.find("table", class_="items")
    if not table: return 0, 0.0
    
    rows = table.select("tbody tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 6: continue
        
        # Extract Club & Role
        cell_strings = list(cols[1].stripped_strings)
        if len(cell_strings) < 2: continue
        
        club_name = cell_strings[0]
        role_name = cell_strings[-1]
        
        # Filters
        if any(x in club_name for x in ["U23", "U21", "U19", "U18", "Youth", "Reserve", "Primavera"]): continue
        if role_name != "Manager": continue
        
        # Stats
        try:
            matches_text = cols[4].get_text(strip=True)
            ppg_text = cols[5].get_text(strip=True).replace(',', '.')
            
            if matches_text.replace('.', '').isdigit(): matches = int(float(matches_text))
            else: matches = 0
            
            if ppg_text.replace('.', '', 1).isdigit(): ppg = float(ppg_text)
            else: ppg = 0.0
            
            if matches > 0:
                total_matches += matches
                weighted_points += (matches * ppg)
        except: continue
            
    career_ppg = round(weighted_points / total_matches, 2) if total_matches > 0 else 0.0
    return total_matches, career_ppg

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
            "Career_PPG": 0.0,
            "Trophies_Total": 0,
            "Trophies_JSON": "[]"
        }
        
        # Bio
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
        
        # Stats
        matches, ppg = parse_career_history(soup)
        data["Total_Matches"] = matches
        data["Career_PPG"] = ppg

        # Trophies
        time.sleep(1) # Be polite
        count, details_str = scrape_trophies_detailed(url)
        data["Trophies_Total"] = count
        data["Trophies_JSON"] = details_str

        return data

    except Exception as e:
        print(f"   ❌ Error scraping {manager_name}: {e}")
        return None

if __name__ == "__main__":
    print("--- 🕵️ MANAGER VOLATILITY & TROPHIES SCRAPER (v9 FIXED) ---")
    managers = get_manager_seed_list()
    # managers = managers[:5] # Comment out for full run
    
    results = []
    for i, name in enumerate(managers):
        print(f"[{i+1}/{len(managers)}] Processing: {name}...")
        url = get_transfermarkt_url(name)
        if url:
            profile = scrape_manager_profile(name, url)
            if profile:
                print(f"   ✅ {name}: {profile['Total_Matches']} Matches | {profile['Trophies_Total']} Trophies")
                results.append(profile)
        time.sleep(random.uniform(2, 4))
        
    if results:
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        pd.DataFrame(results).to_csv(OUTPUT_FILE, index=False)
        print(f"\n✅ Success! Saved detailed profiles to {OUTPUT_FILE}")