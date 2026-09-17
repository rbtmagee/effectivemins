import os
import re
import glob
import subprocess
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="EffectiveMins: Football Analytics Engine",
    page_icon="⏱️",
    layout="wide",
    initial_sidebar_state="expanded"
)

DATA_FILE = "effective_mins_data.csv"
REPORTS_DIR = "match_reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

# ---------------------------------------------------------
# STYLING & ASSETS
# ---------------------------------------------------------
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .metric-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .metric-value { font-size: 26px; font-weight: 700; color: #58a6ff; }
    .metric-label { font-size: 13px; color: #8b949e; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

CLUB_LOGOS = {
    "Arsenal": "https://resources.premierleague.com/premierleague/badges/50/t3.png",
    "Aston Villa": "https://resources.premierleague.com/premierleague/badges/50/t7.png",
    "Bournemouth": "https://resources.premierleague.com/premierleague/badges/50/t91.png",
    "Brentford": "https://resources.premierleague.com/premierleague/badges/50/t94.png",
    "Brighton": "https://resources.premierleague.com/premierleague/badges/50/t36.png",
    "Chelsea": "https://resources.premierleague.com/premierleague/badges/50/t8.png",
    "Coventry City": "https://resources.premierleague.com/premierleague/badges/50/t54.png",
    "Crystal Palace": "https://resources.premierleague.com/premierleague/badges/50/t31.png",
    "Everton": "https://resources.premierleague.com/premierleague/badges/50/t11.png",
    "Fulham": "https://resources.premierleague.com/premierleague/badges/50/t54.png",
    "Hull City": "https://resources.premierleague.com/premierleague/badges/50/t88.png",
    "Ipswich Town": "https://resources.premierleague.com/premierleague/badges/50/t40.png",
    "Leeds United": "https://resources.premierleague.com/premierleague/badges/50/t2.png",
    "Liverpool": "https://resources.premierleague.com/premierleague/badges/50/t14.png",
    "Manchester City": "https://resources.premierleague.com/premierleague/badges/50/t43.png",
    "Manchester United": "https://resources.premierleague.com/premierleague/badges/50/t1.png",
    "Newcastle United": "https://resources.premierleague.com/premierleague/badges/50/t4.png",
    "Nottingham Forest": "https://resources.premierleague.com/premierleague/badges/50/t17.png",
    "Sunderland": "https://resources.premierleague.com/premierleague/badges/50/t56.png",
    "Tottenham": "https://resources.premierleague.com/premierleague/badges/50/t6.png",
    "West Ham": "https://resources.premierleague.com/premierleague/badges/50/t21.png",
    "Wolves": "https://resources.premierleague.com/premierleague/badges/50/t39.png"
}

# ---------------------------------------------------------
# DATA UTILITIES
# ---------------------------------------------------------
def time_to_sec(val):
    if pd.isna(val) or val is None:
        return 0.0
    val_str = str(val).strip()
    if ":" in val_str:
        parts = val_str.split(":")
        try:
            return float(parts[0]) * 60 + float(parts[1])
        except ValueError:
            return 0.0
    try:
        return float(val_str)
    except ValueError:
        return 0.0

def sec_to_time(seconds):
    if pd.isna(seconds) or seconds <= 0:
        return "00:00"
    m, s = divmod(int(round(seconds)), 60)
    return f"{m:02d}:{s:02d}"

@st.cache_data(ttl=5)
def load_data():
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame()
    try:
        df = pd.read_csv(DATA_FILE, encoding="utf-8")
    except Exception:
        df = pd.read_csv(DATA_FILE, encoding="latin1")

    num_cols = ["Gameweek", "Game Stops", "Home Possession", "Away Possession", 
                "Home xG", "Away xG", "Home Total Shots", "Away Total Shots",
                "Home Shots On Target", "Away Shots On Target", "Home Fouls", "Away Fouls"]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    timing_keys = ["Actual In-Play", "Total Match Time", "VAR Checks", "Longest In-Play",
                   "Announced Added", "Actual Added", "Played Added", "Home Total Wasted", 
                   "Away Total Wasted", "Home Goal Kicks", "Away Goal Kicks",
                   "Home Free Kicks", "Away Free Kicks", "Home Throw Ins", "Away Throw Ins",
                   "Home Corners", "Away Corners", "Home Other", "Away Other"]
    for tk in timing_keys:
        if tk in df.columns:
            df[f"{tk}_sec"] = df[tk].apply(time_to_sec)

    return df

df_raw = load_data()

# ---------------------------------------------------------
# HEADER & SIDEBAR FILTERS
# ---------------------------------------------------------
st.title("⏱️ EffectiveMins: Football Analytics Engine")
st.caption("Opta In-Play Stoppage & Ball Retention Metrics | Premier League 2026/27")

if df_raw.empty:
    st.warning("⚠️ No match data found in `effective_mins_data.csv`. Upload match reports in the **Live Spreadsheet Editor & Export** tab to populate the engine.")
    st.stop()

st.sidebar.header("🔍 Filters & Controls")
available_gw = sorted(df_raw["Gameweek"].dropna().unique().astype(int).tolist())
selected_gw = st.sidebar.multiselect("Select Gameweeks", available_gw, default=available_gw)

all_teams = sorted(list(set(df_raw["Home Team"].dropna().unique().tolist() + df_raw["Away Team"].dropna().unique().tolist())))
selected_team = st.sidebar.selectbox("Filter Specific Club Focus", ["All Clubs"] + all_teams)

df_filtered = df_raw[df_raw["Gameweek"].isin(selected_gw)].copy()
if selected_team != "All Clubs":
    df_filtered = df_filtered[(df_filtered["Home Team"] == selected_team) | (df_filtered["Away Team"] == selected_team)]

# ---------------------------------------------------------
# TOP SUMMARY KPIS
# ---------------------------------------------------------
kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
total_matches = len(df_filtered)
avg_in_play = df_filtered["Actual In-Play_sec"].mean() if total_matches > 0 else 0
avg_total_time = df_filtered["Total Match Time_sec"].mean() if total_matches > 0 else 5400
effective_pct = (avg_in_play / avg_total_time * 100) if avg_total_time > 0 else 0
avg_var_checks = df_filtered["VAR Checks_sec"].mean() if total_matches > 0 else 0
avg_stops = df_filtered["Game Stops"].mean() if total_matches > 0 else 0

kpi1.markdown(f"<div class='metric-card'><div class='metric-value'>{total_matches}</div><div class='metric-label'>Matches Analyzed</div></div>", unsafe_allow_html=True)
kpi2.markdown(f"<div class='metric-card'><div class='metric-value'>{sec_to_time(avg_in_play)}</div><div class='metric-label'>Avg In-Play Time</div></div>", unsafe_allow_html=True)
kpi3.markdown(f"<div class='metric-card'><div class='metric-value'>{effective_pct:.1f}%</div><div class='metric-label'>Effective Playing %</div></div>", unsafe_allow_html=True)
kpi4.markdown(f"<div class='metric-card'><div class='metric-value'>{sec_to_time(avg_var_checks)}</div><div class='metric-label'>Avg VAR Stoppage</div></div>", unsafe_allow_html=True)
kpi5.markdown(f"<div class='metric-card'><div class='metric-value'>{avg_stops:.1f}</div><div class='metric-label'>Avg Whistle Stops</div></div>", unsafe_allow_html=True)

st.write("")

# ---------------------------------------------------------
# TABS
# ---------------------------------------------------------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏆 Premier League Standings",
    "🎯 Control, xG & Territory",
    "🌊 Flow & Disruption",
    "⏱️ Added Time Integrity",
    "📺 VAR Stoppage Impact",
    "📑 Live Spreadsheet Editor & Export"
])

