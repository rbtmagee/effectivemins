import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os
import io

st.set_page_config(page_title="EffectiveMins Tracker", layout="wide")

# Custom Dark Styling matching @EffectiveMins aesthetic
st.markdown("""
    <style>
    .main { background-color: #0b1118; }
    h1, h2, h3 { color: #00d2ff; }
    div[data-testid="stMetricValue"] { color: #00d2ff; }
    </style>
""", unsafe_allow_html=True)

DATA_FILE = "effective_mins_data.csv"

# 2026/27 Premier League Teams
PL_TEAMS = sorted([
    "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton",
    "Chelsea", "Coventry City", "Crystal Palace", "Everton", "Fulham",
    "Hull City", "Ipswich Town", "Leeds United", "Liverpool",
    "Manchester City", "Manchester United", "Newcastle United",
    "Nottingham Forest", "Sunderland", "Tottenham"
])

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

# --- HELPER FUNCTIONS ---
def clean_val(val) -> str:
    """Normalises empty or null values into standard strings."""
    if pd.isna(val) or val is None:
        return "00:00"
    s = str(val).strip().replace("–", "-").replace("—", "-")
    return s if s else "00:00"

def time_to_seconds(val: str) -> int:
    """Converts MM:SS strings safely to integer seconds."""
    s_val = clean_val(val)
    if ":" not in s_val or s_val.startswith("-"):
        return 0
    try:
        parts = s_val.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return 0

def seconds_to_time(seconds: int) -> str:
    """Converts seconds back into MM:SS format."""
    m, s = divmod(int(round(seconds)), 60)
    return f"{m:02d}:{s:02d}"

# --- INITIALISE OR LOAD DATABASE ---
if os.path.exists(DATA_FILE):
    try:
        st.session_state.match_log = pd.read_csv(DATA_FILE, encoding="utf-8")
    except Exception:
        st.session_state.match_log = pd.read_csv(DATA_FILE, encoding="latin1")
else:
    st.session_state.match_log = pd.DataFrame(columns=MATCH_COLUMNS)

# Ensure schema alignment
for col in MATCH_COLUMNS:
    if col not in st.session_state.match_log.columns:
        st.session_state.match_log[col] = "00:00" if "Time" in col or "In-Play" in col or "Added" in col or "Wasted" in col else 0

st.title("⏱️ EffectiveMins: Premier League Stoppage Tracker")

