import argparse
import os
import re
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.lines import Line2D

# --- CONFIGURATION & LABELS ---
LABEL_Q1, LABEL_Q2 = "Value Multiplier", "Asset Developer"
LABEL_Q3, LABEL_Q4 = "Results Specialist", "Performance Deficit"
DESC_Q1 = "High Returns on Wages + Asset Growth"
DESC_Q2 = "Building Future Value despite current results"
DESC_Q3 = "Winning now, but consuming squad value"
DESC_Q4 = "Failing to deliver results or value"

# --- 1. DATA LOADING & PROCESSING ---
def load_and_process_data(season):
    """Loads, cleans, and calculates metrics for a specific season."""
    base_dir = os.path.join("data", "raw", season)
    
    # Define Paths
    files = {
        'wages': os.path.join(base_dir, 'wages.csv'),
        'league': os.path.join(base_dir, 'league_table.csv'),
        'market': os.path.join(base_dir, 'market_value.csv'),
        'income': os.path.join(base_dir, 'income_expenditure.csv'),
        'mapping': os.path.join(base_dir, 'team_name.csv')
    }

    # Validation
    missing = [name for name, path in files.items() if not os.path.exists(path)]
    if missing:
        print(f"❌ Error: Missing files in {base_dir}: {', '.join(missing)}")
        return None

    print(f"📂 Loading data for Season {season}...")
    wages_df = pd.read_csv(files['wages'])
    league_df = pd.read_csv(files['league'])
    market_df = pd.read_csv(files['market'])
    income_df = pd.read_csv(files['income'])
    map_df = pd.read_csv(files['mapping'])

    # Create Mappers
    fbref_to_common = dict(zip(map_df['FBref_Name'], map_df['Common_Name']))
    tm_to_common = dict(zip(map_df['TM_Name'], map_df['Common_Name']))
    common_to_mgr = dict(zip(map_df['Common_Name'], map_df['Manager']))

    # --- PROCESS X-AXIS (Performance) ---
    def clean_wage(x):
        if pd.isna(x): return 0.0
        m = re.search(r'€\s*([\d,]+)', str(x))
        return float(m.group(1).replace(',', '')) if m else 0.0
    # Parse Estimation Percentage
    def clean_estimated(x):
        if pd.isna(x): return 0.0
        # Remove % and convert to float (e.g., "25%" -> 0.25)
        return float(str(x).replace('%', '')) / 100.0

    wages_df['Estimated_Pct'] = wages_df['Estimated'].apply(clean_estimated)
    # Create the flag: True if estimation is > 50%
    wages_df['Is_Low_Confidence'] = wages_df['Estimated_Pct'] > 0.5

    def clean_deduction(x):
        if pd.isna(x): return 0
        m = re.search(r'(\d+)-point deduction', str(x))
        return int(m.group(1)) if m else 0

    wages_df['Squad_Common'] = wages_df['Squad'].map(fbref_to_common)
    league_df['Squad_Common'] = league_df['Squad'].map(fbref_to_common)

    wages_df['Wage_Rank'] = wages_df['Annual Wages'].apply(clean_wage).rank(ascending=False, method='min')
    
    league_df['Adjusted_Pts'] = league_df['Pts'] + league_df['Notes'].apply(clean_deduction)
    league_df['Adjusted_League_Rank'] = league_df['Adjusted_Pts'].rank(ascending=False, method='min')

    perf_df = pd.merge(
        league_df[['Squad_Common', 'Adjusted_League_Rank']], 
        wages_df[['Squad_Common', 'Wage_Rank', 'Is_Low_Confidence']], 
        on='Squad_Common', how='left'
    )
    perf_df['Fair_Index'] = perf_df['Wage_Rank'] - perf_df['Adjusted_League_Rank']

    # --- PROCESS Y-AXIS (Development) ---
    market_df['Squad_Common'] = market_df['Club'].map(tm_to_common)
    income_df['Squad_Common'] = income_df['Club'].map(tm_to_common)
    market_df = market_df.dropna(subset=['Squad_Common'])

    # Calculate Value Difference
    # Robust check: if 'Difference' col exists use it, else calc from Value columns
    if 'Difference' not in market_df.columns:
        val_cols = [c for c in market_df.columns if 'Value' in c]
        if len(val_cols) >= 2:
            market_df['Difference'] = market_df[val_cols[-1]] - market_df[val_cols[0]]

    income_df['Net_Spend'] = income_df['Expenditure'] - income_df['Income']

    fin_df = pd.merge(market_df, income_df[['Squad_Common', 'Net_Spend']], on='Squad_Common', how='left')
    fin_df['Organic_Growth'] = fin_df['Difference'] - fin_df['Net_Spend']

    # --- FINAL MERGE ---
    final_df = pd.merge(perf_df, fin_df[['Squad_Common', 'Organic_Growth']], on='Squad_Common', how='left')
    final_df['Manager'] = final_df['Squad_Common'].map(common_to_mgr)
    final_df['Organic_Growth_M'] = final_df['Organic_Growth'] / 1_000_000

    def get_q(row):
        x, y = row['Fair_Index'], row['Organic_Growth']
        if pd.isna(x) or pd.isna(y): return "Unknown"
        if x >= 0 and y >= 0: return LABEL_Q1
        if x < 0 and y >= 0: return LABEL_Q2
        if x >= 0 and y < 0: return LABEL_Q3
        return LABEL_Q4

    final_df['Quadrant'] = final_df.apply(get_q, axis=1)
    
    return final_df.dropna(subset=['Fair_Index', 'Organic_Growth'])

