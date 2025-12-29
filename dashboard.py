import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import os
import age_parser as ap
import manager_matrix as mm

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Football Manager Analytics", layout="wide")

# --- SESSION STATE ---
if 'selected_squad_key' not in st.session_state:
    st.session_state.selected_squad_key = None
if 'current_view' not in st.session_state:
    st.session_state.current_view = "📊 League Matrix"

# --- DYNAMIC DATA LOADING ---
BASE_RAW_DIR = os.path.join("data", "raw")

if not os.path.exists(BASE_RAW_DIR):
    st.error(f"Base data directory not found: {BASE_RAW_DIR}")
    st.stop()

available_seasons = sorted([d for d in os.listdir(BASE_RAW_DIR) if os.path.isdir(os.path.join(BASE_RAW_DIR, d))])

if not available_seasons:
    st.error("No season folders found in 'data/raw/'.")
    st.stop()

# --- SIDEBAR CONTROLS ---
st.sidebar.title("Controls")
selected_season = st.sidebar.selectbox("Select Season", available_seasons, index=len(available_seasons)-1)
SEASON_DIR = os.path.join(BASE_RAW_DIR, selected_season)
show_labels = st.sidebar.checkbox("Show Manager Names on Matrix", value=True)

# --- LOAD DATA ---
df_matrix = mm.load_matrix_data(SEASON_DIR)
df_players = ap.load_data(os.path.join(SEASON_DIR, "player_minutes.csv"))

# NEW: Load maps using the robust functions
manager_map = ap.load_manager_map(os.path.join(SEASON_DIR, "team_name.csv"))
team_map = ap.load_team_mapping(os.path.join(SEASON_DIR, "team_name.csv"))

if df_players is None or df_matrix is None:
    st.error(f"Missing data files in **{selected_season}**.")
    st.stop()

# --- NAVIGATION ---
view_options = ["📊 League Matrix", "🕵️ Manager Deep Dive"]

def update_view_state():
    st.session_state.current_view = st.session_state.nav_radio

try:
    radio_index = view_options.index(st.session_state.current_view)
except ValueError:
    radio_index = 0

selected_view = st.radio(
    "", 
    options=view_options, 
    horizontal=True, 
    index=radio_index,     
    key="nav_radio",       
    on_change=update_view_state,
    label_visibility="collapsed"
)

st.markdown("---")

