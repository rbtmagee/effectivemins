import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os

st.set_page_config(page_title="EffectiveMins Tracker", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0b1118; }
    h1, h2, h3 { color: #00d2ff; }
    div[data-testid="stMetricValue"] { color: #00d2ff; }
    </style>
""", unsafe_allow_html=True)

DATA_FILE = "effective_mins_data.csv"

# --- HELPER FUNCTIONS FOR TIME CONVERSION ---
def time_to_seconds(val: str) -> int:
    """Converts MM:SS or M:SS string to integer seconds."""
    if not val or ":" not in str(val):
        return 0
    try:
        parts = str(val).strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return 0

def seconds_to_time(seconds: int) -> str:
    """Converts integer seconds back into MM:SS format."""
    m, s = divmod(int(round(seconds)), 60)
    return f"{m:02d}:{s:02d}"

# --- INITIALISE OR LOAD DATABASE ---
MATCH_COLUMNS = [
    "Gameweek", "Home Team", "Away Team", 
    "Actual In-Play", "Total Match Time", "VAR Checks", "Game Stops", "Longest In-Play",
    "Announced Added", "Actual Added", "Played Added",
    "Home Goal Kicks", "Away Goal Kicks",
    "Home Free Kicks", "Away Free Kicks",
    "Home Throw Ins", "Away Throw Ins",
    "Home Corners", "Away Corners",
    "Home Other", "Away Other",
    "Home Total Wasted", "Away Total Wasted"
]

if os.path.exists(DATA_FILE):
    raw_df = pd.read_csv(DATA_FILE)
    st.session_state.match_log = raw_df
else:
    st.session_state.match_log = pd.DataFrame(columns=MATCH_COLUMNS)

st.title("⏱️ EffectiveMins: Premier League Stoppage Tracker")

# --- DATA ENTRY FORM (ALL 365SCORES FIELDS) ---
with st.expander("➕ Log New Match from 365Scores", expanded=st.session_state.match_log.empty):
    with st.form("manual_entry_form", clear_on_submit=True):
        st.subheader("1. Match Details")
        c1, c2, c3 = st.columns(3)
        with c1:
            gameweek = st.number_input("Gameweek", min_value=1, max_value=38, step=1, value=1)
        with c2:
            home_team = st.text_input("Home Team (e.g. Arsenal)")
        with c3:
            away_team = st.text_input("Away Team (e.g. Wolves)")

        st.subheader("2. Overall Match In-Play & Stoppages")
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            actual_in_play = st.text_input("Actual In-Play (MM:SS)", placeholder="57:29")
        with m2:
            total_time = st.text_input("Total Match Time (MM:SS)", placeholder="99:01")
        with m3:
            var_checks = st.text_input("Significant VAR Checks", placeholder="02:30")
        with m4:
            game_stops = st.number_input("Game Stops (Count)", min_value=0, step=1, value=0)
        with m5:
            longest_in_play = st.text_input("Longest In-Play", placeholder="03:50")

        st.subheader("3. Added Time Breakdown")
        a1, a2, a3 = st.columns(3)
        with a1:
            announced_added = st.text_input("Announced (MM:SS)", placeholder="08:00")
        with a2:
            actual_added = st.text_input("Actual Added (MM:SS)", placeholder="09:01")
        with a3:
            played_added = st.text_input("Played (MM:SS)", placeholder="06:33")

        st.subheader("4. Time Wasted Breakdown (Home vs Away)")
        st.caption("Enter the exact splits shown on the 365scores graphic")
        
        tw1, tw2, tw3, tw4, tw5, tw6 = st.columns(6)
        with tw1:
            st.markdown("**Goal Kicks**")
            h_gk = st.text_input("Home GK", placeholder="01:13")
            a_gk = st.text_input("Away GK", placeholder="05:45")
        with tw2:
            st.markdown("**Free Kicks**")
            h_fk = st.text_input("Home FK", placeholder="04:06")
            a_fk = st.text_input("Away FK", placeholder="10:32")
        with tw3:
            st.markdown("**Throw Ins**")
            h_ti = st.text_input("Home TI", placeholder="02:49")
            a_ti = st.text_input("Away TI", placeholder="06:06")
        with tw4:
            st.markdown("**Corners**")
            h_co = st.text_input("Home Corner", placeholder="01:24")
            a_co = st.text_input("Away Corner", placeholder="02:50")
        with tw5:
            st.markdown("**Other**")
            h_ot = st.text_input("Home Other", placeholder="02:33")
            a_ot = st.text_input("Away Other", placeholder="03:30")
        with tw6:
            st.markdown("**Total Wasted**")
            h_tot = st.text_input("Home Total", placeholder="12:05")
            a_tot = st.text_input("Away Total", placeholder="28:43")

        submitted = st.form_submit_button("Save Match Record")

        if submitted:
            if not home_team or not away_team:
                st.error("Please provide both Home and Away team names.")
            else:
                new_row = {
                    "Gameweek": int(gameweek),
                    "Home Team": home_team.strip(),
                    "Away Team": away_team.strip(),
                    "Actual In-Play": actual_in_play,
                    "Total Match Time": total_time,
                    "VAR Checks": var_checks,
                    "Game Stops": int(game_stops),
                    "Longest In-Play": longest_in_play,
                    "Announced Added": announced_added,
                    "Actual Added": actual_added,
                    "Played Added": played_added,
                    "Home Goal Kicks": h_gk,
                    "Away Goal Kicks": a_gk,
                    "Home Free Kicks": h_fk,
                    "Away Free Kicks": a_fk,
                    "Home Throw Ins": h_ti,
                    "Away Throw Ins": a_ti,
                    "Home Corners": h_co,
                    "Away Corners": a_co,
                    "Home Other": h_ot,
                    "Away Other": a_ot,
                    "Home Total Wasted": h_tot,
                    "Away Total Wasted": a_tot
                }
                st.session_state.match_log = pd.concat(
                    [st.session_state.match_log, pd.DataFrame([new_row])], 
                    ignore_index=True
                )
                st.session_state.match_log.to_csv(DATA_FILE, index=False)
                st.success(f"Saved {home_team} vs {away_team} successfully!")
                st.rerun()

st.divider()

# --- DISPLAY OPTIONS: LEAGUE TABLE VS MATCH LOG ---
if st.session_state.match_log.empty:
    st.info("No match data logged yet. Use the form above to add your first match.")
else:
    tab_standings, tab_matches = st.tabs(["🏆 Team Standings (Averages)", "📋 Raw Match Log"])

    # --- TAB 1: TEAM STANDINGS ---
    with tab_standings:
        # Build individual team rows
        records = []
        for _, r in st.session_state.match_log.iterrows():
            # Home Entry
            records.append({
                "Team": r["Home Team"],
                "Actual In-Play Sec": time_to_seconds(r["Actual In-Play"]),
                "Total Match Sec": time_to_seconds(r["Total Match Time"]),
                "Goal Kicks Sec": time_to_seconds(r["Home Goal Kicks"]),
                "Free Kicks Sec": time_to_seconds(r["Home Free Kicks"]),
                "Throw Ins Sec": time_to_seconds(r["Home Throw Ins"]),
                "Corners Sec": time_to_seconds(r["Home Corners"]),
                "Other Sec": time_to_seconds(r["Home Other"]),
                "Total Wasted Sec": time_to_seconds(r["Home Total Wasted"])
            })
            # Away Entry
            records.append({
                "Team": r["Away Team"],
                "Actual In-Play Sec": time_to_seconds(r["Actual In-Play"]),
                "Total Match Sec": time_to_seconds(r["Total Match Time"]),
                "Goal Kicks Sec": time_to_seconds(r["Away Goal Kicks"]),
                "Free Kicks Sec": time_to_seconds(r["Away Free Kicks"]),
                "Throw Ins Sec": time_to_seconds(r["Away Throw Ins"]),
                "Corners Sec": time_to_seconds(r["Away Corners"]),
                "Other Sec": time_to_seconds(r["Away Other"]),
                "Total Wasted Sec": time_to_seconds(r["Away Total Wasted"])
            })

        df_calc = pd.DataFrame(records)
        grouped = df_calc.groupby("Team").mean().reset_index()
        counts = df_calc.groupby("Team").size().reset_index(name="Matches")
        team_table = pd.merge(counts, grouped, on="Team")

        # Derive readable figures
        team_table["Effective In-Play %"] = (
            (team_table["Actual In-Play Sec"] / team_table["Total Match Sec"].replace(0, 1)) * 100
        ).round(1)
        team_table["Avg In-Play"] = team_table["Actual In-Play Sec"].apply(seconds_to_time)
        team_table["Avg Goal Kicks Delay"] = team_table["Goal Kicks Sec"].apply(seconds_to_time)
        team_table["Avg Free Kicks Delay"] = team_table["Free Kicks Sec"].apply(seconds_to_time)
        team_table["Avg Throw Ins Delay"] = team_table["Throw Ins Sec"].apply(seconds_to_time)
        team_table["Avg Corners Delay"] = team_table["Corners Sec"].apply(seconds_to_time)
        team_table["Avg Other Delay"] = team_table["Other Sec"].apply(seconds_to_time)
        team_table["Avg Total Wasted"] = team_table["Total Wasted Sec"].apply(seconds_to_time)

        # Sorting selection
        sort_choice = st.selectbox(
            "Sort Table By:",
            [
                ("Total Wasted Sec", "Avg Total Wasted (Highest First)", False),
                ("Goal Kicks Sec", "Goal Kicks Delay (Highest First)", False),
                ("Free Kicks Sec", "Free Kicks Delay (Highest First)", False),
                ("Throw Ins Sec", "Throw Ins Delay (Highest First)", False),
                ("Corners Sec", "Corners Delay (Highest First)", False),
                ("Effective In-Play %", "Effective In-Play % (Lowest First)", True),
            ],
            format_func=lambda x: x[1]
        )

        team_table = team_table.sort_values(by=sort_choice[0], ascending=sort_choice[2])

        # Clean display table
        display_columns = [
            "Team", "Matches", "Effective In-Play %", "Avg In-Play",
            "Avg Total Wasted", "Avg Free Kicks Delay", "Avg Goal Kicks Delay", 
            "Avg Throw Ins Delay", "Avg Corners Delay", "Avg Other Delay"
        ]
        st.dataframe(team_table[display_columns], use_container_width=True, hide_index=True)

        st.divider()

        # --- TWITTER GRAPHIC GENERATOR ---
        st.subheader("Generate X Card (@EffectiveMins)")
        selected_team = st.selectbox("Select Team for Graphic", team_table["Team"])
        t_row = team_table[team_table["Team"] == selected_team].iloc[0]

        cg1, cg2 = st.columns([1.2, 1])
        with cg1:
            fig, ax = plt.subplots(figsize=(10, 5.5), facecolor="#0e1621")
            ax.set_facecolor("#0e1621")

            categories = ["Free Kicks", "Goal Kicks", "Throw Ins", "Corners", "Other"]
            durations = [
                t_row["Free Kicks Sec"] / 60.0,
                t_row["Goal Kicks Sec"] / 60.0,
                t_row["Throw Ins Sec"] / 60.0,
                t_row["Corners Sec"] / 60.0,
                t_row["Other Sec"] / 60.0,
            ]

            bars = ax.barh(categories, durations, color="#00d2ff", edgecolor="#ffffff", height=0.55)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_color('#888888')
            ax.spines['left'].set_color('#888888')
            ax.tick_params(colors='#ffffff', labelsize=11)
            ax.set_xlabel("Average Minutes Lost per Match", color="#ffffff", fontsize=11)
            ax.set_title(f"{selected_team.upper()} — Dead-Ball Delay Breakdown", color="#ffffff", fontsize=15, weight="bold", pad=15)
            fig.text(0.82, 0.02, "@EffectiveMins", color="#888888", fontsize=10, style='italic')

            st.pyplot(fig)

        with cg2:
            st.markdown("### Ready-to-Post Copy")
            tweet_text = f"""⏱️ Stoppage Breakdown: {selected_team}

• Effective Playing Time: {t_row['Effective In-Play %']}% ({t_row['Avg In-Play']})
• Average Time Lost: {t_row['Avg Total Wasted']} per 90

Biggest delay factors:
1. Free Kicks: {t_row['Avg Free Kicks Delay']}
2. Goal Kicks: {t_row['Avg Goal Kicks Delay']}
3. Throw Ins: {t_row['Avg Throw Ins Delay']}

Data tracked by @EffectiveMins #PremierLeague #PL"""
            st.text_area("Draft Post", value=tweet_text, height=200)

    # --- TAB 2: RAW MATCH LOG ---
    with tab_matches:
        st.dataframe(st.session_state.match_log, use_container_width=True)
        
        # Download button to back up CSV
        csv_bytes = st.session_state.match_log.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Match Log (CSV)",
            data=csv_bytes,
            file_name="effective_mins_export.csv",
            mime="text/csv"
        )