# ---------------------------------------------------------
# TAB 1: STANDINGS
# ---------------------------------------------------------
with tab1:
    st.subheader("Team Dead-Ball Waste & Effective Minutes Table")

    standings_rows = []
    for team in all_teams:
        home_m = df_raw[df_raw["Home Team"] == team]
        away_m = df_raw[df_raw["Away Team"] == team]
        team_matches = len(home_m) + len(away_m)
        if team_matches == 0:
            continue

        team_in_play = pd.concat([home_m["Actual In-Play_sec"], away_m["Actual In-Play_sec"]]).mean()
        team_total = pd.concat([home_m["Total Match Time_sec"], away_m["Total Match Time_sec"]]).mean()
        
        wasted_caused = pd.concat([home_m["Home Total Wasted_sec"], away_m["Away Total Wasted_sec"]]).mean()
        goal_kicks = pd.concat([home_m["Home Goal Kicks_sec"], away_m["Away Goal Kicks_sec"]]).mean()
        free_kicks = pd.concat([home_m["Home Free Kicks_sec"], away_m["Away Free Kicks_sec"]]).mean()
        throw_ins = pd.concat([home_m["Home Throw Ins_sec"], away_m["Away Throw Ins_sec"]]).mean()
        corners = pd.concat([home_m["Home Corners_sec"], away_m["Away Corners_sec"]]).mean()
        other = pd.concat([home_m["Home Other_sec"], away_m["Away Other_sec"]]).mean()

        standings_rows.append({
            "Badge": CLUB_LOGOS.get(team, ""),
            "Team": team,
            "Matches": team_matches,
            "Effective In-Play %": round((team_in_play / team_total * 100), 1) if team_total > 0 else 0,
            "Avg In-Play": sec_to_time(team_in_play),
            "Avg Total Wasted": sec_to_time(wasted_caused),
            "Avg Goal Kicks Delay": sec_to_time(goal_kicks),
            "Avg Free Kicks Delay": sec_to_time(free_kicks),
            "Avg Throw Ins Delay": sec_to_time(throw_ins),
            "Avg Corners Delay": sec_to_time(corners),
            "Avg Other Delay": sec_to_time(other),
            "_wasted_sec": wasted_caused
        })

    df_standings = pd.DataFrame(standings_rows).sort_values(by="_wasted_sec", ascending=False).drop(columns=["_wasted_sec"])

    st.dataframe(
        df_standings,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Badge": st.column_config.ImageColumn("Badge", width="small"),
            "Effective In-Play %": st.column_config.ProgressColumn("Effective In-Play %", format="%.1f%%", min_value=40, max_value=80)
        }
    )

