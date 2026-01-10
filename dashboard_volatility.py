import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- CONSTANTS ---
CLUB_DATA_PATH = "data/raw/history/club_volatility.csv"
MANAGER_DATA_PATH = "data/raw/history/manager_volatility.csv"

# --- 1. DATA LOADING ---
@st.cache_data
def load_history_data():
    try:
        club_df = pd.read_csv(CLUB_DATA_PATH)
        mgr_df = pd.read_csv(MANAGER_DATA_PATH)
        return club_df, mgr_df
    except FileNotFoundError:
        st.error("❌ Volatility data not found. Please run the scrapers first.")
        return None, None

# --- 2. LOGIC ENGINE ---
def calculate_club_churn(club_df, club_name, years=5):
    """
    Calculates how many permanent managers the club had in the last N years.
    Returns: (Count, Verdict, Color)
    """
    if club_df is None or club_df.empty:
        return 0, "Unknown", "grey"

    # Filter specific club
    club_hist = club_df[club_df['Club'] == club_name].copy()
    
    if club_hist.empty:
        return 0, "No Data", "grey"

    # Convert Appointed to datetime
    club_hist['Appointed'] = pd.to_datetime(club_hist['Appointed'], dayfirst=True, errors='coerce')
    
    # Filter last N years
    cutoff_date = datetime.now() - timedelta(days=years*365)
    recent_managers = club_hist[club_hist['Appointed'] >= cutoff_date]
    
    churn_count = len(recent_managers)
    
    # Logic for Club Environment
    if churn_count <= 2:
        return churn_count, "Stable Haven", "green"
    elif churn_count <= 4:
        return churn_count, "Reactive", "orange"
    else:
        return churn_count, "The Meat Grinder", "red"

def classify_manager(mgr_row):
    """
    Classifies a manager based on Tenure (Stability) and Matches (Experience).
    """
    if mgr_row.empty:
        return "Unknown", "Unknown", "grey"
        
    tenure = mgr_row['Avg_Tenure_Years'].values[0]
    matches = mgr_row['Total_Matches'].values[0]
    
    # Experience Level
    if matches < 100:
        exp_label = "Rookie"
    elif matches < 300:
        exp_label = "Established"
    else:
        exp_label = "Veteran"
        
    # Stability Type
    if tenure < 1.2:
        stab_label = "Firefighter / Hopper"
        color = "red"
    elif tenure < 2.5:
        stab_label = "Standard"
        color = "orange"
    else:
        stab_label = "Dynasty Builder"
        color = "green"
        
    return f"{exp_label} {stab_label}", tenure, color

# --- 3. VISUALIZATIONS ---
def plot_club_timeline(club_df, club_name):
    """
    Generates a Gantt chart of the club's managerial history colored by PPG.
    """
    if club_df is None: return None
    
    df = club_df[club_df['Club'] == club_name].copy()
    if df.empty: return None

    # Sort by appointment
    df['Appointed_Dt'] = pd.to_datetime(df['Appointed'], dayfirst=True)
    df = df.sort_values('Appointed_Dt')

    # Create End Date (Next Appointed or Today)
    df['End_Dt'] = df['Appointed_Dt'].shift(-1) - timedelta(days=1)
    df['End_Dt'] = df['End_Dt'].fillna(datetime.now())

    # Color Scale for PPG
    fig = px.timeline(
        df, 
        x_start="Appointed_Dt", 
        x_end="End_Dt", 
        y="Club",
        color="PPG",
        hover_data=["Manager", "Matches", "Days_In_Charge"],
        color_continuous_scale=["red", "yellow", "green"],
        range_color=[0.5, 2.5],
        title=f"Managerial History: {club_name} (Color = PPG)"
    )
    
    fig.update_yaxes(visible=False)
    fig.update_layout(height=180, margin=dict(l=10, r=10, t=40, b=10))
    return fig

# --- 4. MAIN WIDGET ---
def render_volatility_widget(selected_manager, selected_club):
    """
    The main function to call in your dashboard.
    """
    st.subheader("🏛️ Strategic Fit & Stability Context")
    
    club_df, mgr_df = load_history_data()
    
    if club_df is None or mgr_df is None:
        return

    # --- A. BIO DATA HEADER ---
    mgr_data = mgr_df[mgr_df['Manager'] == selected_manager]
    
    if not mgr_data.empty:
        row = mgr_data.iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Age", f"{int(row['Age'])}" if pd.notna(row['Age']) else "N/A")
        c2.metric("Agent", row['Agent'] if pd.notna(row['Agent']) else "Unknown")
        c3.metric("Contract", row['Contract_Until'] if pd.notna(row['Contract_Until']) else "Unknown")
        c4.metric("License", "Pro" if "Pro" in str(row['Coaching_Licence']) else "Standard")
        
        st.divider()

        # --- B. THE RISK MATRIX ---
        # 1. Manager Score
        mgr_label, mgr_tenure, mgr_color = classify_manager(mgr_data)
        
        # 2. Club Score
        churn_count, club_label, club_color = calculate_club_churn(club_df, selected_club)
        
        # Display as Columns
        k1, k2, k3 = st.columns([1, 0.2, 1])
        
        with k1:
            st.markdown(f"**👤 Manager Profile**")
            st.caption(f"{selected_manager}")
            st.markdown(f"<h4 style='color:{mgr_color}'>{mgr_label}</h4>", unsafe_allow_html=True)
            st.progress(min(mgr_tenure / 5.0, 1.0))
            st.caption(f"Avg Tenure: {mgr_tenure} Years")

        with k2:
            st.markdown("<h1 style='text-align: center;'>⚡</h1>", unsafe_allow_html=True)

        with k3:
            st.markdown(f"**🏟️ Club Environment**")
            st.caption(f"{selected_club} (Last 5 Yrs)")
            st.markdown(f"<h4 style='color:{club_color}'>{club_label}</h4>", unsafe_allow_html=True)
            st.progress(min(churn_count / 8.0, 1.0)) # Max 8 managers scale
            st.caption(f"Churn: {churn_count} Managers")

        # --- C. THE VERDICT ---
        # Simple Rule-Based Logic
        verdict = ""
        risk_level = ""
        
        if club_label == "The Meat Grinder" and "Builder" in mgr_label:
            verdict = "⚠️ **CULTURE CLASH:** This club fires managers quickly, but this manager needs time to build."
            risk_level = "High Risk"
            box_color = "#ffebee" # Light Red
        elif club_label == "The Meat Grinder" and "Firefighter" in mgr_label:
            verdict = "✅ **ALIGNMENT:** High turnover club hiring a short-term specialist."
            risk_level = "Functional Match"
            box_color = "#e8f5e9" # Light Green
        elif club_label == "Stable Haven":
            verdict = "🛡️ **SAFE ENVIRONMENT:** A perfect platform for a project manager."
            risk_level = "Low Risk"
            box_color = "#e3f2fd" # Light Blue
        else:
            verdict = "⚖️ **NEUTRAL:** Standard risks apply."
            risk_level = "Medium Risk"
            box_color = "#fff3e0" # Light Orange

        st.info(f"{verdict}")

    else:
        st.warning(f"No history data found for {selected_manager}")

    # --- D. THE TIMELINE ---
    st.markdown("#### ⏳ Club Instability Timeline")
    timeline_fig = plot_club_timeline(club_df, selected_club)
    if timeline_fig:
        st.plotly_chart(timeline_fig, use_container_width=True)
    else:
        st.write("No timeline data available.")