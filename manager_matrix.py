import pandas as pd
import os
import re

# --- LABELS ---
LABEL_Q1, LABEL_Q2 = "Value Multiplier", "Asset Developer"
LABEL_Q3, LABEL_Q4 = "Results Specialist", "Performance Deficit"

def clean_wage(x):
    if pd.isna(x): return 0.0
    m = re.search(r'€\s*([\d,]+)', str(x))
    return float(m.group(1).replace(',', '')) if m else 0.0

def clean_estimated(x):
    if pd.isna(x): return 0.0
    return float(str(x).replace('%', '')) / 100.0

def clean_deduction(x):
    if pd.isna(x): return 0
    m = re.search(r'(\d+)-point deduction', str(x))
    return int(m.group(1)) if m else 0

def get_quadrant(row):
    x, y = row['Fair_Index'], row['Organic_Growth']
    if pd.isna(x) or pd.isna(y): return "Unknown"
    # Q1: High Efficiency, High Growth (Green)
    if x >= 0 and y >= 0: return LABEL_Q1
    # Q2: Low Efficiency, High Growth (Blue)
    if x < 0 and y >= 0: return LABEL_Q2
    # Q3: High Efficiency, Negative Growth (Orange)
    if x >= 0 and y < 0: return LABEL_Q3
    # Q4: Low Efficiency, Negative Growth (Red)
    return LABEL_Q4

def load_matrix_data(season_dir):
    # ... [Same loading logic as before] ...
    # Define Paths
    files = {
        'wages': os.path.join(season_dir, 'wages.csv'),
        'league': os.path.join(season_dir, 'league_table.csv'),
        'market': os.path.join(season_dir, 'market_value.csv'),
        'income': os.path.join(season_dir, 'income_expenditure.csv'),
        'mapping': os.path.join(season_dir, 'team_name.csv')
    }

    for name, path in files.items():
        if not os.path.exists(path):
            return None

    wages_df = pd.read_csv(files['wages'])
    league_df = pd.read_csv(files['league'])
    market_df = pd.read_csv(files['market'])
    income_df = pd.read_csv(files['income'])
    map_df = pd.read_csv(files['mapping'])

    fbref_to_common = dict(zip(map_df['FBref_Name'], map_df['Common_Name']))
    tm_to_common = dict(zip(map_df['TM_Name'], map_df['Common_Name']))
    common_to_mgr = dict(zip(map_df['Common_Name'], map_df['Manager']))

    # X-Axis Processing
    wages_df['Estimated_Pct'] = wages_df['Estimated'].apply(clean_estimated)
    # FLAG: Low Confidence if > 50% wages are estimated
    wages_df['Is_Low_Confidence'] = wages_df['Estimated_Pct'] > 0.5
    
    wages_df['Squad_Common'] = wages_df['Squad'].map(fbref_to_common)
    wages_df['Wage_Rank'] = wages_df['Annual Wages'].apply(clean_wage).rank(ascending=False, method='min')

    league_df['Squad_Common'] = league_df['Squad'].map(fbref_to_common)
    league_df['Adjusted_Pts'] = league_df['Pts'] + league_df['Notes'].apply(clean_deduction)
    league_df['Adjusted_League_Rank'] = league_df['Adjusted_Pts'].rank(ascending=False, method='min')

    perf_df = pd.merge(league_df[['Squad_Common', 'Adjusted_League_Rank']], 
                       wages_df[['Squad_Common', 'Wage_Rank', 'Is_Low_Confidence']], 
                       on='Squad_Common', how='left')
    perf_df['Fair_Index'] = perf_df['Wage_Rank'] - perf_df['Adjusted_League_Rank']

    # Y-Axis Processing
    market_df['Squad_Common'] = market_df['Club'].map(tm_to_common)
    income_df['Squad_Common'] = income_df['Club'].map(tm_to_common)
    
    if 'Difference' not in market_df.columns:
        val_cols = [c for c in market_df.columns if 'Value' in c]
        if len(val_cols) >= 2:
            market_df['Difference'] = market_df[val_cols[-1]] - market_df[val_cols[0]]

    income_df['Net_Spend'] = income_df['Expenditure'] - income_df['Income']
    fin_df = pd.merge(market_df, income_df[['Squad_Common', 'Net_Spend']], on='Squad_Common', how='left')
    fin_df['Organic_Growth'] = fin_df['Difference'] - fin_df['Net_Spend']

    final_df = pd.merge(perf_df, fin_df[['Squad_Common', 'Organic_Growth']], on='Squad_Common', how='left')
    final_df['Manager'] = final_df['Squad_Common'].map(common_to_mgr)
    final_df['Organic_Growth_M'] = final_df['Organic_Growth'] / 1_000_000
    final_df['Quadrant'] = final_df.apply(get_quadrant, axis=1)

    return final_df.dropna(subset=['Fair_Index', 'Organic_Growth'])