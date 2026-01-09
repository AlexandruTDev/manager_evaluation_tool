import pandas as pd
import numpy as np
import os

class TacticalDataPipeline:
    def __init__(self, base_dir="data/raw"):
        self.base_dir = base_dir
        self.map_path = os.path.join(base_dir, "config", "manager_career_map.csv")
        
        self.required_files = {
            "passing": "passing.csv",
            "possession": "possession.csv",
            "defense": "defensive_actions.csv",
            "creation": "shot_creation.csv",
            "misc": "miscellaneous.csv",
            "standard": "standard_stats.csv",
            "gk": "advanced_goalkeeping.csv"
        }

    def _clean_cols(self, df):
        df.columns = (df.columns.str.strip()
                      .str.lower()
                      .str.replace(' ', '_')
                      .str.replace('/', '_per_')
                      .str.replace('%', '_pct')
                      .str.replace('#', '')
                      .str.replace('+', '_plus_')
                      .str.replace('-', '_minus_'))
        return df

    def get_manager_stats(self, manager_name):
        if not os.path.exists(self.map_path):
            return print(f"❌ Error: Config file not found at {self.map_path}")
            
        map_df = pd.read_csv(self.map_path)
        history = map_df[map_df['Manager'] == manager_name]
        
        if history.empty:
            return print(f"❌ Manager '{manager_name}' not found in map.")

        season_stats = []

        print(f"\n🕵️ ANALYZING: {manager_name}")
        # [UPDATED]: Full Header
        header = (
            f"{'Season':<8} | {'Poss%':<5} | {'Tilt%':<5} | {'Tempo':<5} | "
            f"{'Direct%':<7} | {'GKLong%':<7} | {'Cross':<5} | "
            f"{'Press':<5} | {'Line%':<5} | {'Sweeper':<7} | "
            f"{'Aerial':<6} | {'Recov':<5} | {'Stab':<5}"
        )
        print(header)
        print("-" * len(header))

        for _, row in history.iterrows():
            season = row['Season']
            squad = row['Squad']
            league = row['League']
            
            league_dir = os.path.join(self.base_dir, season, league)
            s_data = {}
            
            try:
                for key, filename in self.required_files.items():
                    path = os.path.join(league_dir, filename)
                    if not os.path.exists(path):
                        if key in ["misc", "gk"]: 
                            s_data[key] = None
                            continue
                        raise FileNotFoundError(f"Missing {filename}")
                    
                    df = pd.read_csv(path)
                    df = self._clean_cols(df)
                    team_row = df[df['squad'] == squad]
                    if team_row.empty: raise ValueError(f"Squad {squad} not found")
                    s_data[key] = team_row.iloc[0]

                # --- CALCULATIONS ---
                
                # 1. Possession
                poss = s_data['standard']['poss']

                # 2. Field Tilt
                p_row = s_data['possession']
                field_tilt = (p_row['att_3rd'] / p_row['touches']) * 100

                # 3. Tempo
                pass_row = s_data['passing']
                poss_min = 90 * (poss / 100)
                tempo = pass_row['total_att'] / poss_min if poss_min > 0 else 0

                # 4. Directness (Field)
                directness = (pass_row['long_att'] / pass_row['total_att']) * 100

                # 5. GK Long % & 9. GK Sweeper
                gk_row = s_data.get('gk')
                if gk_row is not None:
                    gk_long = gk_row['goal_kick_launch_pct']
                    gk_sweep = gk_row['avgdist']
                else:
                    gk_long = 0; gk_sweep = 0

                # 6. Crossing, 10. Aerial, 11. Recoveries
                m_row = s_data.get('misc')
                if m_row is not None:
                    crossing = m_row['crs']
                    aerial = m_row['aerial_won'] + m_row['aerial_lost']
                    recov = m_row['recov']
                else:
                    crossing = 0; aerial = 0; recov = 0

                # 7. Press Intensity
                d_row = s_data['defense']
                opp_min = 90 * ((100 - poss) / 100)
                acts = d_row['tkl'] + d_row['int']
                press = acts / opp_min if opp_min > 0 else 0

                # 8. Defensive Line
                tkl_tot = d_row['def_3rd'] + d_row['mid_3rd'] + d_row['att_3rd']
                def_line = (d_row['att_3rd'] / tkl_tot) * 100 if tkl_tot > 0 else 0

                # 12. Stability
                stab = p_row['carries_mis'] + p_row['carries_dis']

                # PRINT ROW
                row_str = (
                    f"{season:<8} | {poss:>5.1f} | {field_tilt:>5.1f} | {tempo:>5.1f} | "
                    f"{directness:>7.1f} | {gk_long:>7.1f} | {crossing:>5.1f} | "
                    f"{press:>5.1f} | {def_line:>5.1f} | {gk_sweep:>7.1f} | "
                    f"{aerial:>6.1f} | {recov:>5.1f} | {stab:>5.1f}"
                )
                print(row_str)

                season_stats.append({
                    'Season': season,
                    'Possession': poss,
                    'Field_Tilt': field_tilt,
                    'Tempo': tempo,
                    'Directness': directness,
                    'GK_Long_Pct': gk_long,
                    'Crossing': crossing,
                    'Press_Intensity': press,
                    'Def_Line': def_line,
                    'GK_Sweeper': gk_sweep,
                    'Aerial_Vol': aerial,
                    'Recoveries': recov,
                    'Stability': stab
                })

            except Exception as e:
                print(f"{season:<8} | ❌ Error: {str(e)}")

        return pd.DataFrame(season_stats)

if __name__ == "__main__":
    TacticalDataPipeline().get_manager_stats("Rúben Amorim")