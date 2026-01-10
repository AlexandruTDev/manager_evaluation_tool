import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re
import os
from datetime import datetime

# --- CONFIGURATION ---
DATA_DIRS = ["data/raw/23-24", "data/raw/24-25"]
OUTPUT_FILE = "data/raw/history/club_volatility.csv"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9'
}

def get_club_seed_list():
    """Reads tenure files and returns unique Squad names."""
    clubs = set()
    for d in DATA_DIRS:
        path = os.path.join(d, "manager_tenure.csv")
        if os.path.exists(path):
            df = pd.read_csv(path)
            clubs.update(df['Squad'].unique())
    return sorted(list(clubs))

def get_club_history_url(club_name):
    """Searches TM for the club and constructs the history URL."""
    search_url = f"https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche?query={club_name}"
    
    try:
        response = requests.get(search_url, headers=HEADERS)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Search for the specific club link
        result_row = soup.select_one("table.items tbody tr td.hauptlink a[href*='/startseite/verein/']")
        
        if result_row:
            base_href = result_row['href'] 
            # Replace 'startseite' (overview) with 'mitarbeiterhistorie' (staff history)
            history_href = base_href.replace("startseite", "mitarbeiterhistorie")
            return "https://www.transfermarkt.com" + history_href
            
    except Exception as e:
        print(f"   ⚠️ Search failed for {club_name}: {e}")
    return None

def parse_date(date_str):
    """Parses DD/MM/YYYY to datetime object."""
    try:
        return datetime.strptime(date_str.strip(), "%d/%m/%Y")
    except:
        return None

def scrape_club_history(club_name, url):
    """Parses the history table for a specific club using strict indexing."""
    try:
        response = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 1. Find the specific grid view div by ID
        grid_view = soup.find("div", id="yw1")
        if not grid_view:
            print(f"   ⚠️ Could not find grid view 'yw1' for {club_name}")
            return []

        # 2. Find the main table inside that grid
        table = grid_view.find("table", class_="items")
        if not table:
            return []

        # 3. Find rows
        tbody = table.find("tbody")
        if not tbody:
            return []
            
        rows = tbody.find_all("tr", recursive=False)
        
        history_data = []
        cutoff_date = datetime(2000, 1, 1)
        
        for row in rows:
            # recursive=False is CRITICAL to ignore nested tables
            cols = row.find_all('td', recursive=False)
            
            # HTML Structure:
            # Col 0: Name (Nested table)
            # Col 1: Flag
            # Col 2: Appointed
            # Col 3: Left
            # Col 4: Time in post (Days)
            # Col 5: Matches
            # Col 6: PPG
            
            if len(cols) < 7: continue # Need at least 7 cols for PPG
            
            # --- EXTRACT DATA ---
            
            # 1. Matches (Col 5)
            try:
                matches_text = cols[5].get_text(strip=True)
                matches = int(matches_text)
            except:
                matches = 0
                
            # FILTER: Ignore interims (< 10 matches)
            if matches < 10:
                continue
                
            # 2. Appointed Date (Col 2)
            appointed_text = cols[2].get_text(strip=True)
            appointed_dt = parse_date(appointed_text)
            
            # FILTER: Post-2000
            if not appointed_dt or appointed_dt < cutoff_date:
                continue
                
            # 3. Days in Charge (Col 4)
            days_text = cols[4].get_text(strip=True)
            days_match = re.search(r"(\d+)", days_text)
            days = int(days_match.group(1)) if days_match else 0
            
            # 4. PPG (Col 6) - [NEW ADDITION]
            try:
                ppg_text = cols[6].get_text(strip=True).replace(',', '.')
                ppg = float(ppg_text)
            except:
                ppg = 0.0

            # 5. Manager Name (Col 0 -> .hauptlink)
            name_link = cols[0].select_one(".hauptlink a")
            manager_name = name_link.get_text(strip=True) if name_link else "Unknown"
            
            history_data.append({
                "Club": club_name,
                "Manager": manager_name,
                "Appointed": appointed_text,
                "Matches": matches,
                "Days_In_Charge": days,
                "PPG": ppg  # Added PPG to output
            })
            
        return history_data

    except Exception as e:
        print(f"   ❌ Error scraping {club_name}: {e}")
        return []

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    print("--- 🏟️ CLUB VOLATILITY SCRAPER (WITH PPG) ---")
    
    # 1. Get Seed List
    clubs = get_club_seed_list()
    # clubs = clubs[:5] # Uncomment for testing
    print(f"Found {len(clubs)} clubs to analyze.")
    
    all_history = []
    
    # 2. Process Each Club
    for i, club in enumerate(clubs):
        print(f"[{i+1}/{len(clubs)}] Processing: {club}...")
        
        # A. Find URL
        url = get_club_history_url(club)
        if not url:
            print(f"   ❌ URL not found for {club}")
            continue
            
        # B. Scrape Data
        club_data = scrape_club_history(club, url)
        
        if club_data:
            print(f"   ✅ Found {len(club_data)} managers (post-2000, >10 matches)")
            all_history.extend(club_data)
        else:
            print("   ⚠️ No relevant history found.")
            
        # C. Delay
        time.sleep(random.uniform(2, 4))
        
    # 3. Save to CSV
    if all_history:
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        df_out = pd.DataFrame(all_history)
        df_out.to_csv(OUTPUT_FILE, index=False)
        print(f"\n✅ Success! Saved club history with PPG to {OUTPUT_FILE}")
    else:
        print("\n⚠️ No data extracted.")