import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import time
import re

# --- CONFIGURATION ---
SEASON_YEAR = "2024"
OUTPUT_DIR = os.path.join("data", "raw", "24-25")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "manager_tenure.csv")

# SET TO NONE TO SCRAPE ALL TEAMS
# SET TO INT (e.g., 3) TO TEST WITH FIRST N TEAMS
TEST_LIMIT = None 

# Manual Map of Transfermarkt Club IDs for PL
# Season 2024-25
TM_IDS = {
    "Leicester": 1003,
    "Southampton": 180,
    "Arsenal": 11,
    "Aston Villa": 405,
    "Bournemouth": 989,
    "Brentford": 1148,
    "Brighton": 1237,
    "Chelsea": 631,
    "Crystal Palace": 873,
    "Everton": 29,
    "Fulham": 931,
    "Ipswich": 677,       
    "Liverpool": 31,
    "Man City": 281,
    "Man Utd": 985,
    "Newcastle": 762,
    "Nottm Forest": 703,
    "Tottenham": 148,
    "West Ham": 379,
    "Wolves": 543
}

# Season 2023-24
"""TM_IDS = {
    "Arsenal": 11,
    "Aston Villa": 405,
    "Bournemouth": 989,
    "Brentford": 1148,
    "Brighton": 1237,
    "Burnley": 1132,      # Relegated
    "Chelsea": 631,
    "Crystal Palace": 873,
    "Everton": 29,
    "Fulham": 931,
    "Liverpool": 31,
    "Luton Town": 1031,   # Relegated
    "Man City": 281,
    "Man Utd": 985,
    "Newcastle": 762,
    "Nottm Forest": 703,
    "Sheffield Utd": 350, # Relegated
    "Tottenham": 148,
    "West Ham": 379,
    "Wolves": 543
}"""

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def parse_manager_row(li_element, squad_name):
    """
    Parses a single <li> element from the manager list.
    """
    try:
        # 1. Manager Name
        name_tag = li_element.select_one(".container-main a")
        manager_name = name_tag.text.strip() if name_tag else "Unknown"

        # 2. Tenure (Date)
        tenure_div = li_element.select_one(".container-tenure")
        if tenure_div:
            tenure_text = re.sub(r'\s+', ' ', tenure_div.text).strip()
            dates = re.findall(r'\d{2}/\d{2}/\d{4}', tenure_text)
            start_date = dates[0] if len(dates) > 0 else "Unknown"
            end_date = dates[1] if len(dates) > 1 else "Present"
        else:
            start_date, end_date = "Unknown", "Unknown"

        # 3. Stats (Matches, W, D, L, PPM)
        table = li_element.select_one("table.table-border")
        matches = 0
        w = 0
        d = 0
        l = 0
        ppm = 0.0
        
        if table:
            rows = table.find_all("tr")
            if len(rows) >= 2:
                cols = rows[1].find_all("td")
                if len(cols) >= 5:
                    # Helper to safely extract int
                    def get_int(idx):
                        txt = cols[idx].get_text(strip=True)
                        return int(txt) if txt.isdigit() else 0
                    
                    matches = get_int(0)
                    w = get_int(1) # Wins
                    d = get_int(2) # Draws
                    l = get_int(3) # Losses
                    
                    # PPM
                    ppm_text = cols[4].get_text(strip=True)
                    try:
                        ppm = float(ppm_text)
                    except ValueError:
                        ppm = 0.0

        return {
            "Squad": squad_name,
            "Manager": manager_name,
            "Start_Date": start_date,
            "End_Date": end_date,
            "Matches": matches,
            "W": w,
            "D": d,
            "L": l,
            "PPM": ppm
        }

    except Exception as e:
        print(f"    [ERROR] Parsing failed for a row in {squad_name}: {e}")
        return None

def main():
    if not os.path.exists(OUTPUT_DIR):
        print(f"[SETUP] Creating directory: {OUTPUT_DIR}")
        os.makedirs(OUTPUT_DIR)
        
    all_managers = []

    print(f"\n{'='*60}")
    print(f"[START] Scraping Manager Tenure for Season {SEASON_YEAR}")
    if TEST_LIMIT:
        print(f"[TEST MODE] Limiting to first {TEST_LIMIT} teams only.")
    print(f"{'='*60}\n")

    # Apply Limiter Logic
    items_to_scrape = list(TM_IDS.items())
    if TEST_LIMIT:
        items_to_scrape = items_to_scrape[:TEST_LIMIT]

    for squad_name, tm_id in items_to_scrape:
        slug = squad_name.lower().replace(" ", "-")
        url = f"https://www.transfermarkt.com/{slug}/startseite/verein/{tm_id}/saison_id/{SEASON_YEAR}"

        print(f"[FETCH] {squad_name}")
        print(f"        URL: {url}")
        
        try:
            response = requests.get(url, headers=HEADERS)
            if response.status_code != 200:
                print(f"        [ERROR] Failed HTTP {response.status_code}")
                continue
                
            soup = BeautifulSoup(response.content, "html.parser")
            manager_list = soup.select("ul.list-spacing li.list")
            
            if not manager_list:
                print("        [WARNING] No manager list found in HTML.")
                continue
                
            print(f"        [PARSING] Found {len(manager_list)} entries. Extracting data...")
            
            count_for_squad = 0
            for li in manager_list:
                mgr_data = parse_manager_row(li, squad_name)
                if mgr_data:
                    print(f"          -> Found: {mgr_data['Manager']:<20} | Matches: {mgr_data['Matches']:<3} | Dates: {mgr_data['Start_Date']} - {mgr_data['End_Date']}")
                    all_managers.append(mgr_data)
                    count_for_squad += 1
            
            if count_for_squad == 0:
                 print("        [WARNING] HTML elements found but no valid data extracted.")
            
            # Politeness delay
            time.sleep(1)
            print("-" * 60)
            
        except Exception as e:
            print(f"        [CRITICAL ERROR] {e}")

    # Save to CSV
    print(f"\n[SUMMARY] Scraping finished.")
    if all_managers:
        df = pd.DataFrame(all_managers)
        df.to_csv(OUTPUT_FILE, index=False)
        print(f"[SUCCESS] Saved {len(df)} rows to: {OUTPUT_FILE}")
        print(f"[PREVIEW]\n{df.head(10)}")
    else:
        print("[FAILURE] No data extracted from any URL.")

if __name__ == "__main__":
    main()