# --- 2. LAYOUT ALGORITHM ---
def resolve_overlaps(df, min_dist=18):
    """Prevents vertical label overlap."""
    df = df.copy()
    df['Label_Y'] = df['Organic_Growth_M']
    df['X_Bin'] = df['Fair_Index'].round()
    
    for x_val in df['X_Bin'].unique():
        group = df[df['X_Bin'] == x_val].sort_values(by='Organic_Growth_M')
        if len(group) < 2: continue
        
        indices = group.index
        for i in range(1, len(indices)):
            prev_idx, curr_idx = indices[i-1], indices[i]
            prev_y = df.at[prev_idx, 'Label_Y']
            curr_y = df.at[curr_idx, 'Label_Y']
            
            if (curr_y - prev_y) < min_dist:
                shift = min_dist - (curr_y - prev_y)
                df.at[curr_idx, 'Label_Y'] += shift
    return df

# --- 3. EXECUTION ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", required=True, help="Season folder name (e.g., 23-24)")
    args = parser.parse_args()
    
    df = load_and_process_data(args.season)
    
    if df is not None:
        # --- PRINT LOG (Replaces process_data.py) ---
        print("\n" + "="*85)
        print(f"{f'MANAGER PERFORMANCE MATRIX ({args.season})':^85}")
        print("="*85)
        print(f"{'Squad':<15} | {'Index':<5} | {'Growth (€M)':<12} | {'Quadrant':<20} | {'Manager'}")
        print("-" * 85)
        for _, r in df.sort_values(by='Organic_Growth', ascending=False).iterrows():
            mgr_short = str(r['Manager']).split('/')[0][:20]
            print(f"{r['Squad_Common']:<15} | {int(r['Fair_Index']):<5} | {r['Organic_Growth_M']:<12.1f} | {r['Quadrant']:<20} | {mgr_short}")
        print("-" * 85)

        # --- PLOT CHART ---
        plt.figure(figsize=(16, 12))
        sns.set_style("white")
        
        # Layout
        df_layout = resolve_overlaps(df)
        
        # Limits & Zones
        x_max, x_min = df['Fair_Index'].max() + 1, df['Fair_Index'].min() - 1
        y_max, y_min = df_layout['Label_Y'].max() + 30, df_layout['Label_Y'].min() - 30
        
        colors = ['#2ecc71', '#3498db', '#f1c40f', '#e74c3c'] # G, B, O, R
        quads = [[0, x_max, 0, y_max], [x_min, 0, 0, y_max], [0, x_max, y_min, 0], [x_min, 0, y_min, 0]]
        
        for (x1, x2, y1, y2), c in zip(quads, colors):
            plt.fill_between([x1, x2], y1, y2, color=c, alpha=0.1)

        plt.axhline(0, color='black', lw=1.2); plt.axvline(0, color='black', lw=1.2)

        palette = {LABEL_Q1: '#27ae60', LABEL_Q2: '#2980b9', LABEL_Q3: '#d35400', LABEL_Q4: '#c0392b'}
        
        # Plot in two layers based on confidence
        
        # 1. Plot Reliable Data (Full Opacity)
        sns.scatterplot(
            data=df[~df['Is_Low_Confidence']], # The ~ means NOT low confidence
            x='Fair_Index', y='Organic_Growth_M', hue='Quadrant', 
            palette=palette, s=150, ec='white', lw=1.5, legend=False, zorder=10, alpha=1.0
        )

        # 2. Plot Low Confidence Data (Low Opacity)
        sns.scatterplot(
            data=df[df['Is_Low_Confidence']], 
            x='Fair_Index', y='Organic_Growth_M', hue='Quadrant', 
            palette=palette, s=150, ec='white', lw=1.5, legend=False, zorder=10, alpha=0.4
        )
        #sns.scatterplot(data=df, x='Fair_Index', y='Organic_Growth_M', hue='Quadrant', palette=palette, s=150, ec='white', lw=1.5, legend=False, zorder=10)

        for _, row in df_layout.iterrows():
            mgr = str(row['Manager']).replace('/', ' &\n') if '/' in str(row['Manager']) else str(row['Manager'])
            txt = f"{mgr}\n({row['Squad_Common']})"
            
            ay, ly = row['Organic_Growth_M'], row['Label_Y']
            arrow = dict(arrowstyle="-", color='gray', alpha=0.5) if abs(ly - ay) > 5 else None
            if arrow is None: ly += 8 
            
            # Dynamic Opacity for Text
            # If Low Confidence, set text/box opacity to 0.4, otherwise 1.0 (or 0.7 for box default)
            text_alpha = 0.4 if row['Is_Low_Confidence'] else 1.0
            box_alpha = 0.3 if row['Is_Low_Confidence'] else 0.7
            
            # Add a visual marker (⚠️) to the text if low confidence
            if row['Is_Low_Confidence']:
                txt = "(!) " + txt

            plt.annotate(txt, (row['Fair_Index'], ay), (row['Fair_Index'], ly), 
                         ha='center', va='bottom' if ly>ay else 'top', fontsize=7, fontweight='bold',
                         alpha=text_alpha, 
                         bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="none", alpha=box_alpha), 
                         arrowprops=arrow, zorder=11)

        # 1. Quadrant Legend Items
        legs = [Line2D([0],[0], marker='o', color='w', label=f"{k}: {v}", markerfacecolor=palette[k], markersize=10) 
                for k, v in zip([LABEL_Q1, LABEL_Q2, LABEL_Q3, LABEL_Q4], [DESC_Q1, DESC_Q2, DESC_Q3, DESC_Q4])]
        
        # 2. Add "Low Confidence" Legend Item
        # We use a gray circle with low alpha (0.4) to match the chart
        legs.append(Line2D([0], [0], marker='o', color='w', label='Low Confidence (>50% of the team wages were Est.)', 
                           markerfacecolor='gray', markersize=10, alpha=0.4))

        # Display Legend
        plt.legend(handles=legs, loc='upper center', bbox_to_anchor=(0.5, -0.08), 
                   ncol=2, frameon=False, fontsize=11)
        
        plt.title(f'Football Manager Assessment Matrix ({args.season} Premier League)', fontsize=18, weight='bold', pad=20)
        plt.xlabel('Fair Index (Wage Efficiency)\n<-- Underperforming Budget | Overperforming Budget -->', fontsize=12, labelpad=10)
        plt.ylabel('Organic Growth (€ Millions)\n<-- Value depreciation | Value Creation -->', fontsize=12, labelpad=10)
        plt.xlim(x_min, x_max); plt.ylim(y_min, y_max)
        plt.tight_layout()
        
        out_file = f"manager_matrix_{args.season}.png"
        plt.savefig(out_file, dpi=300, bbox_inches='tight')
        print(f"\n✅ Chart saved to: {out_file}")