# ---------------------------------------------------------
# TAB 2: CONTROL, XG & TERRITORY
# ---------------------------------------------------------
with tab2:
    st.subheader("Matchflow Dominance: In-Play Time vs Expected Goals (xG)")

    fig_xg = px.scatter(
        df_filtered,
        x="Actual In-Play_sec",
        y="Home xG",
        size="Home Total Shots",
        color="Home Team",
        hover_data=["Gameweek", "Home Team", "Away Team", "Actual In-Play"],
        title="Home In-Play Time vs Expected Goals Created",
        labels={"Actual In-Play_sec": "Actual Ball In-Play (Seconds)", "Home xG": "Home Expected Goals (xG)"},
        template="plotly_dark"
    )
    fig_xg.update_layout(xaxis_tickformat="s")
    st.plotly_chart(fig_xg, use_container_width=True)

# ---------------------------------------------------------
# TAB 3: FLOW & DISRUPTION
# ---------------------------------------------------------
with tab3:
    st.subheader("Dead-Ball Delay Decomposition")
    
    col_a, col_b = st.columns(2)
    with col_a:
        delays = {
            "Goal Kicks": df_filtered["Home Goal Kicks_sec"].mean() + df_filtered["Away Goal Kicks_sec"].mean(),
            "Free Kicks": df_filtered["Home Free Kicks_sec"].mean() + df_filtered["Away Free Kicks_sec"].mean(),
            "Throw Ins": df_filtered["Home Throw Ins_sec"].mean() + df_filtered["Away Throw Ins_sec"].mean(),
            "Corners": df_filtered["Home Corners_sec"].mean() + df_filtered["Away Corners_sec"].mean(),
            "Other / Restarts": df_filtered["Home Other_sec"].mean() + df_filtered["Away Other_sec"].mean()
        }
        fig_pie = px.pie(
            names=list(delays.keys()),
            values=list(delays.values()),
            hole=0.45,
            title="Distribution of Dead-Ball Delays (Seconds)",
            template="plotly_dark"
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_b:
        fig_stops = px.bar(
            df_filtered,
            x="Home Team",
            y="Game Stops",
            color="Away Team",
            title="Total Whistle Stops per Fixture",
            template="plotly_dark"
        )
        st.plotly_chart(fig_stops, use_container_width=True)

# ---------------------------------------------------------
# TAB 4: ADDED TIME INTEGRITY
# ---------------------------------------------------------
with tab4:
    st.subheader("Announced vs Actual Played Added Time Integrity")
    fig_added = go.Figure()
    fig_added.add_trace(go.Bar(
        x=df_filtered["Home Team"] + " vs " + df_filtered["Away Team"],
        y=df_filtered["Announced Added_sec"] / 60,
        name="Announced Added (Mins)",
        marker_color="#8b949e"
    ))
    fig_added.add_trace(go.Bar(
        x=df_filtered["Home Team"] + " vs " + df_filtered["Away Team"],
        y=df_filtered["Played Added_sec"] / 60,
        name="Played Added (Mins)",
        marker_color="#2ea043"
    ))
    fig_added.update_layout(barmode="group", template="plotly_dark", title="Stoppage Time Deficit/Surplus (Minutes)")
    st.plotly_chart(fig_added, use_container_width=True)

# ---------------------------------------------------------
# TAB 5: VAR STOPPAGE IMPACT
# ---------------------------------------------------------
with tab5:
    st.subheader("VAR Review Duration Breakdown")
    fig_var = px.histogram(
        df_filtered,
        x="VAR Checks_sec",
        nbins=20,
        color="Gameweek",
        title="VAR Stoppage Distribution Across Season",
        labels={"VAR Checks_sec": "VAR Check Duration (Seconds)"},
        template="plotly_dark"
    )
    st.plotly_chart(fig_var, use_container_width=True)

# ---------------------------------------------------------
# TAB 6: LIVE SPREADSHEET EDITOR & REPORT UPLOADER
# ---------------------------------------------------------
with tab6:
    st.subheader("📂 Manage Match Reports & Live Database")

    col_up1, col_up2 = st.columns(2)

    with col_up1:
        st.markdown("**1. Upload Raw Match `.txt` Reports**")
        uploaded_txts = st.file_uploader(
            "Drop match stats .txt files here",
            type=["txt"],
            accept_multiple_files=True,
            key="txt_uploader"
        )
        if uploaded_txts:
            for txt_file in uploaded_txts:
                dest_path = os.path.join(REPORTS_DIR, txt_file.name)
                with open(dest_path, "wb") as f:
                    f.write(txt_file.getbuffer())
            st.success(f"Saved {len(uploaded_txts)} report(s) into `{REPORTS_DIR}/`.")

        if st.button("⚡ Parse All .txt Reports into CSV", type="primary"):
            with st.spinner("Processing match reports..."):
                if os.path.exists("parse_reports.py"):
                    proc = subprocess.run(["python3", "parse_reports.py"], capture_output=True, text=True)
                    st.code(proc.stdout)
                else:
                    st.error("`parse_reports.py` script not found in root directory.")
                st.cache_data.clear()
                st.rerun()

    with col_up2:
        st.markdown("**2. Direct CSV Import / Backup**")
        uploaded_csv = st.file_uploader("Upload pre-filled `effective_mins_data.csv`", type=["csv"], key="csv_uploader")
        if uploaded_csv:
            with open(DATA_FILE, "wb") as f:
                f.write(uploaded_csv.getbuffer())
            st.success("Successfully replaced `effective_mins_data.csv`!")
            st.cache_data.clear()
            st.rerun()

    st.divider()
    st.subheader("✏️ Interactive Match Database Editor")
    st.caption("Edit values directly in the spreadsheet below and click **Save Changes to CSV**.")

    editable_df = st.data_editor(
        df_raw,
        use_container_width=True,
        num_rows="dynamic",
        key="data_editor"
    )

    if st.button("💾 Save Changes to CSV"):
        editable_df.to_csv(DATA_FILE, index=False, encoding="utf-8")
        st.success("Changes successfully written to `effective_mins_data.csv`!")
        st.cache_data.clear()
        st.rerun()
