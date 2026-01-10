import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from tactical_data_parser import TacticalDataPipeline

# --- CONFIGURATION: NORMALIZATION RANGES ---
# Defined ranges to scale raw metrics into a 0-100 Score
METRIC_RANGES = {
    'Possession': (35, 65),       # <35% (Low) to >65% (Domination)
    'Field_Tilt': (20, 80),       # Territorial Dominance
    'Tempo': (9, 15),             # Passes per minute of possession
    'Directness': (5, 25),        # % Long Balls (Lower is usually "Modern", Higher is "Direct")
    'GK_Long_Pct': (20, 80),      # Intent: Playing out from back vs Hoofing
    'Crossing': (10, 25),         # Crosses per 90
    'Press_Intensity': (0.4, 1.0),# Actions per minute of opp possession
    'Def_Line': (10, 30),         # % Tackles in Att 3rd (10=Low Block, 30=High Press)
    'GK_Sweeper': (10, 20),       # Avg Distance (Yards)
    'Aerial_Vol': (20, 45),       # Total Aerials per 90 (Physicality)
    'Recoveries': (40, 60),       # Work Rate / Scrappiness
    'Stability': (25, 15)         # INVERTED: 25 Errors (Bad) -> 15 Errors (Good)
}

METRIC_LABELS = {
    'Possession': 'Possession',
    'Field_Tilt': 'Field Tilt',
    'Tempo': 'Tempo',
    'Directness': 'Direct Play',
    'GK_Long_Pct': 'GK Long Kick',
    'Crossing': 'Crossing',
    'Press_Intensity': 'Press Intensity',
    'Def_Line': 'High Line',
    'GK_Sweeper': 'Sweeper Keeper',
    'Aerial_Vol': 'Aerials',
    'Recoveries': 'Recoveries',
    'Stability': 'Stability'
}

def normalize_value(value, metric_name):
    """Scales a raw value to 0-100 based on defined ranges."""
    if pd.isna(value): return 50 # Handle NaNs safely
    
    if metric_name not in METRIC_RANGES:
        return 50 
    
    min_val, max_val = METRIC_RANGES[metric_name]
    
    # Handle Inverted Metrics (e.g. Stability: Lower value is Higher Score)
    if min_val > max_val:
        # Swap for calculation logic
        true_min, true_max = max_val, min_val
        clipped = max(true_min, min(value, true_max))
        # Formula for inverted: 100 - (normalized%)
        return 100 - ((clipped - true_min) / (true_max - true_min) * 100)
    
    # Standard Metrics (Higher value = Higher Score)
    clipped = max(min_val, min(value, max_val))
    return (clipped - min_val) / (max_val - min_val) * 100

