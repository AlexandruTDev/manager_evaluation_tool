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

def render_radar_chart(df_stats):
    """Generates the Spider/Radar Chart for the Manager's Profile"""
    
    # 1. Calculate Averages across seasons for the Profile Shape
    metrics = list(METRIC_RANGES.keys())
    
    norm_avgs = []
    
    for m in metrics:
        if m in df_stats.columns:
            raw_avg = df_stats[m].mean()
            norm_score = normalize_value(raw_avg, m)
            norm_avgs.append(norm_score)
        else:
            norm_avgs.append(50) # Neutral filler if missing

    # Close the loop for the radar chart (append first to last)
    plot_values = norm_avgs + [norm_avgs[0]]
    plot_labels = metrics + [metrics[0]]
    
    # 2. Build the Chart
    fig = go.Figure()

    # The Profile Shape (Solid Line)
    fig.add_trace(go.Scatterpolar(
        r=plot_values,
        theta=plot_labels,
        fill='toself',
        name='Career Avg',
        line=dict(color='#2ecc71', width=3),
        fillcolor="rgba(46, 204, 113, 0.3)"
    ))

    # Formatting
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                showticklabels=False, # Abstract 0-100 score
                tickmode='array',
                tickvals=[25, 50, 75],
                gridcolor='lightgray'
            ),
            angularaxis=dict(
                tickfont=dict(size=10, color='gray')
            )
        ),
        showlegend=False,
        height=450,
        margin=dict(l=50, r=50, t=30, b=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    return fig

def render_manager_tactics(manager_name):
    """Main function to call inside the dashboard tab"""
    
    # 1. Run Pipeline
    pipeline = TacticalDataPipeline() # Ensure this class is available
    df_stats = pipeline.get_manager_stats(manager_name)
    
    if df_stats is None or df_stats.empty:
        st.info(f"ℹ️ No historical tactical data configured for {manager_name}.")
        st.caption("Please update 'data/raw/config/manager_career_map.csv' to include this manager.")
        return

    st.markdown(f"### 🧬 Tactical DNA: {manager_name}")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # --- A. Summary Card ---
        st.markdown("#### Style Profile")
        
        # Calculate Consistency (Standard Deviation of Normalized Scores)
        # We normalize the variance to see who changes style the most
        variances = []
        for m in METRIC_RANGES.keys():
            if m in df_stats.columns:
                # Calculate std of the raw values
                raw_std = df_stats[m].std()
                # We simply sum raw stds for critical 'Style' metrics to gauge adaptability
                if m in ['Possession', 'GK_Long_Pct', 'Directness', 'Def_Line']:
                    variances.append(raw_std)
        
        # Heuristic for Tagging
        avg_var = np.nanmean(variances) if variances else 0
        
        # Label Logic
        if avg_var < 3.0:
            tag = "🔒 RIGID SYSTEM"
            desc = "Does not change tactics. High Consistency."
            color = "red"
        elif avg_var < 8.0:
            tag = "⚖️ BALANCED"
            desc = "Adapts to league, keeps core principles."
            color = "orange"
        else:
            tag = "🔄 CHAMELEON"
            desc = "Highly adaptable. Changes style per squad."
            color = "green"
            
        st.markdown(f":{color}[**{tag}**]")
        st.caption(desc)
        
        st.divider()
        
        # Quick Stats
        c1, c2 = st.columns(2)
        c1.metric("Possession", f"{df_stats['Possession'].mean():.0f}%")
        c2.metric("Press Height", f"{df_stats['Def_Line'].mean():.0f}%")
        
        c3, c4 = st.columns(2)
        c3.metric("Directness", f"{df_stats['Directness'].mean():.0f}%")
        c4.metric("Aerial Vol", f"{df_stats['Aerial_Vol'].mean():.0f}")

    with col2:
        # --- B. The Radar Chart ---
        fig = render_radar_chart(df_stats)
        st.plotly_chart(fig, use_container_width=True)

    # --- C. The Boardroom Log ---
    with st.expander("📂 View Season-by-Season Data"):
        # Format the dataframe for display
        display_df = df_stats.copy()
        
        # [FIX]: Select only numeric columns for float formatting
        numeric_cols = display_df.select_dtypes(include=['float', 'int']).columns
        
        # Apply formatting ONLY to the numeric subset
        st.dataframe(
            display_df.style.format("{:.1f}", subset=numeric_cols), 
            use_container_width=True
        )