import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import ast 

# --- CONSTANTS ---
CLUB_DATA_PATH = "data/raw/history/club_volatility.csv"
MANAGER_DATA_PATH = "data/raw/history/manager_volatility.csv"

@st.cache_data
def load_history_data():
    try:
        club_df = pd.read_csv(CLUB_DATA_PATH)
        mgr_df = pd.read_csv(MANAGER_DATA_PATH)
        return club_df, mgr_df
    except FileNotFoundError:
        return None, None

def calculate_club_churn(club_df, club_name, years=5):
    if club_df is None or club_df.empty: return 0, 0, "Unknown", "grey" # <--- Return 4 values now
    
    club_hist = club_df[club_df['Club'] == club_name].copy()
    if club_hist.empty: return 0, 0, "No Data", "grey"

    club_hist['Appointed'] = pd.to_datetime(club_hist['Appointed'], dayfirst=True, errors='coerce')
    
    # --- [NEW LOGIC START] Calculate Exit Dates ---
    club_hist = club_hist.sort_values('Appointed')
    club_hist['Left_Date'] = club_hist['Appointed'].shift(-1) - timedelta(days=1)
    # ---------------------------------------------

    cutoff_date = datetime.now() - timedelta(days=years*365)
    recent_managers = club_hist[club_hist['Appointed'] >= cutoff_date]
    churn_count = len(recent_managers)
    
    # --- Count Inner-Season Exits ---
    inner_season_exits = 0
    for _, row in recent_managers.iterrows():
        if pd.notna(row['Left_Date']):
            month = row['Left_Date'].month
            # Active Months: Aug(8) to April(4). May/June/July are safe.
            if month in [8, 9, 10, 11, 12, 1, 2, 3, 4]:
                inner_season_exits += 1
    # --------------------------------------------------

    # Thresholds
    if churn_count <= 2: 
        return churn_count, inner_season_exits, "High Stability", "green"
    elif churn_count == 3: 
        return churn_count, inner_season_exits, "Moderate Stability", "orange"
    else: 
        return churn_count, inner_season_exits, "High Turnover", "red"

def classify_manager(mgr_row):
    if mgr_row.empty: return "Unknown", "Unknown", "grey", "Unknown", "grey", 0, 0
        
    tenure = mgr_row['Avg_Tenure_Years'].values[0]
    matches = mgr_row['Total_Matches'].values[0]
    
    # Experience
    if matches < 100:
        exp_label = "Novice"
        exp_color = "#3498db" 
    elif matches < 300:
        exp_label = "Established"
        exp_color = "#f39c12" 
    else:
        exp_label = "Experienced"
        exp_color = "#27ae60" 
        
    # Stability
    if tenure < 1.2:
        stab_label = "High Mobility"
        stab_color = "red"
    elif tenure < 2.5:
        stab_label = "Moderate Tenure"
        stab_color = "orange"
    else:
        stab_label = "Long-Term Architect"
        stab_color = "green"
        
    return exp_label, exp_color, stab_label, stab_color, tenure, matches