def render_radar_chart(active_row, comparison_row=None, title="Tactical Profile"):
    """
    Generates a Professional Radar Chart.
    Args:
        active_row (Series/DF): The main data to display (colored).
        comparison_row (Series/DF): Optional background context.
        title (str): Legend label for the active trace.
    """
    metrics = list(METRIC_RANGES.keys())
    
    # --- HELPER: Data Processing ---
    def get_values(row_data):
        if isinstance(row_data, pd.DataFrame):
            data = row_data.mean(numeric_only=True)
        else:
            data = row_data
            
        values = []
        for m in metrics:
            val = data.get(m, np.nan)
            norm = normalize_value(val, m)
            values.append(norm)
        return values + [values[0]]

    # Process Data
    active_values = get_values(active_row)
    display_labels = [METRIC_LABELS.get(m, m) for m in metrics]
    plot_labels = display_labels + [display_labels[0]]
    
    fig = go.Figure()

    # 1. THE "GHOST" TRACE (Career Reference)
    # [UPDATED]: Now using Faded Amber for better visibility/contrast
    if comparison_row is not None:
        comp_values = get_values(comparison_row)
        fig.add_trace(go.Scatterpolar(
            r=comp_values,
            theta=plot_labels,
            fill='toself',
            name='Career Norm',
            # Amber Style: distinct from blue, warm vs cool contrast
            line=dict(color='rgba(243, 156, 18, 0.6)', width=2, dash='longdash'), 
            fillcolor='rgba(243, 156, 18, 0.25)', # Slightly higher opacity for visibility
            hoverinfo='skip',
            showlegend=True
        ))

    # 2. THE MAIN TRACE (Foreground Season)
    fig.add_trace(go.Scatterpolar(
        r=active_values,
        theta=plot_labels,
        fill='toself',
        name=title,
        # Scouting Blue Style
        line=dict(color='#3498db', width=3),
        fillcolor="rgba(52, 152, 219, 0.3)", 
        mode='lines+markers',
        marker=dict(
            size=6,
            color='white',
            line=dict(color='#3498db', width=2)
        )
    ))

    # 3. PROFESSIONAL LAYOUT
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                showticklabels=False,
                tickmode='array',
                tickvals=[25, 50, 75],
                gridcolor='#d1d5db', # Medium gray grid for structure
                gridwidth=1
            ),
            angularaxis=dict(
                tickfont=dict(size=12, color='black', family="Arial, sans-serif", weight="bold"),
                rotation=0,
                direction="clockwise"
            ),
            bgcolor='rgba(0,0,0,0)'
        ),
        showlegend=True,
        legend=dict(
            orientation="h", 
            yanchor="bottom", y=1.05, 
            xanchor="left", x=0,
            font=dict(size=12)
        ),
        height=450,
        margin=dict(l=80, r=80, t=40, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        dragmode=False
    )
    
    return fig

