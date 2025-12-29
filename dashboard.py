import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import os
import age_parser as ap
import manager_matrix as mm

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
view_options = ["📊 League Matrix", "🕵️ Manager Deep Dive"]
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

        # Click Event
        event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode="points", key="matrix_chart")
        if event and event.get("selection") and event["selection"]["points"]:
            try:
                clicked_squad = event["selection"]["points"][0]["customdata"][0]
                found_raw = None
                available_squads = ap.apply_squad_filters(df_players)['Squad'].unique()
                for squad in available_squads:
                    if team_map.get(squad, squad) == clicked_squad:
                        found_raw = squad; break
                if found_raw:
                    st.session_state.selected_squad_key = found_raw
                    st.session_state.current_view = "🕵️ Manager Deep Dive"
                    st.rerun()
            except: pass
        
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
elif st.session_state.current_view == "🕵️ Manager Deep Dive":
    df_clean = ap.apply_squad_filters(df_players)
    squads = sorted(df_clean['Squad'].dropna().unique())
    default_index = 0
    if st.session_state.selected_squad_key in squads:
        default_index = squads.index(st.session_state.selected_squad_key)
        if st.button("← Back"):
            st.session_state.current_view = "📊 League Matrix"; st.rerun()

    c1, c2 = st.columns(2)
    def update_sq(): st.session_state.selected_squad_key = st.session_state.squad_selector
    with c1: selected_squad = st.selectbox("Squad", squads, index=default_index, key="squad_selector", on_change=update_sq)
    
    df_clean['Age_Group'] = df_clean['Age'].apply(ap.get_age_group)
    df_clean['Pos_Simple'] = df_clean['Pos'].astype(str).apply(lambda x: x.split(',')[0].strip())
    with c2: selected_pos = st.selectbox("Position", ["All"] + sorted(df_clean['Pos_Simple'].unique()))

    squad_common = team_map.get(selected_squad, selected_squad)
    active_managers = ap.get_active_managers(df_tenure, squad_common, selected_season, match_threshold_pct=0.25)
    mgr_stats = df_matrix[df_matrix['Squad_Common'] == squad_common]
    
    st.markdown("---")
    st.markdown(f"### {squad_common}")
    
    if active_managers:
        cols = st.columns(len(active_managers))
        for idx, mgr in enumerate(active_managers):
            with cols[idx]:
                with st.container(border=True):
                    st.markdown(f"#### {mgr['Manager']}")
                    st.caption(f"**{mgr['Phase']}** • {mgr['Dates']}")
                    st.progress(mgr['Share']/100, text=f"Season Share: {mgr['Share']:.1f}%")
                    
                    st.markdown(f"""
                        <div style="display: flex; justify-content: space-between; margin-top: 10px;">
                            <div style="text-align:center;">
                                <span class="stat-badge badge-w">{mgr['W_Pct']:.0f}%</span><br>
                                <span class="small-label">Win</span>
                            </div>
                            <div style="text-align:center;">
                                <span class="stat-badge badge-d">{mgr['D_Pct']:.0f}%</span><br>
                                <span class="small-label">Draw</span>
                            </div>
                            <div style="text-align:center;">
                                <span class="stat-badge badge-l">{mgr['L_Pct']:.0f}%</span><br>
                                <span class="small-label">Loss</span>
                            </div>
                            <div style="text-align:center;">
                                <span class="stat-badge badge-ppm">{mgr['PPM']:.2f}</span><br>
                                <span class="small-label">Points/Match</span>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
    else:
        st.title(manager_map.get(selected_squad, "Unknown"))

    st.markdown("#### Matrix Performance")
    c1, c2 = st.columns(2)
    with c1: st.metric("Quadrant", mgr_stats.iloc[0]['Quadrant'] if not mgr_stats.empty else "N/A")
    with c2: st.metric("Wage Efficiency", f"{mgr_stats.iloc[0]['Fair_Index']:+.0f}" if not mgr_stats.empty else "N/A")

    st.markdown("---")
    # Restored Detailed Age Legend
    cols = st.columns(4)
    definitions = [
        ("Prospects", "< 21", "Future Assets"),
        ("Developing", "21 - 23", "High Value"),
        ("Prime", "24 - 29", "Performance Core"),
        ("Veterans", "30+", "Leadership")
    ]
    for col, (name, age, desc) in zip(cols, definitions):
        col.markdown(f"**{name}**")
        col.caption(f"Age: {age}")
        col.caption(f"Role: *{desc}*")
    st.markdown("---")
    
    st.markdown("### The Trust Gap Analysis")
    
    df_viz = df_clean[df_clean['Squad'] == selected_squad]
    if selected_pos != "All": df_viz = df_viz[df_viz['Pos_Simple'] == selected_pos]
    metrics = ap.calculate_trust_metrics(df_viz)

    if not metrics.empty:
        gap = metrics.pivot(index="Age Group", columns="Metric", values="Percentage").reset_index()
        gap["Trust Gap"] = gap["Minutes Played (Players Utilization)"] - gap["Squad Depth (Available Players)"]
        
        main_mgr = sorted(active_managers, key=lambda x: x['Share'], reverse=True)[0]['Manager'].split(' ')[-1] if active_managers else "Manager"
        
        fig = px.bar(
            gap, x="Trust Gap", y="Age Group", orientation='h', 
            text_auto='.1f', # <--- Formats hover
            color="Trust Gap", color_continuous_scale="RdYlGn", 
            range_color=[-20,20], title=f"Who does {main_mgr} trust?"
        )
        
        # FIX: Explicit Text Template for Bar Labels
        fig.update_traces(texttemplate='%{x:.1f}%', textposition='auto')
        
        fig.add_vline(x=0, line_dash="dash", line_color="black")
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("Available Players vs Minutes"):
            scope = f"Scope: **{selected_pos}**" if selected_pos != "All" else "Scope: **Full Squad**"
            st.markdown(f"{scope} | Team: **{selected_squad}**")
            fig_bar = px.bar(metrics, x="Age Group", y="Percentage", color="Metric", barmode="group", text_auto='.1f', height=350)
            st.plotly_chart(fig_bar, use_container_width=True)
    else: st.warning("No data.")