import pandas as pd
import os

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
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
        return df
    except Exception as e:
        print(f"Error loading data file: {e}")
        return None

def load_manager_map(path):
    """
    Loads manager names using a broad lookup strategy.
    Returns: { 'Any_Team_Name_Variant': 'Manager Name' }
    """
    if not os.path.exists(path):
        return {}
    try:
        df = pd.read_csv(path)
        manager_map = {}
        
        # We map EVERY name variant to the manager
        if 'Manager' in df.columns:
            for col in ['Common_Name', 'FBref_Name', 'TM_Name']:
                if col in df.columns:
                    # Create dictionary: {Variant: Manager}
                    # dropna() ensures we don't map NaNs
                    subset = df.dropna(subset=[col, 'Manager'])
                    manager_map.update(dict(zip(subset[col], subset['Manager'])))
                    
        return manager_map
    except Exception as e:
        print(f"Error loading manager map: {e}")
        return {}

def load_team_mapping(path):
    """
    Creates a robust Master Map.
    Input: Any known name variant (FBref, TM, Common).
    Output: The standardized 'Common_Name' used in the Matrix.
    """
    if not os.path.exists(path):
        return {}
    try:
        df = pd.read_csv(path)
        master_map = {}
        
        # Ensure we have the target column
        if 'Common_Name' not in df.columns:
            return {}

        # Loop through rows and map ALL variants to the Common_Name
        for _, row in df.iterrows():
            target_name = row['Common_Name']
            
            # Map the Common Name to itself (Identity)
            master_map[target_name] = target_name
            
            # Map FBref Name -> Common Name
            if 'FBref_Name' in df.columns and pd.notna(row['FBref_Name']):
                master_map[row['FBref_Name']] = target_name
                
            # Map TM Name -> Common Name
            if 'TM_Name' in df.columns and pd.notna(row['TM_Name']):
                master_map[row['TM_Name']] = target_name

        return master_map
    except Exception as e:
        print(f"Error loading team mapping: {e}")
        return {}

# --- CORE LOGIC ---
def get_age_group(age):
    for group, (min_a, max_a) in AGE_RANGES.items():
        if min_a <= age <= max_a:
            return group
    return "Unknown"

def apply_squad_filters(df):
    """
    Applies the 'Ghost Cleanse' and 'Active Backup' logic.
    Returns the clean DataFrame.
    """
    # 1. Standardize Columns
    if 'unSub' not in df.columns: df['unSub'] = 0
    df['unSub'] = df['unSub'].fillna(0).astype(int)
    df['MP'] = df['MP'].fillna(0).astype(int)
    df['Min'] = df['Min'].fillna(0).astype(int)

    # 2. Calculate Total Squad Inclusions
    df['Squad_Apps'] = df['MP'] + df['unSub']

    # 3. Filter Logic
    # Senior (>21): Keep if they made the squad at least once
    is_senior = (df['Age'] >= 21) & (df['Squad_Apps'] > 0)
    
    # Prospect (<21): Keep if Played >= 3 OR Bench >= 5
    is_valid_prospect = (df['Age'] < 21) & ( (df['MP'] >= 3) | (df['Squad_Apps'] >= 5) )
    
    keep_mask = is_senior | is_valid_prospect
    return df[keep_mask].copy()

def calculate_trust_metrics(df):
    """
    Calculates Inventory % vs Minutes % for each Age Group.
    Returns a dataframe ready for plotting.
    """
    total_players = len(df)
    total_minutes = df['Min'].sum()
    
    data = []
    
    # Assign Age Groups if not already present
    if 'Age_Group' not in df.columns:
        df['Age_Group'] = df['Age'].apply(get_age_group)

    grouped = df.groupby('Age_Group')
    
    for group in ORDERED_GROUPS:
        if group in grouped.groups:
            group_df = grouped.get_group(group)
            count = len(group_df)
            minutes = group_df['Min'].sum()
        else:
            count = 0
            minutes = 0
            
        inv_pct = (count / total_players * 100) if total_players > 0 else 0
        min_pct = (minutes / total_minutes * 100) if total_minutes > 0 else 0
        
        data.append({
            "Age Group": group, 
            "Metric": "Squad Depth (Available Players)", 
            "Percentage": inv_pct, 
            "Raw Value": count
        })
        data.append({
            "Age Group": group, 
            "Metric": "Minutes Played (Players Utilization)", 
            "Percentage": min_pct, 
            "Raw Value": minutes
        })
        
    return pd.DataFrame(data)