# --- SIDEBAR: EXCEL IMPORT & TEMPLATE ---
with st.sidebar:
    st.header("📂 Master Spreadsheet Sync")
    st.caption("Upload your master Excel (.xlsx) or CSV file to sync your database instantly.")
    
    uploaded_master = st.file_uploader("Upload Spreadsheet", type=["xlsx", "csv"], label_visibility="collapsed")
    if uploaded_master is not None:
        try:
            if uploaded_master.name.endswith(".xlsx"):
                df_imported = pd.read_excel(uploaded_master)
            else:
                df_imported = pd.read_csv(uploaded_master)
            
            # Format and validate columns
            for col in MATCH_COLUMNS:
                if col not in df_imported.columns:
                    df_imported[col] = "--"
            
            st.session_state.match_log = df_imported[MATCH_COLUMNS].copy()
            st.session_state.match_log.to_csv(DATA_FILE, index=False, encoding="utf-8")
            st.success(f"Loaded {len(df_imported)} matches from spreadsheet!")
            st.rerun()
        except Exception as e:
            st.error(f"Error reading file: {str(e)}")

    st.divider()
    
    # Download blank template for Excel / Google Sheets
    st.markdown("**Need an Excel template?**")
    blank_template = pd.DataFrame(columns=MATCH_COLUMNS)
    template_buffer = io.BytesIO()
    with pd.ExcelWriter(template_buffer, engine='openpyxl') as writer:
        blank_template.to_excel(writer, index=False, sheet_name="EffectiveMins")
    
    st.download_button(
        label="📥 Download Blank Excel Template",
        data=template_buffer.getvalue(),
        file_name="effective_mins_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.divider()
    st.header("🛠️ Database Admin")
    st.write(f"Logged Fixtures: `{len(st.session_state.match_log)}`")
    
    with st.expander("⚠️ Danger Zone"):
        if st.button("🗑️ Reset Entire Database", type="secondary"):
            st.session_state.match_log = pd.DataFrame(columns=MATCH_COLUMNS)
            if os.path.exists(DATA_FILE):
                os.remove(DATA_FILE)
            st.warning("All records cleared.")
            st.rerun()

    st.divider()
    st.markdown("**@EffectiveMins** Analytics Engine")

# --- MATCH INGESTION SECTION ---
with st.expander("➕ Log Single Fixture Manually", expanded=st.session_state.match_log.empty):
    with st.form("manual_match_entry", clear_on_submit=True):
        st.subheader("1. Match Overview")
        c1, c2, c3 = st.columns(3)
        with c1:
            gw = st.number_input("Gameweek", min_value=1, max_value=38, value=1, step=1)
        with c2:
            home_team = st.selectbox("Home Team", PL_TEAMS, index=0)
        with c3:
            away_team = st.selectbox("Away Team", PL_TEAMS, index=1)

        st.subheader("2. Match In-Play & Stoppages")
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            actual_in_play = st.text_input("Actual In-Play", placeholder="57:29")
        with m2:
            total_time = st.text_input("Total Match Time", placeholder="99:01")
        with m3:
            var_checks = st.text_input("Significant VAR Checks", placeholder="02:30")
        with m4:
            game_stops = st.number_input("Game Stops", min_value=0, step=1, value=0)
        with m5:
            longest_in_play = st.text_input("Longest In-Play", placeholder="03:50")

        st.subheader("3. Added Time Breakdown")
        a1, a2, a3 = st.columns(3)
        with a1:
            ann_added = st.text_input("Announced Added", placeholder="08:00")
        with a2:
            act_added = st.text_input("Actual Added", placeholder="09:01")
        with a3:
            ply_added = st.text_input("Played Added", placeholder="06:33")

        st.subheader("4. Time Wasted Breakdown (Home vs Away)")
        tw1, tw2, tw3, tw4, tw5, tw6 = st.columns(6)
        with tw1:
            st.caption("Goal Kicks")
            h_gk = st.text_input("Home GK", placeholder="01:13")
            a_gk = st.text_input("Away GK", placeholder="05:45")
        with tw2:
            st.caption("Free Kicks")
            h_fk = st.text_input("Home FK", placeholder="04:06")
            a_fk = st.text_input("Away FK", placeholder="10:32")
        with tw3:
            st.caption("Throw Ins")
            h_ti = st.text_input("Home TI", placeholder="02:49")
            a_ti = st.text_input("Away TI", placeholder="06:06")
        with tw4:
            st.caption("Corners")
            h_co = st.text_input("Home Cor", placeholder="01:24")
            a_co = st.text_input("Away Cor", placeholder="02:50")
        with tw5:
            st.caption("Other")
            h_ot = st.text_input("Home Oth", placeholder="02:33")
            a_ot = st.text_input("Away Oth", placeholder="03:30")
        with tw6:
            st.caption("Total Wasted")
            h_tot = st.text_input("Home Tot", placeholder="12:05")
            a_tot = st.text_input("Away Tot", placeholder="28:43")

        submitted = st.form_submit_button("Save Fixture Record", type="primary")
        if submitted:
            if home_team == away_team:
                st.error("Home and Away teams must be different.")
            else:
                new_row = {
                    "Gameweek": int(gw),
                    "Home Team": home_team,
                    "Away Team": away_team,
                    "Actual In-Play": clean_val(actual_in_play),
                    "Total Match Time": clean_val(total_time or "90:00"),
                    "VAR Checks": clean_val(var_checks),
                    "Game Stops": int(game_stops),
                    "Longest In-Play": clean_val(longest_in_play),
                    "Announced Added": clean_val(ann_added),
                    "Actual Added": clean_val(act_added),
                    "Played Added": clean_val(ply_added),
                    "Home Goal Kicks": clean_val(h_gk),
                    "Away Goal Kicks": clean_val(a_gk),
                    "Home Free Kicks": clean_val(h_fk),
                    "Away Free Kicks": clean_val(a_fk),
                    "Home Throw Ins": clean_val(h_ti),
                    "Away Throw Ins": clean_val(a_ti),
                    "Home Corners": clean_val(h_co),
                    "Away Corners": clean_val(a_co),
                    "Home Other": clean_val(h_ot),
                    "Away Other": clean_val(a_ot),
                    "Home Total Wasted": clean_val(h_tot),
                    "Away Total Wasted": clean_val(a_tot)
                }
                st.session_state.match_log = pd.concat(
                    [st.session_state.match_log, pd.DataFrame([new_row])],
                    ignore_index=True
                )
                st.session_state.match_log.to_csv(DATA_FILE, index=False, encoding="utf-8")
                st.success(f"Saved {home_team} vs {away_team} successfully!")
                st.rerun()

st.divider()

# --- STANDINGS & VISUAL ANALYTICS ---
if st.session_state.match_log.empty:
    st.info("No fixtures recorded yet. Upload a spreadsheet in the sidebar or log a match using the form above.")
else:
    tab1, tab2 = st.tabs(["🏆 Team Standings (Averages)", "📝 Live Spreadsheet Editor & Export"])

    with tab1:
        team_rows = []
        for _, r in st.session_state.match_log.iterrows():
            # Home side entry
            team_rows.append({
                "Team": r["Home Team"],
                "InPlay_Sec": time_to_seconds(r["Actual In-Play"]),
                "Total_Sec": time_to_seconds(r["Total Match Time"]),
                "GoalKicks_Sec": time_to_seconds(r["Home Goal Kicks"]),
                "FreeKicks_Sec": time_to_seconds(r["Home Free Kicks"]),
                "ThrowIns_Sec": time_to_seconds(r["Home Throw Ins"]),
                "Corners_Sec": time_to_seconds(r["Home Corners"]),
                "Other_Sec": time_to_seconds(r["Home Other"]),
                "TotalWasted_Sec": time_to_seconds(r["Home Total Wasted"])
            })
            # Away side entry
            team_rows.append({
                "Team": r["Away Team"],
                "InPlay_Sec": time_to_seconds(r["Actual In-Play"]),
                "Total_Sec": time_to_seconds(r["Total Match Time"]),
                "GoalKicks_Sec": time_to_seconds(r["Away Goal Kicks"]),
                "FreeKicks_Sec": time_to_seconds(r["Away Free Kicks"]),
                "ThrowIns_Sec": time_to_seconds(r["Away Throw Ins"]),
                "Corners_Sec": time_to_seconds(r["Away Corners"]),
                "Other_Sec": time_to_seconds(r["Away Other"]),
                "TotalWasted_Sec": time_to_seconds(r["Away Total Wasted"])
            })

        df_calc = pd.DataFrame(team_rows)
        grouped = df_calc.groupby("Team").mean().reset_index()
        counts = df_calc.groupby("Team").size().reset_index(name="Matches")
        standings = pd.merge(counts, grouped, on="Team")

        standings["Effective In-Play %"] = ((standings["InPlay_Sec"] / standings["Total_Sec"].replace(0, 1)) * 100).round(1)
        standings["Avg In-Play"] = standings["InPlay_Sec"].apply(seconds_to_time)
        standings["Avg Total Wasted"] = standings["TotalWasted_Sec"].apply(seconds_to_time)
        standings["Avg Free Kicks Delay"] = standings["FreeKicks_Sec"].apply(seconds_to_time)
        standings["Avg Goal Kicks Delay"] = standings["GoalKicks_Sec"].apply(seconds_to_time)
        standings["Avg Throw Ins Delay"] = standings["ThrowIns_Sec"].apply(seconds_to_time)
        standings["Avg Corners Delay"] = standings["Corners_Sec"].apply(seconds_to_time)
        standings["Avg Other Delay"] = standings["Other_Sec"].apply(seconds_to_time)

        # Dynamic Sorting Selector
        sort_mode = st.selectbox(
            "Sort Standings By:",
            [
                ("TotalWasted_Sec", "Total Delay (Highest First)", False),
                ("GoalKicks_Sec", "Goal Kicks Delay (Highest First)", False),
                ("FreeKicks_Sec", "Free Kicks Delay (Highest First)", False),
                ("ThrowIns_Sec", "Throw Ins Delay (Highest First)", False),
                ("Corners_Sec", "Corners Delay (Highest First)", False),
                ("Effective In-Play %", "Effective In-Play % (Lowest First)", True)
            ],
            format_func=lambda x: x[1]
        )

        standings = standings.sort_values(by=sort_mode[0], ascending=sort_mode[2])

        display_cols = [
            "Team", "Matches", "Effective In-Play %", "Avg In-Play",
            "Avg Total Wasted", "Avg Free Kicks Delay", "Avg Goal Kicks Delay",
            "Avg Throw Ins Delay", "Avg Corners Delay", "Avg Other Delay"
        ]
        st.dataframe(standings[display_cols], use_container_width=True, hide_index=True)

        st.divider()

        # --- TWITTER INFOGRAPHIC CARD GENERATOR ---
        st.subheader("Generate Graphic for @EffectiveMins")
        selected_team = st.selectbox("Select Club for Graphic Card", standings["Team"])
        t_row = standings[standings["Team"] == selected_team].iloc[0]

        cg1, cg2 = st.columns([1.2, 1])
        with cg1:
            fig, ax = plt.subplots(figsize=(10, 5.5), facecolor="#0e1621")
            ax.set_facecolor("#0e1621")

            categories = ["Free Kicks", "Goal Kicks", "Throw Ins", "Corners", "Other"]
            durations = [
                t_row["FreeKicks_Sec"] / 60.0,
                t_row["GoalKicks_Sec"] / 60.0,
                t_row["ThrowIns_Sec"] / 60.0,
                t_row["Corners_Sec"] / 60.0,
                t_row["Other_Sec"] / 60.0,
            ]

            ax.barh(categories, durations, color="#00d2ff", edgecolor="#ffffff", height=0.55)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_color('#888888')
            ax.spines['left'].set_color('#888888')
            ax.tick_params(colors='#ffffff', labelsize=11)
            ax.set_xlabel("Average Minutes Spent per Match", color="#ffffff", fontsize=11)
            ax.set_title(f"{selected_team.upper()} — Dead-Ball Delay Profile", color="#ffffff", fontsize=15, weight="bold", pad=15)
            fig.text(0.82, 0.02, "@EffectiveMins", color="#888888", fontsize=10, style='italic')

            st.pyplot(fig)

        with cg2:
            st.markdown("### Ready-to-Post Copy")
            post_text = f"""⏱️ Stoppage Breakdown: {selected_team}

• Effective Playing Time: {t_row['Effective In-Play %']}% ({t_row['Avg In-Play']})
• Average Time Lost: {t_row['Avg Total Wasted']} per 90

Biggest delay factors:
1. Free Kicks: {t_row['Avg Free Kicks Delay']}
2. Goal Kicks: {t_row['Avg Goal Kicks Delay']}
3. Throw Ins: {t_row['Avg Throw Ins Delay']}

Data tracked by @EffectiveMins #PremierLeague #PL"""
            st.text_area("Draft Post", value=post_text, height=190)

    # --- TAB 2: LIVE SPREADSHEET EDITOR ---
    with tab2:
        st.markdown("💡 **Tip:** Double-click any cell to modify values directly. Tick checkboxes on the left and hit `Delete` on your keyboard to remove fixtures.")
        
        edited_df = st.data_editor(
            st.session_state.match_log,
            num_rows="dynamic",
            use_container_width=True,
            key="match_data_editor"
        )

        if not edited_df.equals(st.session_state.match_log):
            st.session_state.match_log = edited_df.reset_index(drop=True)
            st.session_state.match_log.to_csv(DATA_FILE, index=False, encoding="utf-8")
            st.success("Database updated!")
            st.rerun()

        st.write("")
        csv_export = st.session_state.match_log.to_csv(index=False, encoding="utf-8").encode('utf-8')
        st.download_button("📥 Export Database (CSV)", data=csv_export, file_name="effective_mins_database.csv", mime="text/csv")
