import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Manager Trust Dashboard", layout="wide")

# --- CONFIGURATION ---
# Update this path to where your CSV is located relative to this script
FILE_PATH = os.path.join("data", "raw", "23-24", "player_minutes.csv")

# --- AGE DEFINITIONS ---
AGE_RANGES = {
    "Prospects":  (0, 20),
    "Developing": (21, 23),
    "Prime":      (24, 29),
    "Veterans":   (30, 100)
}
ORDERED_GROUPS = ["Prospects", "Developing", "Prime", "Veterans"]

# --- HELPER FUNCTIONS ---

def get_age_group(age):
    for group, (min_a, max_a) in AGE_RANGES.items():
        if min_a <= age <= max_a:
            return group
    return "Unknown"

def load_data(path):
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    return df

def apply_squad_filters(df):
    """
    Applies the 'Ghost Cleanse' and 'Active Backup' logic.
    """
    # Standardize Columns
    if 'unSub' not in df.columns: df['unSub'] = 0
    df['unSub'] = df['unSub'].fillna(0).astype(int)
    df['MP'] = df['MP'].fillna(0).astype(int)
    df['Min'] = df['Min'].fillna(0).astype(int)

    # Calculate Total Squad Inclusions
    df['Squad_Apps'] = df['MP'] + df['unSub']

    # Filter Logic
    is_senior = (df['Age'] >= 21) & (df['Squad_Apps'] > 0)
    is_valid_prospect = (df['Age'] < 21) & ( (df['MP'] >= 3) | (df['Squad_Apps'] >= 5) )
    
    keep_mask = is_senior | is_valid_prospect
    return df[keep_mask].copy()

def calculate_trust_metrics(df):
    """
    Calculates Inventory % vs Minutes % for each Age Group.
    Returns a long-format DataFrame suitable for Plotly.
    """
    total_players = len(df)
    total_minutes = df['Min'].sum()
    
    data = []
    
    # Group by Age Group
    grouped = df.groupby('Age_Group')
    
    for group in ORDERED_GROUPS:
        # Get subset for this group
        if group in grouped.groups:
            group_df = grouped.get_group(group)
            count = len(group_df)
            minutes = group_df['Min'].sum()
        else:
            count = 0
            minutes = 0
            
        # Calculate Percentages
        inv_pct = (count / total_players * 100) if total_players > 0 else 0
        min_pct = (minutes / total_minutes * 100) if total_minutes > 0 else 0
        
        # Append Inventory Data Point
        data.append({
            "Age Group": group,
            "Metric": "Squad Depth (Inventory)",
            "Percentage": inv_pct,
            "Raw Value": count  # For tooltip
        })
        
        # Append Utilization Data Point
        data.append({
            "Age Group": group,
            "Metric": "Minutes Played (Utilization)",
            "Percentage": min_pct,
            "Raw Value": minutes # For tooltip
        })
        
    return pd.DataFrame(data)

# --- MAIN APP LOGIC ---

st.title("⚽ Manager Trust Matrix: Inventory vs. Utilization")
st.markdown("""
**The 'Trust Gap' Analysis:** Compare the players available to the manager (Inventory) vs. the actual playing time given (Utilization).
* **Inventory:** Filtered to exclude 'ghost' players. Includes Active Backups.
* **Utilization:** Based on actual minutes played.
""")

# 1. Load Data
df_raw = load_data(FILE_PATH)

if df_raw is None:
    st.error(f"File not found at: {FILE_PATH}. Please check the path.")
    st.stop()

# 2. Filter Data (Global Filter)
df_clean = apply_squad_filters(df_raw)
df_clean['Age_Group'] = df_clean['Age'].apply(get_age_group)

# 3. Sidebar Controls
st.sidebar.header("Filter Options")

# Select Squad
squads = sorted(df_clean['Squad'].dropna().unique())
selected_squad = st.sidebar.selectbox("Select Squad", squads)

# Select Position
# We create a 'Clean Pos' column for filtering
df_clean['Pos_Simple'] = df_clean['Pos'].astype(str).apply(lambda x: x.split(',')[0].strip())
positions = ["All"] + sorted(df_clean['Pos_Simple'].unique().tolist())
selected_pos = st.sidebar.selectbox("Select Position", positions)

# 4. Filter for Visualization
df_viz = df_clean[df_clean['Squad'] == selected_squad]

if selected_pos != "All":
    df_viz = df_viz[df_viz['Pos_Simple'] == selected_pos]

# 5. Calculation
metrics_df = calculate_trust_metrics(df_viz)

# 6. Visualization
if not metrics_df.empty:
    
    # Create the Grouped Bar Chart
    fig = px.bar(
        metrics_df, 
        x="Age Group", 
        y="Percentage", 
        color="Metric", 
        barmode="group",
        text_auto='.1f',
        color_discrete_map={
            "Squad Depth (Inventory)": "#1f77b4",  # Blue
            "Minutes Played (Utilization)": "#d62728" # Red
        },
        title=f"Distribution for {selected_squad} ({selected_pos})",
        height=500
    )
    
    fig.update_layout(yaxis_title="Percentage Share (%)", xaxis_title="")
    
    st.plotly_chart(fig, use_container_width=True)

    # 7. Data Table View
    st.subheader("Detailed Breakdown")
    
    # Pivot for cleaner table display
    table_df = metrics_df.pivot(index="Age Group", columns="Metric", values="Percentage")
    table_df["Trust Gap"] = table_df["Minutes Played (Utilization)"] - table_df["Squad Depth (Inventory)"]
    
    # Formatting
    st.dataframe(
        table_df.style.format("{:.1f}%").background_gradient(subset=["Trust Gap"], cmap="RdYlGn", vmin=-20, vmax=20)
    )

else:
    st.warning("No players found for this selection.")

# Debug Section (Optional - Good for development)
with st.expander("See Raw Filtered Data"):
    st.dataframe(df_viz[['Player', 'Age', 'Pos', 'Min', 'MP', 'unSub', 'Age_Group']])