def plot_club_timeline(club_df, club_name):
    if club_df is None: return None
    df = club_df[club_df['Club'] == club_name].copy()
    if df.empty: return None

    # Prepare Dates
    df['Appointed_Dt'] = pd.to_datetime(df['Appointed'], dayfirst=True)
    df = df.sort_values('Appointed_Dt')
    df['End_Dt'] = df['Appointed_Dt'].shift(-1) - timedelta(days=1)
    df['End_Dt'] = df['End_Dt'].fillna(datetime.now())

    # Pre-format dates for the hover tooltip (so they look clean like "Nov 01, 2023")
    df['Start_Str'] = df['Appointed_Dt'].dt.strftime('%b %d, %Y')
    df['End_Str'] = df['End_Dt'].dt.strftime('%b %d, %Y')

    # --- 1. Identify Inner-Season Exits & Relevant Seasons ---
    inner_season_exits = []
    seasons_with_exits = set() # Store years that need labels
    
    for idx, row in df.iterrows():
        exit_date = row['End_Dt']
        if exit_date.date() >= datetime.now().date(): continue
        
        # Check inner-season months (Aug-April)
        if exit_date.month in [8, 9, 10, 11, 12, 1, 2, 3, 4]:
            inner_season_exits.append(exit_date)
            
            # Determine which season this belongs to for labeling
            # If exit is Jan-May 2024, season started 2023. If Aug-Dec 2023, season started 2023.
            if exit_date.month < 8:
                season_year = exit_date.year - 1
            else:
                season_year = exit_date.year
            seasons_with_exits.add(season_year)

    # --- 2. Build Chart ---
    # We add custom_data to pass our formatted strings to the hover template
    fig = px.timeline(
        df, 
        x_start="Appointed_Dt", 
        x_end="End_Dt", 
        y="Club", 
        color="PPG",
        # Pass extra columns for the custom tooltip
        custom_data=["Manager", "Matches", "Days_In_Charge", "Start_Str", "End_Str"],
        color_continuous_scale=["#e74c3c", "#f1c40f", "#2ecc71"],
        range_color=[0.5, 2.5],
        title=f"{club_name}: Managerial Timeline"
    )
    
    # --- 3. Custom Hover Template ---
    # <br> creates new lines, <b> bolds text. 
    # %{customdata[0]} refers to the first item in the custom_data list above (Manager)
    fig.update_traces(
        hovertemplate="<br>".join([
            "<b>%{customdata[0]}</b>", # Manager Name Header
            "──────────────",
            "<b>Appointed:</b> %{customdata[3]}",
            "<b>Left:</b> %{customdata[4]}",
            "<b>Tenure:</b> %{customdata[2]} days",
            "<b>Matches:</b> %{customdata[1]}",
            "<b>PPG:</b> %{marker.color:.2f}", # Access color value directly
            "<extra></extra>" # Hides the secondary box
        ])
    )

    # --- 4. Season Delimiters (Selective Labeling) ---
    min_year = df['Appointed_Dt'].min().year
    max_year = datetime.now().year
    
    for year in range(min_year, max_year + 1):
        ts_obj = pd.Timestamp(year=year, month=8, day=1)
        season_start_ms = ts_obj.timestamp() * 1000 
        
        # Only add text label if this season had an exit
        label_text = f"'{str(year)[2:]}" if year in seasons_with_exits else ""
        
        fig.add_vline(
            x=season_start_ms, 
            line_width=1, 
            line_dash="dash", 
            line_color="rgba(0,0,0,0.15)",
            annotation_text=label_text, 
            annotation_position="top left",
            annotation_font=dict(color="gray", size=10)
        )

    # --- 5. Inner-Season Markers ---
    for exit_dt in inner_season_exits:
        fig.add_annotation(
            x=exit_dt, y=club_name,
            text="▼", showarrow=False,
            yshift=50,
            font=dict(color="black", size=14)
        )

    fig.update_yaxes(visible=False)
    fig.update_layout(
        height=250, 
        margin=dict(l=10, r=10, t=40, b=50),
        xaxis=dict(title="", showgrid=False),
        plot_bgcolor="rgba(0,0,0,0)",
        coloraxis_colorbar=dict(
            orientation="h",
            yanchor="top", y=-0.2,
            xanchor="center", x=0.5,
            title="PPG Performance",
            thickness=15
        )
    )
    
    return fig

