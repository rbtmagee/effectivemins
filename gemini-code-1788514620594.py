import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os
import io
import re
import html

st.set_page_config(page_title="EffectiveMins Tracker", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0b1118; }
    h1, h2, h3 { color: #00d2ff; }
    div[data-testid="stMetricValue"] { color: #00d2ff; }
    </style>
""", unsafe_allow_html=True)

DATA_FILE = "effective_mins_data.csv"

CLUB_BADGES = {
    "Arsenal": "https://resources.premierleague.com/premierleague/badges/t3.png",
    "Aston Villa": "https://resources.premierleague.com/premierleague/badges/t7.png",
    "Bournemouth": "https://resources.premierleague.com/premierleague/badges/t91.png",
    "Brentford": "https://resources.premierleague.com/premierleague/badges/t94.png",
    "Brighton": "https://resources.premierleague.com/premierleague/badges/t36.png",
    "Chelsea": "https://resources.premierleague.com/premierleague/badges/t8.png",
    "Coventry City": "https://resources.premierleague.com/premierleague/badges/t9.png",
    "Crystal Palace": "https://resources.premierleague.com/premierleague/badges/t31.png",
    "Everton": "https://resources.premierleague.com/premierleague/badges/t11.png",
    "Fulham": "https://resources.premierleague.com/premierleague/badges/t54.png",
    "Hull City": "https://resources.premierleague.com/premierleague/badges/t88.png",
    "Ipswich Town": "https://resources.premierleague.com/premierleague/badges/t40.png",
    "Leeds United": "https://resources.premierleague.com/premierleague/badges/t2.png",
    "Liverpool": "https://resources.premierleague.com/premierleague/badges/t14.png",
    "Manchester City": "https://resources.premierleague.com/premierleague/badges/t43.png",
    "Manchester United": "https://resources.premierleague.com/premierleague/badges/t1.png",
    "Newcastle United": "https://resources.premierleague.com/premierleague/badges/t4.png",
    "Nottingham Forest": "https://resources.premierleague.com/premierleague/badges/t17.png",
    "Sunderland": "https://resources.premierleague.com/premierleague/badges/t56.png",
    "Tottenham": "https://resources.premierleague.com/premierleague/badges/t6.png"
}

ALL_KNOWN_TEAMS = sorted(list(CLUB_BADGES.keys()))

MATCH_COLUMNS = [
    "Competition", "Gameweek", "Home Team", "Away Team",
    "Actual In-Play", "Total Match Time", "VAR Checks", "Game Stops", "Longest In-Play",
    "Announced Added", "Actual Added", "Played Added",
    "Home Goal Kicks", "Away Goal Kicks",
    "Home Free Kicks", "Away Free Kicks",
    "Home Throw Ins", "Away Throw Ins",
    "Home Corners", "Away Corners",
    "Home Other", "Away Other",
    "Home Total Wasted", "Away Total Wasted",
    "Home Possession", "Away Possession",
    "Home xG", "Away xG",
    "Home xGOT", "Away xGOT",
    "Home Total Shots", "Away Total Shots",
    "Home Shots On Target", "Away Shots On Target",
    "Home Shots Inside Box", "Away Shots Inside Box",
    "Home Passes Opp Half", "Away Passes Opp Half",
    "Home Passes Final Third", "Away Passes Final Third",
    "Home Key Passes", "Away Key Passes",
    "Home Final Third Won", "Away Final Third Won",
    "Home Possession Lost", "Away Possession Lost",
    "Home Fouls", "Away Fouls",
    "Home Yellow Cards", "Away Yellow Cards",
    "Home Red Cards", "Away Red Cards"
]

def clean_val(val, default="00:00") -> str:
    if pd.isna(val) or val is None:
        return default
    s = str(val).strip().replace("–", "-").replace("—", "-")
    return s if s else default

def to_float(val, default=0.0) -> float:
    try:
        s = str(val).replace("%", "").strip()
        return float(s)
    except (ValueError, TypeError):
        return default

def time_to_seconds(val: str) -> int:
    s_val = clean_val(val)
    if ":" not in s_val or s_val.startswith("-"):
        return 0
    try:
        parts = s_val.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return 0

def seconds_to_time(seconds: int) -> str:
    m, s = divmod(int(round(seconds)), 60)
    return f"{m:02d}:{s:02d}"

if os.path.exists(DATA_FILE):
    try:
        st.session_state.match_log = pd.read_csv(DATA_FILE, encoding="utf-8")
    except Exception:
        st.session_state.match_log = pd.read_csv(DATA_FILE, encoding="latin1")
else:
    st.session_state.match_log = pd.DataFrame(columns=MATCH_COLUMNS)

if "Competition" not in st.session_state.match_log.columns:
    st.session_state.match_log.insert(0, "Competition", "Premier League")

st.session_state.match_log["Competition"] = (
    st.session_state.match_log["Competition"]
    .fillna("Premier League")
    .replace("", "Premier League")
)

for col in MATCH_COLUMNS:
    if col not in st.session_state.match_log.columns:
        if any(term in col for term in ["xG", "xGOT"]):
            st.session_state.match_log[col] = "0.00"
        elif any(term in col for term in ["Shots", "Passes", "Won", "Lost", "Fouls", "Cards"]):
            st.session_state.match_log[col] = "0"
        elif "Possession" in col:
            st.session_state.match_log[col] = "50%"
        elif any(term in col for term in ["Time", "In-Play", "Added", "Wasted"]):
            st.session_state.match_log[col] = "00:00"
        else:
            st.session_state.match_log[col] = 0

st.title("⏱️ EffectiveMins: Football Analytics Engine")

with st.sidebar:
    st.header("🏆 Competition Filter")
    active_competition = st.radio(
        "Active Dashboard:",
        ["Premier League", "Champions League", "All Competitions"],
        index=0
    )
    st.divider()
    st.write(f"Total Logged Fixtures: `{len(st.session_state.match_log)}`")

if active_competition == "All Competitions":
    active_df = st.session_state.match_log.copy()
else:
    active_df = st.session_state.match_log[st.session_state.match_log["Competition"] == active_competition].copy()

if active_df.empty:
    st.info(f"No fixtures recorded for **{active_competition}** yet.")
else:
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        f"🏆 {active_competition} Standings",
        "🎯 Control, xG & Territory",
        "🌊 Flow & Disruption",
        "⏱️ Added Time Integrity",
        "📺 VAR Stoppage Impact",
        "📝 Live Spreadsheet Editor & Export"
    ])

    with tab1:
        unique_logged_teams = sorted(set(active_df["Home Team"]).union(set(active_df["Away Team"])))
        standings_rows = []

        for team in unique_logged_teams:
            h_matches = active_df[active_df["Home Team"] == team]
            a_matches = active_df[active_df["Away Team"] == team]

            h_count = len(h_matches)
            a_count = len(a_matches)
            total_matches = h_count + a_count
            if total_matches == 0:
                continue

            h_inplay = h_matches["Actual In-Play"].apply(time_to_seconds).sum()
            a_inplay = a_matches["Actual In-Play"].apply(time_to_seconds).sum()
            total_inplay = h_inplay + a_inplay

            h_tot_time = h_matches["Total Match Time"].apply(time_to_seconds).sum()
            a_tot_time = a_matches["Total Match Time"].apply(time_to_seconds).sum()
            total_match_time = h_tot_time + a_tot_time

            h_wasted = h_matches["Home Total Wasted"].apply(time_to_seconds).sum()
            a_wasted = a_matches["Away Total Wasted"].apply(time_to_seconds).sum()
            total_wasted = h_wasted + a_wasted

            gk_sec = h_matches["Home Goal Kicks"].apply(time_to_seconds).sum() + a_matches["Away Goal Kicks"].apply(time_to_seconds).sum()
            fk_sec = h_matches["Home Free Kicks"].apply(time_to_seconds).sum() + a_matches["Away Free Kicks"].apply(time_to_seconds).sum()
            ti_sec = h_matches["Home Throw Ins"].apply(time_to_seconds).sum() + a_matches["Away Throw Ins"].apply(time_to_seconds).sum()
            cor_sec = h_matches["Home Corners"].apply(time_to_seconds).sum() + a_matches["Away Corners"].apply(time_to_seconds).sum()
            oth_sec = h_matches["Home Other"].apply(time_to_seconds).sum() + a_matches["Away Other"].apply(time_to_seconds).sum()

            all_team_matches = pd.concat([h_matches, a_matches])
            total_stops = all_team_matches["Game Stops"].astype(int).sum()

            avg_home_wasted_sec = h_wasted / h_count if h_count > 0 else 0
            avg_away_wasted_sec = a_wasted / a_count if a_count > 0 else 0

            standings_rows.append({
                "Team": team,
                "Badge": CLUB_BADGES.get(team, ""),
                "Matches": total_matches,
                "Home_Matches": h_count,
                "Away_Matches": a_count,
                "Total_Stops": total_stops,
                "Avg_Stops": round(total_stops / total_matches, 1),
                "InPlay_Sec": total_inplay / total_matches,
                "Total_Sec": total_match_time / total_matches,
                "TotalWasted_Sec": total_wasted / total_matches,
                "HomeWasted_Sec": avg_home_wasted_sec,
                "AwayWasted_Sec": avg_away_wasted_sec,
                "GoalKicks_Sec": gk_sec / total_matches,
                "FreeKicks_Sec": fk_sec / total_matches,
                "ThrowIns_Sec": ti_sec / total_matches,
                "Corners_Sec": cor_sec / total_matches,
                "Other_Sec": oth_sec / total_matches,
            })

        standings = pd.DataFrame(standings_rows)

        standings["Effective In-Play %"] = ((standings["InPlay_Sec"] / standings["Total_Sec"].replace(0, 1)) * 100).round(1)
        standings["Avg In-Play"] = standings["InPlay_Sec"].apply(seconds_to_time)
        standings["Avg Total Wasted"] = standings["TotalWasted_Sec"].apply(seconds_to_time)
        standings["Avg Home Wasted"] = standings.apply(lambda r: seconds_to_time(r["HomeWasted_Sec"]) if r["Home_Matches"] > 0 else "—", axis=1)
        standings["Avg Away Wasted"] = standings.apply(lambda r: seconds_to_time(r["AwayWasted_Sec"]) if r["Away_Matches"] > 0 else "—", axis=1)
        standings["Avg Free Kicks Delay"] = standings["FreeKicks_Sec"].apply(seconds_to_time)
        standings["Avg Goal Kicks Delay"] = standings["GoalKicks_Sec"].apply(seconds_to_time)
        standings["Avg Throw Ins Delay"] = standings["ThrowIns_Sec"].apply(seconds_to_time)
        standings["Avg Corners Delay"] = standings["Corners_Sec"].apply(seconds_to_time)
        standings["Avg Other Delay"] = standings["Other_Sec"].apply(seconds_to_time)

        sort_mode = st.selectbox(
            "Sort Standings By:",
            [
                ("TotalWasted_Sec", "Total Delay (Highest First)", False),
                ("HomeWasted_Sec", "Avg Home Wasted (Highest First)", False),
                ("AwayWasted_Sec", "Avg Away Wasted (Highest First)", False),
                ("Effective In-Play %", "Effective In-Play % (Lowest First)", True)
            ],
            format_func=lambda x: x[1]
        )

        standings = standings.sort_values(by=sort_mode[0], ascending=sort_mode[2])

        display_cols = [
            "Badge", "Team", "Matches", "Effective In-Play %", "Avg In-Play",
            "Avg Total Wasted", "Avg Home Wasted", "Avg Away Wasted",
            "Avg Free Kicks Delay", "Avg Goal Kicks Delay",
            "Avg Throw Ins Delay", "Avg Corners Delay", "Avg Other Delay"
        ]

        st.dataframe(
            standings[display_cols],
            use_container_width=True,
            hide_index=True,
            column_config={"Badge": st.column_config.ImageColumn("Badge", width="small")}
        )

    with tab2:
        st.subheader("🎯 Match Control, xG & Pressing Performance")
        adv_rows = []
        for team in unique_logged_teams:
            h_m = active_df[active_df["Home Team"] == team]
            a_m = active_df[active_df["Away Team"] == team]
            t_count = len(h_m) + len(a_m)
            if t_count == 0:
                continue

            xg_tot = h_m["Home xG"].apply(to_float).sum() + a_m["Away xG"].apply(to_float).sum()
            xgot_tot = h_m["Home xGOT"].apply(to_float).sum() + a_m["Away xGOT"].apply(to_float).sum()
            sot_tot = h_m["Home Shots On Target"].apply(to_float).sum() + a_m["Away Shots On Target"].apply(to_float).sum()
            box_tot = h_m["Home Shots Inside Box"].apply(to_float).sum() + a_m["Away Shots Inside Box"].apply(to_float).sum()
            ft_pass_tot = h_m["Home Passes Final Third"].apply(to_float).sum() + a_m["Away Passes Final Third"].apply(to_float).sum()
            ft_won_tot = h_m["Home Final Third Won"].apply(to_float).sum() + a_m["Away Final Third Won"].apply(to_float).sum()
            fouls_tot = h_m["Home Fouls"].apply(to_float).sum() + a_m["Away Fouls"].apply(to_float).sum()

            adv_rows.append({
                "Badge": CLUB_BADGES.get(team, ""),
                "Team": team,
                "Matches": t_count,
                "Avg xG / 90": round(xg_tot / t_count, 2),
                "Avg xGOT / 90": round(xgot_tot / t_count, 2),
                "Shots on Target / 90": round(sot_tot / t_count, 1),
                "Box Shots / 90": round(box_tot / t_count, 1),
                "Final Third Entries / 90": round(ft_pass_tot / t_count, 1),
                "High Turnovers Won / 90": round(ft_won_tot / t_count, 1),
                "Fouls Committed / 90": round(fouls_tot / t_count, 1),
            })

        df_adv = pd.DataFrame(adv_rows).sort_values(by="Avg xG / 90", ascending=False)
        st.dataframe(
            df_adv,
            use_container_width=True,
            hide_index=True,
            column_config={"Badge": st.column_config.ImageColumn("Badge", width="small")}
        )

    with tab3:
        st.subheader("🌊 Whistle Disruptions & Match Flow")
        df_flow = active_df.copy()
        df_flow["Total_Sec"] = df_flow["Total Match Time"].apply(time_to_seconds)
        df_flow["Stops"] = df_flow["Game Stops"].astype(int)
        df_flow["Match"] = df_flow["Home Team"] + " vs " + df_flow["Away Team"]
        df_flow["Seconds Per Whistle"] = (df_flow["Total_Sec"] / df_flow["Stops"].replace(0, 1)).round(1)

        st.dataframe(
            df_flow[["Gameweek", "Match", "Stops", "Seconds Per Whistle", "Actual In-Play", "Longest In-Play"]].sort_values(by="Stops", ascending=False),
            use_container_width=True,
            hide_index=True
        )

    with tab4:
        st.subheader("⏱️ Added Time Integrity")
        df_at = active_df.copy()
        df_at["Ann_Sec"] = df_at["Announced Added"].apply(time_to_seconds)
        df_at["Act_Sec"] = df_at["Actual Added"].apply(time_to_seconds)
        df_at["Overrun_Sec"] = df_at["Act_Sec"] - df_at["Ann_Sec"]
        df_at["Overrun"] = df_at["Overrun_Sec"].apply(lambda s: f"+{seconds_to_time(s)}" if s >= 0 else f"-{seconds_to_time(abs(s))}")
        df_at["Match"] = df_at["Home Team"] + " vs " + df_at["Away Team"]

        st.dataframe(
            df_at[["Gameweek", "Match", "Announced Added", "Actual Added", "Overrun", "Played Added", "Total Match Time"]].sort_values(by="Gameweek", ascending=False),
            use_container_width=True,
            hide_index=True
        )

    with tab5:
        st.subheader("📺 VAR Review Impact")
        var_log = active_df[active_df["VAR Checks"] != "00:00"].copy()
        if var_log.empty:
            st.info("No fixtures have recorded significant VAR reviews yet.")
        else:
            var_log["Match"] = var_log["Home Team"] + " vs " + var_log["Away Team"]
            st.dataframe(var_log[["Gameweek", "Match", "VAR Checks", "Total Match Time", "Actual In-Play"]], use_container_width=True, hide_index=True)

    with tab6:
        st.markdown("💡 **Tip:** Double-click any cell to edit numbers directly.")
        edited_df = st.data_editor(
            st.session_state.match_log,
            num_rows="dynamic",
            use_container_width=True,
            key="match_data_editor"
        )
        if not edited_df.equals(st.session_state.match_log):
            st.session_state.match_log = edited_df.reset_index(drop=True)
            st.session_state.match_log.to_csv(DATA_FILE, index=False, encoding="utf-8")
            st.success("Changes saved!")
            st.rerun()
