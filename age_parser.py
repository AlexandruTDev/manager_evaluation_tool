import pandas as pd
import os
from datetime import datetime

# --- CONSTANTS ---
AGE_RANGES = {
    "Prospects":  (0, 20),
    "Developing": (21, 23),
    "Prime":      (24, 29),
    "Veterans":   (30, 100)
}
ORDERED_GROUPS = ["Prospects", "Developing", "Prime", "Veterans"]

# --- DATA LOADING ---
def load_data(path):
    if not os.path.exists(path): return None
    try:
        return pd.read_csv(path)
    except: return None

def load_manager_map(path):
    if not os.path.exists(path): return {}
    try:
        df = pd.read_csv(path)
        manager_map = {}
        if 'Manager' in df.columns:
            for col in ['Common_Name', 'FBref_Name', 'TM_Name']:
                if col in df.columns:
                    subset = df.dropna(subset=[col, 'Manager'])
                    manager_map.update(dict(zip(subset[col], subset['Manager'])))
        return manager_map
    except: return {}

def load_team_mapping(path):
    if not os.path.exists(path): return {}
    try:
        df = pd.read_csv(path)
        master_map = {}
        if 'Common_Name' not in df.columns: return {}
        for _, row in df.iterrows():
            target_name = row['Common_Name']
            master_map[target_name] = target_name
            if 'FBref_Name' in df.columns and pd.notna(row['FBref_Name']):
                master_map[row['FBref_Name']] = target_name
            if 'TM_Name' in df.columns and pd.notna(row['TM_Name']):
                master_map[row['TM_Name']] = target_name
        return master_map
    except: return {}

def load_manager_tenure(path):
    if not os.path.exists(path): return pd.DataFrame()
    try: return pd.read_csv(path)
    except: return pd.DataFrame()

# --- CORE LOGIC ---
def get_age_group(age):
    for group, (min_a, max_a) in AGE_RANGES.items():
        if min_a <= age <= max_a: return group
    return "Unknown"

def apply_squad_filters(df):
    if 'unSub' not in df.columns: df['unSub'] = 0
    df['unSub'] = df['unSub'].fillna(0).astype(int)
    df['MP'] = df['MP'].fillna(0).astype(int)
    df['Min'] = df['Min'].fillna(0).astype(int)
    df['Squad_Apps'] = df['MP'] + df['unSub']
    is_senior = (df['Age'] >= 21) & (df['Squad_Apps'] > 0)
    is_valid_prospect = (df['Age'] < 21) & ( (df['MP'] >= 3) | (df['Squad_Apps'] >= 5) )
    return df[is_senior | is_valid_prospect].copy()

def calculate_trust_metrics(df):
    total_players = len(df)
    total_minutes = df['Min'].sum()
    data = []
    if 'Age_Group' not in df.columns: df['Age_Group'] = df['Age'].apply(get_age_group)
    grouped = df.groupby('Age_Group')
    for group in ORDERED_GROUPS:
        if group in grouped.groups:
            group_df = grouped.get_group(group)
            count = len(group_df)
            minutes = group_df['Min'].sum()
        else: count, minutes = 0, 0
        inv_pct = (count / total_players * 100) if total_players > 0 else 0
        min_pct = (minutes / total_minutes * 100) if total_minutes > 0 else 0
        data.append({"Age Group": group, "Metric": "Squad Depth (Available Players)", "Percentage": inv_pct})
        data.append({"Age Group": group, "Metric": "Minutes Played (Players Utilization)", "Percentage": min_pct})
    return pd.DataFrame(data)

def get_active_managers(tenure_df, squad_name, season_str, match_threshold_pct=0.25):
    """
    Returns list of managers filtered by threshold with calculated percentages.
    Now dynamic based on the selected season string (e.g., "24-25").
    """
    if tenure_df.empty: return []

    # 1. Parse Season Year dynamically
    # Expecting format like "24-25" -> Start Year 2024
    try:
        start_short = season_str.split('-')[0] # "24"
        season_start_year = int("20" + start_short) # 2024
        season_end_year = season_start_year + 1     # 2025
    except:
        # Fallback if folder naming is weird
        season_start_year = datetime.now().year - 1
        season_end_year = datetime.now().year

    # Filter for squad
    squad_data = tenure_df[tenure_df['Squad'] == squad_name].copy()
    if squad_data.empty: return []

    total_matches = squad_data['Matches'].sum()
    if total_matches == 0: return []

    results = []
    
    def parse_date(d_str):
        if str(d_str).lower() == "present": return datetime.now()
        try: return datetime.strptime(str(d_str), "%d/%m/%Y")
        except: return datetime.now()

    for _, row in squad_data.iterrows():
        matches = row['Matches']
        share = matches / total_matches
        
        # Threshold Filter
        if share < match_threshold_pct: continue

        # Stats
        w_pct = (row['W'] / matches * 100) if matches > 0 else 0
        d_pct = (row['D'] / matches * 100) if matches > 0 else 0
        l_pct = (row['L'] / matches * 100) if matches > 0 else 0
        
        start_date = parse_date(row['Start_Date'])
        
        # --- DYNAMIC PHASE LOGIC ---
        # 1. Full Season: Managed > 80% of games
        if share >= 0.80: 
            phase = "Full Season"
            
        # 2. Early Season: Hired Aug/Sep/Oct/Nov of the START year (e.g., Aug 2024)
        elif start_date.year == season_start_year and start_date.month in [8, 9, 10, 11]:
            phase = "Early Season"
            
        # 3. Mid-Season: Hired Dec (Start Year) OR Jan/Feb (End Year)
        elif (start_date.year == season_start_year and start_date.month == 12) or \
             (start_date.year == season_end_year and start_date.month in [1, 2]):
            phase = "Mid-Season Takeover"
            
        # 4. Late Season: Hired Mar/Apr/May of the END year
        elif start_date.year == season_end_year and start_date.month in [3, 4, 5]:
            phase = "Late Season Rescue"
            
        # 5. Season Starter: Hired BEFORE August of the start year (e.g., July 2024 or earlier)
        # This catches managers hired in summer or carried over from previous seasons
        else:
            phase = "Season Starter"

        results.append({
            "Manager": row['Manager'],
            "Matches": matches,
            "Share": share * 100,
            "W_Pct": w_pct,
            "D_Pct": d_pct,
            "L_Pct": l_pct,
            "PPM": row['PPM'],
            "Phase": phase,
            "Dates": f"{row['Start_Date']} - {row['End_Date']}",
            "Start_Obj": start_date
        })
            
    results.sort(key=lambda x: x['Start_Obj'])
    return results