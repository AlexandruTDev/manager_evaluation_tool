import pandas as pd
import numpy as np
import os

class TacticalDataPipeline:
    def __init__(self, base_dir="data/raw"):
        self.base_dir = base_dir
        self.map_path = os.path.join(base_dir, "config", "manager_career_map.csv")
        
        # Files required for the 3 Pillars
        self.required_files = {
            "passing": "passing.csv",
            "possession": "possession.csv",
            "defense": "defensive_actions.csv",
            "creation": "shot_creation.csv"
        }

    def _clean_cols(self, df):
        """Standardizes columns to snake_case"""
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('/', '_per_')
        return df

    def get_manager_stats(self, manager_name):
        # 1. READ CONFIG
        if not os.path.exists(self.map_path):
            return print(f"❌ Error: Config file not found at {self.map_path}")
            
        map_df = pd.read_csv(self.map_path)
        history = map_df[map_df['Manager'] == manager_name]
        
        if history.empty:
            return print(f"❌ Manager '{manager_name}' not found in map.")

        season_stats = []

        print(f"\n🕵️ ANALYZING: {manager_name}")
        print(f"{'Season':<10} {'Squad':<15} | {'Build-Up (Short/Mid/Long)':<30} | {'Def (Low/Mid/High)':<30} | {'Trans %':<10}")
        print("-" * 110)

        # 2. ITERATE SEASONS
        for _, row in history.iterrows():
            season = row['Season']
            squad = row['Squad']
            league = row['League']
            
            # Construct path: data/raw/23-24/premier_league/
            league_dir = os.path.join(self.base_dir, season, league)
            
            # Container for single-season data
            s_data = {}
            
            try:
                # 3. LOAD FILES
                for key, filename in self.required_files.items():
                    path = os.path.join(league_dir, filename)
                    if not os.path.exists(path):
                        raise FileNotFoundError(f"Missing {filename}")
                        
                    df = pd.read_csv(path)
                    df = self._clean_cols(df)
                    
                    # Filter for Squad
                    team_row = df[df['squad'] == squad]
                    if team_row.empty:
                        raise ValueError(f"Squad {squad} not found in {filename}")
                        
                    s_data[key] = team_row.iloc[0]

                # 4. CALCULATE PILLARS
                
                # --- Pillar 1: Build-Up (Distribution) ---
                pass_row = s_data['passing']
                total_pass = pass_row['total_att']
                
                if total_pass > 0:
                    short_pct = (pass_row['short_att'] / total_pass) * 100
                    mid_pct   = (pass_row['mid_att'] / total_pass) * 100
                    long_pct  = (pass_row['long_att'] / total_pass) * 100
                else:
                    short_pct = mid_pct = long_pct = 0

                # --- Pillar 2: Defensive Zones (Distribution) ---
                def_row = s_data['defense']
                # Total tackles = Sum of all 3 zones
                total_tkl = def_row['def_3rd'] + def_row['mid_3rd'] + def_row['att_3rd']
                
                if total_tkl > 0:
                    def_low_pct  = (def_row['def_3rd'] / total_tkl) * 100  # Low Block
                    def_mid_pct  = (def_row['mid_3rd'] / total_tkl) * 100  # Mid Block
                    def_high_pct = (def_row['att_3rd'] / total_tkl) * 100  # High Press
                else:
                    def_low_pct = def_mid_pct = def_high_pct = 0
                
                # --- Pillar 3: Transition (Reaction Speed) ---
                # Formula: SCA from Defensive Actions / Total SCA
                # (Measures how often defense turns instantly into attack)
                sca_row = s_data['creation']
                trans_threat = (sca_row['sca_def'] / sca_row['sca']) * 100 if sca_row['sca'] > 0 else 0

                # Print for Validation
                build_str = f"{short_pct:.0f}/{mid_pct:.0f}/{long_pct:.0f}"
                def_str   = f"{def_low_pct:.0f}/{def_mid_pct:.0f}/{def_high_pct:.0f}"
                
                print(f"{season:<10} {squad:<15} | {build_str:<30} | {def_str:<30} | {trans_threat:>8.1f}%")

                season_stats.append({
                    'Season': season,
                    'Build_Short': short_pct,
                    'Build_Mid': mid_pct,
                    'Build_Long': long_pct,
                    'Def_Low': def_low_pct,
                    'Def_Mid': def_mid_pct,
                    'Def_High': def_high_pct,
                    'Transition_Threat': trans_threat
                })

            except Exception as e:
                print(f"{season:<10} {squad:<15} | ❌ Error: {str(e)}")

        # 5. CALCULATE CONSISTENCY (Std Dev)
        if season_stats:
            df_res = pd.DataFrame(season_stats)
            print("-" * 110)
            print("📊 CONSISTENCY REPORT (Standard Deviation - Lower = More Rigid)")
            print(f"Short Passing σ: {df_res['Build_Short'].std():.2f}")
            print(f"High Pressing σ: {df_res['Def_High'].std():.2f}")
            
            return df_res

# --- TEST RUN ---
if __name__ == "__main__":
    pipeline = TacticalDataPipeline()
    # Test with a manager likely to be in your config
    pipeline.get_manager_stats("Sean Dyche")