def render_seasonal_heatmap(df_stats):
    """
    Generates a Heatmap to visualize tactical evolution over seasons.
    Rows = Metrics, Cols = Seasons. Colors = Normalized Score (Intensity).
    """
    # 1. Prepare Data
    # Sort by season desc (newest first) or asc (oldest first)
    df_sorted = df_stats.sort_values('Season', ascending=True)
    
    # [UPDATED]: Rename seasons for display (e.g. "23-24" -> "Season 23-24")
    seasons = [f"Season {s}" for s in df_sorted['Season'].tolist()]
    
    # We only want the relevant metrics
    metrics = list(METRIC_LABELS.keys())
    
    # Lists for Plotly
    z_values = [] # Normalized values for Color
    text_values = [] # Raw values for Display
    y_labels = [] # Metric Names
    
    for metric_key in metrics:
        if metric_key in df_stats.columns:
            # Row Data
            raw_series = df_sorted[metric_key]
            
            # Normalize row for color scaling (0-100)
            norm_row = [normalize_value(x, metric_key) for x in raw_series]
            z_values.append(norm_row)
            
            # Format raw text for the cell
            is_pct = any(x in metric_key for x in ['Poss', 'Tilt', 'Direct', 'Line', 'Long'])
            fmt = "{:.1f}%" if is_pct else "{:.1f}"
            text_row = [fmt.format(x) for x in raw_series]
            text_values.append(text_row)
            
            y_labels.append(METRIC_LABELS.get(metric_key, metric_key))

    # 2. Build Heatmap
    fig = go.Figure(data=go.Heatmap(
        z=z_values,
        x=seasons,
        y=y_labels,
        text=text_values,
        texttemplate="%{text}", 
        textfont={"size": 11}, # Slightly larger text
        colorscale="RdBu", 
        zmin=0, zmax=100, 
        showscale=False, 
        ygap=2, # Increased gap for cleaner look
        xgap=2
    ))

    # 3. Styling
    fig.update_layout(
        title=dict(
            text="📈 Tactical Evolution Timeline", 
            font=dict(size=16, color="#2c3e50"),
            x=0, # Align title left
            y=0.95
        ),
        height=450,
        # [UPDATED]: Increased Top Margin (t=80) to prevent overlap
        margin=dict(l=0, r=0, t=80, b=20),
        xaxis=dict(
            side="top", 
            tickfont=dict(size=12, weight='bold', color="#2c3e50"),
            ticksuffix="  " # Add padding
        ),
        yaxis=dict(
            tickfont=dict(size=12, color="#555"),
            autorange="reversed" # Ensures metrics list top-to-bottom
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    return fig

def render_manager_tactics(manager_name, current_season=None):
    """
    Main function to call inside the dashboard tab.
    Args:
        manager_name (str): Name of the manager to analyze.
        current_season (str): Optional. The season string (e.g., "23-24").
    """
    
    # 1. Run Pipeline
    pipeline = TacticalDataPipeline()
    df_stats = pipeline.get_manager_stats(manager_name)
    
    if df_stats is None or df_stats.empty:
        st.info(f"ℹ️ No historical tactical data configured for {manager_name}.")
        return

    st.markdown(f"### 🧬 Tactical DNA: {manager_name}")
    
    # [UPDATED]: Checkbox removed. Logic simplified.
    # Default: Show specific season (if provided), with Career Average as comparison.
    
    if current_season:
        # Try Exact Match
        season_data = df_stats[df_stats['Season'] == current_season]
        
        # Fallback: Fuzzy Match
        if season_data.empty:
            short_season = current_season.split("-")[0][-2:] 
            season_data = df_stats[df_stats['Season'].str.contains(short_season, na=False)]
        
        if not season_data.empty:
            # Found Season
            active_stats = season_data 
            display_stats = season_data.iloc[0] 
            chart_title = f"Profile: {current_season}"
            
            # Ghost Trace = Career Average (Full DF)
            comparison_stats = df_stats 
        else:
            # Fallback
            active_stats = df_stats 
            display_stats = df_stats.mean(numeric_only=True)
            chart_title = "Career Avg"
            comparison_stats = None # No ghost if we are already showing avg
    else:
        # No season selected (Career Mode)
        active_stats = df_stats 
        display_stats = df_stats.mean(numeric_only=True)
        chart_title = "Career Avg"
        comparison_stats = None

    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # --- A. Summary Card ---
        st.markdown(f"#### Style Profile")
        
        variances = []
        style_pillars = ['Possession', 'Directness', 'Def_Line']
        
        for m in style_pillars:
            if m in df_stats.columns:
                variances.append(df_stats[m].std())
        
        avg_var = np.nanmean(variances) if variances else 0
        
        # Label Logic
        if avg_var < 2.0:
            tag, color, desc = "RIGID", "red", "Unwavering tactical identity. High consistency."
        elif avg_var < 6.0:
            tag, color, desc = "BALANCED", "orange", "Clear principles, but adapts execution to context."
        else:
            tag, color, desc = "VERSATILE", "green", "Highly adaptable. Shape shifts to fit the squad."
            
        st.markdown(f":{color}[**{tag}**]")
        st.caption(desc)
        st.divider()
        
        # 2. QUICK STATS
        def get_stat(col, is_pct=False):
            if col in display_stats:
                val = display_stats[col]
            else:
                val = 0
            fmt = "{:.0f}%" if is_pct else "{:.0f}"
            return fmt.format(val)

        c1_m, c2_m = st.columns(2)
        c1_m.metric("Avg Possession", get_stat('Possession', True), help="Avg % possession per game.")
        c2_m.metric("High Press %", get_stat('Def_Line', True), help="% of defensive actions in the attacking 3rd.")
        
        c3_m, c4_m = st.columns(2)
        c3_m.metric("Long Ball %", get_stat('Directness', True), help="% of passes longer than 30 yards.")
        c4_m.metric("Aerial Duels/90", get_stat('Aerial_Vol', False), help="Total aerial duels per 90.")

    with col2:
        # --- B. The Radar Chart ---
        fig = render_radar_chart(active_stats, comparison_stats, chart_title) 
        st.plotly_chart(fig, use_container_width=True)

    # --- C. The Evolution Heatmap (Replaces Table) ---
    st.markdown("---")
    # [UPDATED]: Heatmap Visual
    fig_heat = render_seasonal_heatmap(df_stats)
    st.plotly_chart(fig_heat, use_container_width=True)