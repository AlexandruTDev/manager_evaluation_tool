import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import os
import age_parser as ap
import manager_matrix as mm
import dashboard_tactics as dt

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Football Manager Analytics", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .manager-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #e0e0e0;
        margin-bottom: 10px;
    }
    .stat-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        color: white;
        font-weight: bold;
        font-size: 0.9em;
        text-align: center;
        min-width: 40px;
    }
    .badge-w { background-color: #2ecc71; } /* Green */
    .badge-d { background-color: #95a5a6; } /* Grey */
    .badge-l { background-color: #e74c3c; } /* Red */
    .badge-ppm { background-color: #3498db; } /* Blue */
    .small-label { font-size: 0.8em; color: #666; text-transform: uppercase; letter-spacing: 1px; }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE ---
if 'selected_squad_key' not in st.session_state: st.session_state.selected_squad_key = None
if 'current_view' not in st.session_state: st.session_state.current_view = "📊 League Matrix"

# --- DYNAMIC DATA LOADING ---
BASE_RAW_DIR = os.path.join("data", "raw")
if not os.path.exists(BASE_RAW_DIR):
    st.error(f"Base data directory not found: {BASE_RAW_DIR}")
    st.stop()

available_seasons = sorted([d for d in os.listdir(BASE_RAW_DIR) if os.path.isdir(os.path.join(BASE_RAW_DIR, d))])
if not available_seasons:
    st.error("No season folders found.")
    st.stop()

# --- SIDEBAR ---
st.sidebar.title("Controls")
selected_season = st.sidebar.selectbox("Select Season", available_seasons, index=len(available_seasons)-1)
SEASON_DIR = os.path.join(BASE_RAW_DIR, selected_season)
show_labels = st.sidebar.checkbox("Show Manager Names on Matrix", value=True)

# --- LOAD DATA ---
df_matrix = mm.load_matrix_data(SEASON_DIR)
df_players = ap.load_data(os.path.join(SEASON_DIR, "player_minutes.csv"))
manager_map = ap.load_manager_map(os.path.join(SEASON_DIR, "team_name.csv"))
team_map = ap.load_team_mapping(os.path.join(SEASON_DIR, "team_name.csv"))
df_tenure = ap.load_manager_tenure(os.path.join(SEASON_DIR, "manager_tenure.csv"))

if df_players is None or df_matrix is None:
    st.error(f"Missing data in **{selected_season}**.")
    st.stop()

# --- NAVIGATION ---
view_options = ["📊 League Matrix", "🕵️ Manager Profile"]
def update_view_state(): st.session_state.current_view = st.session_state.nav_radio
try: radio_index = view_options.index(st.session_state.current_view)
except: radio_index = 0

selected_view = st.radio(
    "", options=view_options, horizontal=True, index=radio_index, 
    key="nav_radio", on_change=update_view_state, label_visibility="collapsed"
)
st.markdown("---")

# ==============================================================================
# VIEW 1: LEAGUE MATRIX
# ==============================================================================
if st.session_state.current_view == "📊 League Matrix":
    st.header(f"Manager Performance Matrix ({selected_season})")
    
    if not df_matrix.empty:
        df_matrix['Manager_Short'] = df_matrix['Manager'].astype(str).apply(lambda x: x.split(' ')[-1] if isinstance(x, str) else x)
        
        # Ensure categories match the legend we want
        def get_display_category(row):
            if row['Is_Low_Confidence']: return "Low Confidence"
            return row['Quadrant']
        df_matrix['Display_Category'] = df_matrix.apply(get_display_category, axis=1)

        x_max, x_min = df_matrix['Fair_Index'].max() + 3, df_matrix['Fair_Index'].min() - 3
        y_max, y_min = df_matrix['Organic_Growth_M'].max() + 70, df_matrix['Organic_Growth_M'].min() - 70

        hover_temp = "<b>%{hovertext}</b><br><span style='font-size:12px;color:gray;'>Team: %{customdata[0]}</span><br><br>──────────<br>Wage Efficiency: <b>%{x:+.0f}</b><br>Squad Value Fluctuation: <b>%{y:+.1f}M €</b><extra></extra>"

        fig = px.scatter(
            df_matrix, x="Fair_Index", y="Organic_Growth_M", color="Display_Category",
            text="Manager_Short" if show_labels else None, hover_name="Manager",
            hover_data={"Squad_Common": True, "Fair_Index": False, "Organic_Growth_M": False, "Display_Category": False, "Manager_Short": False},
            color_discrete_map={
                "Value Multiplier": "#2ecc71", 
                "Asset Developer": "#3498db", 
                "Results Specialist": "#f1c40f", 
                "Performance Deficit": "#e74c3c", 
                "Low Confidence": "#95a5a6"
            },
            height=700
        )
        
        fig.update_traces(
            marker=dict(size=20, line=dict(width=1, color='DarkSlateGrey')),
            hovertemplate=hover_temp,
            hoverlabel=dict(bgcolor="rgba(255, 255, 255, 0.95)", bordercolor="#444", font_size=13, font_family="Arial")
        )
        if show_labels: 
            fig.update_traces(textposition='top center', textfont=dict(size=11, family="Arial", color='black'), selector=dict(mode='markers+text'))

        # Background Quadrants
        fig.add_shape(type="rect", x0=0, y0=0, x1=x_max, y1=y_max, fillcolor="#2ecc71", opacity=0.1, layer="below", line_width=0)
        fig.add_shape(type="rect", x0=x_min, y0=0, x1=0, y1=y_max, fillcolor="#3498db", opacity=0.1, layer="below", line_width=0)
        fig.add_shape(type="rect", x0=0, y0=y_min, x1=x_max, y1=0, fillcolor="#f1c40f", opacity=0.1, layer="below", line_width=0)
        fig.add_shape(type="rect", x0=x_min, y0=y_min, x1=0, y1=0, fillcolor="#e74c3c", opacity=0.1, layer="below", line_width=0)
        
        # Axis Lines
        fig.add_vline(x=0, line_width=2, line_color="black")
        fig.add_hline(y=0, line_width=2, line_color="black")

        # Annotations (Directional)
        fig.add_annotation(x=0, y=y_max, text="Value Creation ↖", showarrow=False, xanchor="right", xshift=-15, yshift=-10, font=dict(color="gray", size=12, weight="bold"))
        fig.add_annotation(x=0, y=y_min, text="↘ Value Depreciation", showarrow=False, xanchor="left", xshift=15, yshift=10, font=dict(color="gray", size=12, weight="bold"))
        fig.add_annotation(x=x_min, y=y_min, text="← Underperforming Budget", showarrow=False, xanchor="left", yshift=10)
        fig.add_annotation(x=x_max, y=y_min, text="Overperforming Budget →", showarrow=False, xanchor="right", yshift=10)

        # Layout Update: Explicit Titles & Legend
        fig.update_layout(
            xaxis_title="<b>Wage Efficiency</b> (Rank vs Budget)",
            yaxis_title="<b>Organic Growth</b> (€ Millions)",
            showlegend=False,  # Forced Legend ON
            plot_bgcolor="white",
            margin=dict(l=50, r=50, t=50, b=60)
        )
        
        fig.update_xaxes(range=[x_min, x_max])
        fig.update_yaxes(range=[y_min, y_max])

        st.plotly_chart(fig, use_container_width=True, key="matrix_chart")
        
        # Legend Description Block (Restored)
        st.markdown("""
        <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">
            <h4 style="margin-top:0;">Legend Definitions</h4>
            <ul style="list-style-type: none; padding-left: 0; display: flex; flex-wrap: wrap; gap: 20px;">
                <li><span style="color: #2ecc71;">&#9679;</span> <b>Value Multiplier</b><br><small>High Returns + Asset Growth</small></li>
                <li><span style="color: #3498db;">&#9679;</span> <b>Asset Developer</b><br><small>Building Value vs Results</small></li>
                <li><span style="color: #f1c40f;">&#9679;</span> <b>Results Specialist</b><br><small>Winning vs Value Cost</small></li>
                <li><span style="color: #e74c3c;">&#9679;</span> <b>Performance Deficit</b><br><small>Failing Results & Value</small></li>
                <li><span style="color: #95a5a6;">&#9679;</span> <b>Low Confidence</b><br><small>>50% Estimated Wages</small></li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("View Raw Data"):
            st.dataframe(df_matrix[['Manager', 'Squad_Common', 'Fair_Index', 'Organic_Growth_M', 'Display_Category']].sort_values(by='Organic_Growth_M', ascending=False))

# ==============================================================================
# VIEW 2: DEEP DIVE 
# ==============================================================================
elif st.session_state.current_view == "🕵️ Manager Profile":
    
    # Step 1: Get Unique Managers from TENURE file
    if df_tenure is not None and not df_tenure.empty:
        # Filter: Only managers with >= 5 matches (~13% of a season)
        relevant_tenures = df_tenure[df_tenure['Matches'] >= 5]
        
        if relevant_tenures.empty:
            st.warning("No managers found with sufficient matches (>5) in tenure data.")
            st.stop()
            
        available_managers = sorted(relevant_tenures['Manager'].unique())
    else:
        st.error("Manager Tenure data missing.")
        st.stop()
    
    c1, c2 = st.columns([1, 2])
    
    with c1:
        # Manager Dropdown
        selected_manager = st.selectbox("Select Manager", available_managers)
        
        # Find associated squads
        mgr_tenures = df_tenure[df_tenure['Manager'] == selected_manager]
        associated_squads = mgr_tenures['Squad'].unique()
        
        # Handle Multi-Club Managers
        if len(associated_squads) > 1:
            selected_squad_common = st.selectbox("Select Club (Multiple Tenures)", associated_squads)
        elif len(associated_squads) == 1:
            selected_squad_common = associated_squads[0]
            # [REMOVED]: The caption "Club: ..." is gone.
        else:
            selected_squad_common = None
            st.warning("Manager found but no club linked in tenure file.")

    if selected_squad_common:
        # Get the specific tenure record
        current_tenure = mgr_tenures[mgr_tenures['Squad'] == selected_squad_common].iloc[0]
        
        # Link to Matrix Data
        matrix_squad_row = df_matrix[df_matrix['Squad_Common'] == selected_squad_common]
        
        quadrant = "N/A"
        fair_index = "N/A"
        
        if not matrix_squad_row.empty:
            row = matrix_squad_row.iloc[0]
            quadrant = row['Quadrant']
            fair_index = row['Fair_Index']

        st.markdown("---")
        
        # --- ID CARD SECTION ---
        with st.container(border=True):
            # Layout: Name/Club | Stats
            c_head_1, c_head_2 = st.columns([1.5, 2.5])
            
            with c_head_1:
                st.markdown(f"## {selected_manager}")
                st.markdown(f"<h4 style='color: #2c3e50; margin-top: -15px; margin-bottom: 5px;'>🛡️ {selected_squad_common}</h4>", unsafe_allow_html=True)
                
                # [UPDATED]: Robust Date-Based Phase Logic
                try:
                    # 1. Determine Season Start Year from folder name (e.g. "23-24" -> 2023)
                    # Adjust this split logic if your folder names differ (e.g. "2023-2024")
                    if "-" in selected_season:
                        parts = selected_season.split("-")
                        if len(parts[0]) == 2:
                            season_start_year = int("20" + parts[0])
                        else:
                            season_start_year = int(parts[0])
                    else:
                        season_start_year = 2023 # Fallback
                        
                    # Define Season Boundaries
                    season_start_date = pd.Timestamp(year=season_start_year, month=8, day=15) # Mid-August
                    season_end_date = pd.Timestamp(year=season_start_year + 1, month=5, day=1) # May 1st
                    
                    # 2. Parse Tenure Dates
                    start_str = current_tenure.get('Start_Date', '')
                    end_str = current_tenure.get('End_Date', '')
                    
                    # Clean strings (handle typos or formats)
                    tenure_start = pd.to_datetime(start_str, dayfirst=True, errors='coerce')
                    
                    # Logic Tree
                    if pd.isna(tenure_start):
                        phase_label = "Unknown Phase"
                    elif tenure_start < season_start_date:
                        # They started BEFORE the season cutoff (Incumbent)
                        
                        # Did they finish the season?
                        is_finished = False
                        if "Present" in end_str:
                            is_finished = True
                        else:
                            tenure_end = pd.to_datetime(end_str, dayfirst=True, errors='coerce')
                            if pd.notna(tenure_end) and tenure_end > season_end_date:
                                is_finished = True
                                
                        if is_finished:
                            phase_label = "Full Season Charge"
                        else:
                            phase_label = "Dismissed Before Season End"
                    else:
                        # They started AFTER season began
                        phase_label = "Mid-Season Takeover"
                        
                except Exception as e:
                    phase_label = "Phase Calculation Error"
                    # print(e) # Debug if needed

                st.caption(f"Phase: **{phase_label}**")
            
            with c_head_2:
                matches = current_tenure['Matches']
                if matches > 0:
                    w_rate = current_tenure['W'] / matches * 100
                    d_rate = current_tenure['D'] / matches * 100
                    l_rate = current_tenure['L'] / matches * 100
                else:
                    w_rate = d_rate = l_rate = 0

                st.markdown(f"""
                    <div style="display: flex; justify-content: space-around; margin-top: 15px; align-items: center;">
                        <div style="text-align:center;">
                            <span class="stat-badge badge-w">{w_rate:.0f}%</span><br>
                            <span class="small-label">Win Rate</span>
                        </div>
                        <div style="text-align:center;">
                            <span class="stat-badge badge-d">{d_rate:.0f}%</span><br>
                            <span class="small-label">Draw Rate</span>
                        </div>
                        <div style="text-align:center;">
                            <span class="stat-badge badge-l">{l_rate:.0f}%</span><br>
                            <span class="small-label">Loss Rate</span>
                        </div>
                        <div style="text-align:center;">
                            <span class="stat-badge badge-ppm" style="font-size:1.2em;">{current_tenure['PPM']:.2f}</span><br>
                            <span class="small-label">Points/Match</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            
            # Full Width Progress Bar (Clamped)
            st.write("")
            calculated_share_pct = (matches / 38) * 100
            display_share = min(calculated_share_pct, 100.0)
            progress_val = min(calculated_share_pct / 100, 1.0)
            
            st.progress(progress_val, text=f"Season Share: {display_share:.1f}% ({matches} Matches)")

        # --- TABS ---
        tab_perf, tab_tactics = st.tabs(["🏆 Squad & Performance", "🧠 Tactical DNA"])

        # --- SUB-TAB 1: PERFORMANCE ---
        with tab_perf:
            st.markdown("#### Matrix Performance (Squad Level)")
            c1, c2 = st.columns(2)
            with c1: st.metric("Quadrant", quadrant)
            with c2: st.metric("Wage Efficiency", f"{fair_index:+.0f}" if fair_index != "N/A" else "N/A")

            st.markdown("---")
            
            # --- TRUST GAP ANALYSIS ---
            st.markdown("### The Trust Gap Analysis")
            st.caption(f"How did {selected_manager} utilize the squad?")
            
            # Reverse lookup for raw squad name
            raw_squad_name = None
            for s in df_players['Squad'].unique():
                if team_map.get(s, s) == selected_squad_common:
                    raw_squad_name = s; break
            
            if raw_squad_name:
                df_viz = df_players[df_players['Squad'] == raw_squad_name].copy()
                
                df_viz['Pos_Simple'] = df_viz['Pos'].astype(str).apply(lambda x: x.split(',')[0].strip())
                df_viz['Age_Group'] = df_viz['Age'].apply(ap.get_age_group)
                
                pos_options = ["All"] + sorted(df_viz['Pos_Simple'].unique())
                selected_pos = st.selectbox("Filter by Position", pos_options, key="pos_filter_trust")
                
                if selected_pos != "All": 
                    df_viz = df_viz[df_viz['Pos_Simple'] == selected_pos]
                
                metrics = ap.calculate_trust_metrics(df_viz)

                if not metrics.empty:
                    gap = metrics.pivot(index="Age Group", columns="Metric", values="Percentage").reset_index()
                    gap["Trust Gap"] = gap["Minutes Played (Players Utilization)"] - gap["Squad Depth (Available Players)"]
                    
                    fig = px.bar(
                        gap, x="Trust Gap", y="Age Group", orientation='h', 
                        text_auto='.1f', 
                        color="Trust Gap", color_continuous_scale="RdYlGn", 
                        range_color=[-20,20], title=f"Trust Distribution: {selected_manager}"
                    )
                    
                    fig.update_traces(texttemplate='%{x:.1f}%', textposition='auto')
                    fig.add_vline(x=0, line_dash="dash", line_color="black")
                    fig.update_layout(coloraxis_showscale=False)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    with st.expander("Detailed Split (Available vs Played)"):
                        fig_bar = px.bar(metrics, x="Age Group", y="Percentage", color="Metric", barmode="group", text_auto='.1f', height=350)
                        st.plotly_chart(fig_bar, use_container_width=True)
                else: 
                    st.warning("Insufficient player data for trust analysis.")
            else:
                st.warning(f"Could not map '{selected_squad_common}' to player data.")

        # --- SUB-TAB 2: TACTICAL DNA ---
        with tab_tactics:
            dt.render_manager_tactics(selected_manager)