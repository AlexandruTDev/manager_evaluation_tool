import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from tactical_data_parser import TacticalDataPipeline

# --- CONFIGURATION: NORMALIZATION RANGES ---
METRIC_RANGES = {
    'Possession': (35, 65),       # <35% (Low) to >65% (Domination)
    'Field_Tilt': (20, 80),       # Territorial Dominance
    'Tempo': (9, 15),             # Passes per minute of possession
    'Directness': (5, 25),        # % Long Balls (Lower is "Modern")
    'GK_Long_Pct': (20, 80),      # Intent: Playing out from back
    'Crossing': (10, 25),         # Crosses per 90
    'Press_Intensity': (0.4, 1.0),# Actions per minute of opp possession
    'Def_Line': (10, 30),         # % Tackles in Att 3rd
    'GK_Sweeper': (10, 20),       # Avg Distance (Yards)
    'Aerial_Vol': (20, 45),       # Total Aerials per 90
    'Recoveries': (40, 60),       # Work Rate
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

# [NEW] Tooltip Dictionary for Hover Explanations
TOOLTIPS = {
    'Possession': "Average percentage of time the team controls the ball per match.",
    'Def_Line': "Percentage of defensive actions (tackles, interceptions) made in the attacking third. Proxy for High Press.",
    'Directness': "Percentage of passes classified as Long Balls (>30 yards). Higher = More Direct/Hoofball.",
    'Aerial_Vol': "Total aerial duels contested per 90 minutes. Indicates physical style of play."
}

def normalize_value(value, metric_name):
    """Scales a raw value to 0-100 based on defined ranges."""
    if pd.isna(value): return 50
    if metric_name not in METRIC_RANGES: return 50 
    
    min_val, max_val = METRIC_RANGES[metric_name]
    
    if min_val > max_val: # Handle Inverted Metrics
        true_min, true_max = max_val, min_val
        clipped = max(true_min, min(value, true_max))
        return 100 - ((clipped - true_min) / (true_max - true_min) * 100)
    
    clipped = max(min_val, min(value, max_val))
    return (clipped - min_val) / (max_val - min_val) * 100

def render_radar_chart(active_row, comparison_row=None, title="Tactical Profile"):
    metrics = list(METRIC_RANGES.keys())
    
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

    active_values = get_values(active_row)
    display_labels = [METRIC_LABELS.get(m, m) for m in metrics]
    plot_labels = display_labels + [display_labels[0]]
    
    fig = go.Figure()

    # 1. GHOST TRACE (Career Norm) - Faded Orange
    if comparison_row is not None:
        comp_values = get_values(comparison_row)
        fig.add_trace(go.Scatterpolar(
            r=comp_values,
            theta=plot_labels,
            fill='toself',
            name='Career Average',
            line=dict(color='rgba(243, 156, 18, 0.6)', width=2, dash='longdash'), 
            fillcolor='rgba(243, 156, 18, 0.25)',
            hoverinfo='skip',
            showlegend=True
        ))

    # 2. MAIN TRACE
    fig.add_trace(go.Scatterpolar(
        r=active_values,
        theta=plot_labels,
        fill='toself',
        name=title,
        line=dict(color='#3498db', width=3),
        fillcolor="rgba(52, 152, 219, 0.25)", 
        mode='lines+markers',
        marker=dict(size=6, color='white', line=dict(color='#3498db', width=2))
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], showticklabels=False, tickvals=[25, 50, 75], gridcolor='#e0e0e0'),
            angularaxis=dict(tickfont=dict(size=11, color='#2c3e50', weight="bold"), rotation=0),
            bgcolor='rgba(0,0,0,0)'
        ),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="center", x=0.5),
        height=400,
        margin=dict(l=60, r=60, t=40, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
    )
    return fig

def render_seasonal_heatmap(df_stats):
    df_sorted = df_stats.sort_values('Season', ascending=True)
    seasons = [f"'{s.split('-')[0][-2:]}" for s in df_sorted['Season'].tolist()]
    
    metrics = list(METRIC_LABELS.keys())
    z_values, text_values, custom_data, y_labels = [], [], [], []
    
    for metric_key in metrics:
        if metric_key in df_stats.columns:
            raw_series = df_sorted[metric_key]
            norm_row = [normalize_value(x, metric_key) for x in raw_series]
            z_values.append(norm_row)
            
            is_pct = any(x in metric_key for x in ['Poss', 'Tilt', 'Direct', 'Line', 'Long'])
            fmt = "{:.1f}%" if is_pct else "{:.1f}"
            text_row = [fmt.format(x) for x in raw_series]
            text_values.append(text_row)
            
            row_custom = np.dstack((text_row, norm_row))[0]
            custom_data.append(row_custom)
            y_labels.append(METRIC_LABELS.get(metric_key, metric_key))

    fig = go.Figure(data=go.Heatmap(
        z=z_values, x=seasons, y=y_labels, text=text_values, customdata=custom_data,
        texttemplate="%{text}", textfont={"size": 11}, colorscale="RdBu", 
        zmin=0, zmax=100, showscale=False, ygap=2, xgap=2,
        hovertemplate="<b>%{y}</b><br>Season: %{x}<br>Raw Metric: <b>%{customdata[0]}</b><br>Tactical Rating: %{customdata[1]:.0f}/100<extra></extra>"
    ))

    fig.update_layout(
        title=dict(text="📈 Tactical Evolution Timeline", font=dict(size=16, color="#2c3e50"), x=0, y=0.98),
        height=450, margin=dict(l=0, r=0, t=60, b=20),
        xaxis=dict(side="top", tickfont=dict(size=12, weight='bold')),
        yaxis=dict(autorange="reversed"),
        paper_bgcolor='rgba(0,0,0,0)',
    )
    return fig