# ==============================================================================
# VIEW 1: THE LEAGUE MATRIX
# ==============================================================================
if st.session_state.current_view == "📊 League Matrix":
    st.header(f"Manager Performance Matrix ({selected_season})")
    
    if not df_matrix.empty:
        df_matrix['Manager_Short'] = df_matrix['Manager'].astype(str).apply(lambda x: x.split(' ')[-1] if isinstance(x, str) else x)
        
        def get_display_category(row):
            if row['Is_Low_Confidence']: return "Low Confidence"
            return row['Quadrant']
            
        df_matrix['Display_Category'] = df_matrix.apply(get_display_category, axis=1)

        x_max = df_matrix['Fair_Index'].max() + 3
        x_min = df_matrix['Fair_Index'].min() - 3
        y_max = df_matrix['Organic_Growth_M'].max() + 70
        y_min = df_matrix['Organic_Growth_M'].min() - 70

        custom_hovertemplate = (
            "<b>%{hovertext}</b><br>" +
            "<span style='font-size:12px; color: gray;'>Team: %{customdata[0]}</span><br>" +
            "<br>──────────<br>" +
            "Wage Efficiency: <b>%{x:+.0f}</b><br>" + 
            "Squad Value Fluctuation: <b>%{y:+.1f}M €</b><br>" +
            "<extra></extra>"
        )

        fig = px.scatter(
            df_matrix,
            x="Fair_Index",
            y="Organic_Growth_M",
            color="Display_Category",
            text="Manager_Short" if show_labels else None,
            hover_name="Manager",
            # Pass Squad_Common as customdata[0]
            hover_data={"Squad_Common": True, "Fair_Index": False, "Organic_Growth_M": False, "Display_Category": False, "Manager_Short": False},
            color_discrete_map={
                "Value Multiplier": "#2ecc71", "Asset Developer": "#3498db",
                "Results Specialist": "#f1c40f", "Performance Deficit": "#e74c3c",
                "Low Confidence": "#95a5a6"
            },
            height=700
        )

        fig.update_traces(
            marker=dict(size=20, line=dict(width=1, color='DarkSlateGrey')),
            hovertemplate=custom_hovertemplate,
            hoverlabel=dict(bgcolor="rgba(255, 255, 255, 0.95)", bordercolor="#444", font_size=13, font_family="Arial")
        )

        if show_labels:
            fig.update_traces(textposition='top center', textfont=dict(size=11, family="Arial", color='black'), selector=dict(mode='markers+text'))

        fig.add_shape(type="rect", x0=0, y0=0, x1=x_max, y1=y_max, fillcolor="#2ecc71", opacity=0.1, layer="below", line_width=0)
        fig.add_shape(type="rect", x0=x_min, y0=0, x1=0, y1=y_max, fillcolor="#3498db", opacity=0.1, layer="below", line_width=0)
        fig.add_shape(type="rect", x0=0, y0=y_min, x1=x_max, y1=0, fillcolor="#f1c40f", opacity=0.1, layer="below", line_width=0)
        fig.add_shape(type="rect", x0=x_min, y0=y_min, x1=0, y1=0, fillcolor="#e74c3c", opacity=0.1, layer="below", line_width=0)

        fig.add_vline(x=0, line_width=2, line_color="black")
        fig.add_hline(y=0, line_width=2, line_color="black")

        fig.add_annotation(
            x=0, y=y_max, text="Value Creation ↖", showarrow=False, 
            xanchor="right", xshift=-15, yshift=-10, font=dict(color="gray", size=12, weight="bold")
        )
        fig.add_annotation(
            x=0, y=y_min, text="↘ Value Depreciation", showarrow=False, 
            xanchor="left", xshift=15, yshift=10, font=dict(color="gray", size=12, weight="bold")
        )
        fig.add_annotation(x=x_min, y=y_min, text="← Underperforming Budget", showarrow=False, xanchor="left", yanchor="bottom", font=dict(color="gray", size=12), xshift=10, yshift=10)
        fig.add_annotation(x=x_max, y=y_min, text="Overperforming Budget →", showarrow=False, xanchor="right", yanchor="bottom", font=dict(color="gray", size=12), xshift=-10, yshift=10)

        fig.update_layout(
            xaxis_title="<b>Wage Efficiency</b> (Rank vs Budget)",
            yaxis_title="<b>Organic Growth</b> (€ Millions)",
            showlegend=False,
            plot_bgcolor="white",
            margin=dict(l=50, r=50, t=50, b=60)
        )
        fig.update_xaxes(range=[x_min, x_max])
        fig.update_yaxes(range=[y_min, y_max])

        event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode="points", key="matrix_chart")
        
        if event and event.get("selection") and event["selection"]["points"]:
            try:
                # 1. Get Common Name from Matrix Click
                clicked_squad_common = event["selection"]["points"][0]["customdata"][0]
                
                # 2. Reverse Map: Common -> Raw (What is the squad called in player_minutes.csv?)
                # Since our map is Many-to-One (Many variants -> One Common), we look for a match
                # The robust approach: We store the 'Raw' name in the session state as the 'Target'
                # But wait, the dropdown logic uses the raw name. 
                
                # Finding the raw name in the squad list that maps to this Common Name
                found_raw_name = None
                
                # Get list of squads actually available in the player CSV
                df_clean_check = ap.apply_squad_filters(df_players)
                available_squads = sorted(df_clean_check['Squad'].dropna().unique())
                
                for squad in available_squads:
                    # Check if this squad maps to the clicked common name
                    # We check: Is "Ipswich Town" (squad) -> "Ipswich" (Common)?
                    mapped_common = team_map.get(squad, squad) 
                    if mapped_common == clicked_squad_common:
                        found_raw_name = squad
                        break
                
                if found_raw_name:
                    st.session_state.selected_squad_key = found_raw_name
                    st.session_state.current_view = "🕵️ Manager Deep Dive"
                    st.rerun()
                else:
                    st.toast(f"Data for {clicked_squad_common} not found in player records.", icon="⚠️")
                
            except Exception as e:
                pass

        st.markdown("""
        <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">
            <h4 style="margin-top:0;">Legend</h4>
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
# VIEW 2: MANAGER DEEP DIVE
# ==============================================================================
elif st.session_state.current_view == "🕵️ Manager Deep Dive":
    
    df_clean = ap.apply_squad_filters(df_players)
    squads = sorted(df_clean['Squad'].dropna().unique())
    
    default_index = 0
    if st.session_state.selected_squad_key in squads:
        default_index = squads.index(st.session_state.selected_squad_key)
        if st.button("← Back to League Matrix"):
            st.session_state.current_view = "📊 League Matrix"
            st.rerun()

    col_sel1, col_sel2 = st.columns(2)
    
    def update_squad_selection():
        st.session_state.selected_squad_key = st.session_state.squad_selector

    with col_sel1:
        selected_squad = st.selectbox("Select Squad to Analyze", squads, index=default_index, key="squad_selector", on_change=update_squad_selection)

    df_clean['Age_Group'] = df_clean['Age'].apply(ap.get_age_group)
    df_clean['Pos_Simple'] = df_clean['Pos'].astype(str).apply(lambda x: x.split(',')[0].strip())
    positions = ["All"] + sorted(df_clean['Pos_Simple'].unique().tolist())
    with col_sel2:
        selected_pos = st.selectbox("Filter Position", positions)

    # 1. Get Manager Name (Robust)
    manager_name = manager_map.get(selected_squad, "Unknown Manager")
    
    # 2. Get Matrix Stats (Robust)
    # Translate Raw Name (Dropdown) -> Common Name (Matrix Key)
    squad_common_name = team_map.get(selected_squad, selected_squad)
    mgr_stats = df_matrix[df_matrix['Squad_Common'] == squad_common_name]
    
    st.markdown("---")
    
    h_col1, h_col2, h_col3 = st.columns([2, 1, 1])
    with h_col1:
        st.title(manager_name)
        st.caption(f"Squad: {selected_squad}")
    
    with h_col2:
        if not mgr_stats.empty:
            q = mgr_stats.iloc[0]['Quadrant']
            st.metric("Matrix Quadrant", q)
        else:
            st.metric("Matrix Quadrant", "N/A")
            
    with h_col3:
        if not mgr_stats.empty:
            fi = mgr_stats.iloc[0]['Fair_Index']
            st.metric("Wage Efficiency", f"{fi:+.0f}")
        else:
            st.metric("Wage Efficiency", "N/A")

    st.markdown("---")
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
    if selected_pos != "All":
        df_viz = df_viz[df_viz['Pos_Simple'] == selected_pos]

    metrics_df = ap.calculate_trust_metrics(df_viz)

    if not metrics_df.empty:
        gap_df = metrics_df.pivot(index="Age Group", columns="Metric", values="Percentage").reset_index()
        gap_df["Trust Gap"] = gap_df["Minutes Played (Players Utilization)"] - gap_df["Squad Depth (Available Players)"]
        
        fig_gap = px.bar(
            gap_df,
            x="Trust Gap",
            y="Age Group",
            orientation='h',
            text=gap_df["Trust Gap"].apply(lambda x: f"{x:+.1f}%"),
            color="Trust Gap",
            color_continuous_scale="RdYlGn",
            range_color=[-20, 20], 
            height=400,
            title=f"Who does {manager_name.split(' ')[-1]} trust?"
        )
        fig_gap.add_vline(x=0, line_width=2, line_dash="dash", line_color="black")
        fig_gap.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig_gap, use_container_width=True)

        with st.expander("See Available Squad vs. Minutes Breakdown"):
            fig_bar = px.bar(
                metrics_df, 
                x="Age Group", y="Percentage", color="Metric", barmode="group",
                color_discrete_map={
                    "Squad Depth (Available Players)": "#1f77b4", 
                    "Minutes Played (Players Utilization)": "#d62728"
                },
                text_auto='.1f',
                height=350
            )
            st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.warning("No data available for this selection.")