def render_volatility_widget(selected_manager, selected_club):
    st.subheader("Career & Stability Context")
    
    club_df, mgr_df = load_history_data()
    if club_df is None: 
        st.warning("Data missing.")
        return

    mgr_data = mgr_df[mgr_df['Manager'] == selected_manager]
    
    if not mgr_data.empty:
        row = mgr_data.iloc[0]
        
        # Bio Header
        c0, c1, c2, c3, c4, c5 = st.columns([1.6, 0.5, 1.5, 1.4, 0.8, 0.8])
        c0.metric("Name", selected_manager)
        c1.metric("Age", f"{int(row['Age'])}" if pd.notna(row['Age']) else "-")
        c2.metric("Agent", row['Agent'] if pd.notna(row['Agent']) else "Unknown")
        c3.metric("Contract Expiry", row['Contract_Until'] if pd.notna(row['Contract_Until']) else "-")
        c4.metric("License", "Pro" if "Pro" in str(row['Coaching_Licence']) else "Std")
        
        trophies_count = row['Trophies_Total'] if 'Trophies_Total' in row else 0
        c5.metric("Honours", f"🏆 {int(trophies_count)}" if trophies_count > 0 else "-")
        
        # Trophy Cabinet
        if trophies_count > 0 and 'Trophies_JSON' in row:
            try:
                trophy_data = ast.literal_eval(row['Trophies_JSON'])
                with st.expander(f"🏆 Trophy Cabinet ({int(trophies_count)})"):
                    for t in trophy_data:
                        st.markdown(f"**{t['name']}** <span style='color:grey; font-size:0.9em;'>({t['count']}x)</span>", unsafe_allow_html=True)
                        if t['wins']:
                            for win in t['wins']:
                                st.caption(f"• {win['season']}: {win['club']}")
                        else:
                            st.caption("• *Details unavailable*")
                        st.write("") 
            except: pass 
        
        st.divider()

        # Classification Logic
        exp_label, exp_color, stab_label, stab_color, mgr_tenure, matches = classify_manager(mgr_data)
        churn_count, inner_season_exits, club_label, club_color = calculate_club_churn(club_df, selected_club)
        
        k1, k2, k3 = st.columns([1, 0.1, 1])
        
        with k1:
            st.markdown("**Manager Profile**") 
            # --- [NEW] Changed Label to 'Seniority Level' ---
            st.markdown(f"""
                <div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 10px;">
                    <div style="background-color: {exp_color}20; border: 1px solid {exp_color}; color: {exp_color}; padding: 6px 10px; border-radius: 5px; font-weight: bold; font-size: 0.95em;">
                        Seniority Level: {exp_label} ({int(matches)} Matches)
                    </div>
                    <div style="background-color: {stab_color}20; border: 1px solid {stab_color}; color: {stab_color}; padding: 6px 10px; border-radius: 5px; font-weight: bold; font-size: 0.95em;">
                        Average Tenure: {mgr_tenure} Years ({stab_label})
                    </div>
                </div>
            """, unsafe_allow_html=True)

        with k2:
            st.markdown("<div style='border-left: 1px solid #ddd; height: 80px; margin: auto;'></div>", unsafe_allow_html=True)

        with k3:
            st.markdown("**Club Environment**")
            
            # --- [NEW] Logic for Warning Message ---
            warning_html = ""
            if inner_season_exits >= 2:
                warning_html = f"<div style='margin-top: 5px; font-size: 0.9em; color: #e74c3c;'>⚠️ <b>{inner_season_exits} Inner-Season Sackings</b></div>"
            elif inner_season_exits == 1:
                warning_html = f"<div style='margin-top: 5px; font-size: 0.9em; color: #f39c12;'>⚠️ 1 Inner-Season Sacking</div>"
            else:
                warning_html = f"<div style='margin-top: 5px; font-size: 0.9em; color: #2ecc71;'>✅ Stable Seasons (No inner-season exits)</div>"

            st.markdown(f"""
                <div style="margin-bottom: 10px;">
                    <div style="background-color: {club_color}20; border: 1px solid {club_color}; color: {club_color}; padding: 6px 10px; border-radius: 5px; font-weight: bold; font-size: 0.95em;">
                        Past 5 Years: {churn_count} Managers ({club_label})
                    </div>
                    {warning_html}
                </div>
            """, unsafe_allow_html=True)

    else:
        st.warning(f"No profile data for {selected_manager}")

    # Timeline
    timeline_fig = plot_club_timeline(club_df, selected_club)
    if timeline_fig:
        st.plotly_chart(timeline_fig, use_container_width=True)