import pandas as pd
import os

# --- CONFIGURATION ---
SEASONS = ['23-24', '24-25']
BASE_DIR = os.path.join("data", "raw")
FILE_NAME = "player_minutes.csv"

# --- AGE DEFINITIONS ---
# Defined as (Min_Age, Max_Age) inclusive
AGE_RANGES = {
    "Prospects":  (0, 20),
    "Developing": (21, 23),
    "Prime":      (24, 29),
    "Veterans":   (30, 100)
}

def get_age_group(age):
    for group, (min_a, max_a) in AGE_RANGES.items():
        if min_a <= age <= max_a:
            return group
    return "Unknown"

def format_availability_share(group_df):
    """
    Returns string: "Prospects (25.0%), Prime (50.0%)"
    Calculates the % of HEADCOUNT (Inventory) each age group represents.
    """
    total_players = len(group_df)
    
    if total_players == 0:
        return "No Players"
    
    # 1. Assign Group Names to the slice
    group_df = group_df.copy()
    group_df['Group_Name'] = group_df['Age'].apply(get_age_group)
    
    # 2. Count players per group
    counts = group_df['Group_Name'].value_counts()
    
    # 3. Build String (Ordered)
    segments = []
    order = ["Prospects", "Developing", "Prime", "Veterans"]
    
    for group_name in order:
        count = counts.get(group_name, 0)
        if count > 0:
            pct = (count / total_players) * 100
            segments.append(f"{group_name} ({pct:.1f}%)")
            
    return ", ".join(segments)

def format_minutes_share(group_df):
    """
    Returns string: "Prospects (17.2%), Prime (70.1%)"
    """
    total_pos_minutes = group_df['Min'].sum()
    
    if total_pos_minutes == 0:
        return "No Minutes Played"
    
    # Group by Age Group and sum minutes
    # We map the age to the group name first
    group_df = group_df.copy() # Avoid SettingWithCopy warning
    group_df['Group_Name'] = group_df['Age'].apply(get_age_group)
    
    stats = group_df.groupby('Group_Name')['Min'].sum()
    
    # Build the string in a specific order for consistency
    segments = []
    # We iterate through the specific order to keep the output clean
    order = ["Prospects", "Developing", "Prime", "Veterans"]
    
    for group_name in order:
        minutes = stats.get(group_name, 0)
        if minutes > 0:
            pct = (minutes / total_pos_minutes) * 100
            segments.append(f"{group_name} ({pct:.1f}%)")
            
    return ", ".join(segments)

def apply_squad_filters(df):
    """
    Applies the 'Ghost Cleanse' and 'Active Backup' logic.
    """
    initial_count = len(df)
    
    if 'unSub' not in df.columns: df['unSub'] = 0
    
    df['unSub'] = df['unSub'].fillna(0).astype(int)
    df['MP'] = df['MP'].fillna(0).astype(int)
    df['Min'] = df['Min'].fillna(0).astype(int)

    df['Squad_Apps'] = df['MP'] + df['unSub']

    # Filter Logic
    is_senior = (df['Age'] >= 21) & (df['Squad_Apps'] > 0)
    is_valid_prospect = (df['Age'] < 21) & ( (df['MP'] >= 3) | (df['Squad_Apps'] >= 5) )
    
    keep_mask = is_senior | is_valid_prospect
    df_filtered = df[keep_mask].copy()

    dropped_count = initial_count - len(df_filtered)
    print(f"   >> Filters applied: Dropped {dropped_count} 'Ghost' players. Final Squad Size: {len(df_filtered)}")
    
    return df_filtered

def process_squad_breakdown(file_path):
    if not os.path.exists(file_path):
        print(f"⚠️ File not found: {file_path}")
        return

    print(f"\n📂 Loading: {file_path}")
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return

    required_cols = {'Squad', 'Age', 'Pos', 'MP'}
    if not required_cols.issubset(df.columns):
        print(f"❌ Error: Missing required columns.")
        return

    # --- APPLY FILTERS ---
    df = apply_squad_filters(df)

    # Clean Position
    df['Pos_Clean'] = df['Pos'].astype(str).apply(lambda x: x.split(',')[0].strip())
    squads = sorted(df['Squad'].dropna().unique())

    for squad in squads:
        print(f"\n{'='*10} {squad.upper()} {'='*10}")
        squad_df = df[df['Squad'] == squad]
        
        if squad_df.empty:
            continue

        # --- PREPARE COLUMNS ---
        # 1. Age Counts (Left)
        age_counts = squad_df['Age'].value_counts().sort_index()
        left_lines = [f"Age {age}: {count}" for age, count in age_counts.items()]

        # 2. Position Data (Middle & Right)
        positions = sorted(squad_df['Pos_Clean'].unique())
        mid_lines = []  # Positional Depth
        right_lines = [] # Minutes Share
        
        for pos in positions:
            pos_group = squad_df[squad_df['Pos_Clean'] == pos]
            
            # Format Depth: "CB: 3 A19..."
            depth_str = f"{pos}: {format_availability_share(pos_group)}"
            mid_lines.append(depth_str)
            
            # Format Minutes: "Prospects (10%)..."
            min_str = format_minutes_share(pos_group)
            right_lines.append(min_str)

        # --- PRINT TABLE ---
        max_rows = max(len(left_lines), len(mid_lines))
        
        # Header
        # We adjust width: Age (15) | Depth (35) | Minutes (Rest)
        print(f"{'AGE COUNT':<15} | {'POSITIONAL DEPTH':<40} | {'MINUTES SHARE (By Age Group)'}")
        print("-" * 110)

        for i in range(max_rows):
            l_col = left_lines[i] if i < len(left_lines) else ""
            m_col = mid_lines[i] if i < len(mid_lines) else ""
            r_col = right_lines[i] if i < len(right_lines) else ""
            
            print(f"{l_col:<15} | {m_col:<40} | {r_col}")

# --- EXECUTION ---
if __name__ == "__main__":
    for season in SEASONS:
        full_path = os.path.join(BASE_DIR, season, FILE_NAME)
        print(f"\nProcessing Season: {season}")
        process_squad_breakdown(full_path)