def render_manager_tactics(manager_name, current_season=None):
    pipeline = TacticalDataPipeline()
    df_stats = pipeline.get_manager_stats(manager_name)
    
    if df_stats is None or df_stats.empty:
        st.info(f"ℹ️ No historical tactical data configured for {manager_name}.")
        return

    st.markdown(f"### 🧬 Tactical DNA: {manager_name}")
    
    # Career Stats (Baseline for Delta)
    career_stats = df_stats.mean(numeric_only=True)
    
    if current_season:
        season_data = df_stats[df_stats['Season'] == current_season]
        if season_data.empty:
            short_season = current_season.split("-")[0][-2:] 
            season_data = df_stats[df_stats['Season'].str.contains(short_season, na=False)]
        
        if not season_data.empty:
            active_stats = season_data 
            display_stats = season_data.iloc[0] 
            chart_title = f"Profile: {current_season}"
            comparison_stats = df_stats 
        else:
            active_stats = df_stats 
            display_stats = career_stats
            chart_title = "Career Avg"
            comparison_stats = None
    else:
        active_stats = df_stats 
        display_stats = career_stats
        chart_title = "Career Avg"
        comparison_stats = None

    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown(f"#### Style Profile")
        
        # Variance Logic
        variances = []
        style_pillars = ['Possession', 'Directness', 'Def_Line']
        for m in style_pillars:
            if m in df_stats.columns: variances.append(df_stats[m].std())
        
        avg_var = np.nanmean(variances) if variances else 0
        if avg_var < 2.0:
            tag, color, desc = "RIGID IDENTITY", "#e74c3c", "Dogmatic. Plays the same way regardless of squad."
        elif avg_var < 6.0:
            tag, color, desc = "BALANCED", "#f39c12", "Clear principles, but adapts execution to context."
        else:
            tag, color, desc = "CHAMELEON", "#2ecc71", "Highly adaptable. Shape shifts significantly per season."
            
        st.markdown(f"""
            <div style="margin-bottom: 10px;">
                <div style="background-color: {color}20; border: 1px solid {color}; color: {color}; padding: 6px 10px; border-radius: 5px; font-weight: bold; font-size: 0.95em; display: inline-block;">
                    {tag}
                </div>
            </div>
        """, unsafe_allow_html=True)
        st.caption(desc)
        st.divider()
        
        # [NEW] Helper for Metric with Delta & Tooltip
        def render_stat(label, col_key, is_pct=False):
            # 1. Get Values
            curr_val = display_stats[col_key] if col_key in display_stats else 0
            avg_val = career_stats[col_key] if col_key in career_stats else 0
            
            # 2. Format Value
            fmt = "{:.0f}%" if is_pct else "{:.1f}"
            val_str = fmt.format(curr_val)
            
            # 3. Calculate Delta (vs Career)
            # Only show delta if we are looking at a specific season, not the career avg itself
            delta_str = None
            if chart_title != "Career Avg":
                diff = curr_val - avg_val
                # Use string formatting to look like "+2.5% vs Career"
                delta_str = f"{diff:+.1f}{'%' if is_pct else ''} vs Career"

            # 4. Render with st.metric
            st.metric(
                label=label,
                value=val_str,
                delta=delta_str,
                help=TOOLTIPS.get(col_key, "Tactical metric.")
            )

        c1_m, c2_m = st.columns(2)
        with c1_m: render_stat("Avg Possession", 'Possession', True)
        with c2_m: render_stat("High Press %", 'Def_Line', True)
        
        c3_m, c4_m = st.columns(2)
        with c3_m: render_stat("Long Ball %", 'Directness', True)
        with c4_m: render_stat("Aerials/90", 'Aerial_Vol', False)

    with col2:
        fig = render_radar_chart(active_stats, comparison_stats, chart_title) 
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    fig_heat = render_seasonal_heatmap(df_stats)
    st.plotly_chart(fig_heat, use_container_width=True)