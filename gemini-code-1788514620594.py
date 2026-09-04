import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os
import io
import re

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

# --- UTILITY & SANITISATION HELPERS ---
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

# --- DIRECT ZERO-AI 365SCORES TEXT PARSER ---
def parse_365_raw_text(content: str) -> dict:
    """
    Parses expanded 365Scores text reports without any third-party AI APIs.
    Supports both uploaded .txt web saves and pasted clipboard text.
    """
    stats = {}

    # 1. Headline Match Durations
    act_m = re.search(r"Actual\s+(\d{1,2}:\d{2})", content, re.IGNORECASE)
    tot_m = re.search(r"Total\s+(\d{1,2}:\d{2})", content, re.IGNORECASE)
    stats["actual_in_play"] = act_m.group(1) if act_m else "00:00"
    stats["total_time"] = tot_m.group(1) if tot_m else "90:00"

    # 2. Game Stops & Longest Run
    stops_m = re.search(r"Game\s*Stops\s*(?:\n|\s+)*(\d+)", content, re.IGNORECASE)
    longest_m = re.search(r"Longest\s*In-Play\s*(?:\n|\s+)*(\d{1,2}:\d{2})", content, re.IGNORECASE)
    stats["game_stops"] = int(stops_m.group(1)) if stops_m else 0
    stats["longest_in_play"] = longest_m.group(1) if longest_m else "00:00"

    # 3. Added Time Metrics
    ann_m = re.search(r"(\d{1,2}:\d{2})\s*(?:\n|\s+)*Announced", content, re.IGNORECASE)
    act_add_m = re.search(r"(\d{1,2}:\d{2})\s*(?:\n|\s+)*Actual\s+Added", content, re.IGNORECASE)
    stats["announced_added"] = ann_m.group(1) if ann_m else "00:00"
    stats["actual_added"] = act_add_m.group(1) if act_add_m else "00:00"
    stats["played_added"] = "00:00"
    stats["var_checks"] = "00:00"

    # Check for significant VAR checks line if present
    var_m = re.search(r"(?:Significant\s+)?VAR\s*Checks\s*(?:\n|\s+)*(\d{1,2}:\d{2})", content, re.IGNORECASE)
    if var_m:
        stats["var_checks"] = var_m.group(1)

    # 4. Dead-Ball Stoppage Categories (Split after "Time Wasted On")
    wasted_section = content
    if "Time Wasted On" in content:
        wasted_section = content.split("Time Wasted On", 1)[1]

    categories = [
        ("goal_kicks", r"Goal\s+Kicks"),
        ("free_kicks", r"Free\s+Kicks"),
        ("throw_ins", r"Throw\s+Ins"),
        ("corners", r"Corners"),
        ("other", r"Other"),
        ("total_wasted", r"Total")
    ]

    for key, label in categories:
        # Handles both multi-line text files and single-line copies
        pattern = rf"(\d{{1,2}}:\d{{2}})\s*(?:\n|\s+)*{label}\s*(?:\n|\s+)*(\d{{1,2}}:\d{{2}})"
        match = re.search(pattern, wasted_section, re.IGNORECASE)
        if match:
            stats[f"home_{key}"] = match.group(1)
            stats[f"away_{key}"] = match.group(2)
        else:
            stats[f"home_{key}"] = "00:00"
            stats[f"away_{key}"] = "00:00"

    return stats

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

# --- SIDEBAR: EXCEL IMPORT & MASTER TEMPLATE ---
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

            for col in MATCH_COLUMNS:
                if col not in df_imported.columns:
                    df_imported[col] = "00:00"

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
with st.expander("➕ Log New Fixture (Text Parser or Manual)", expanded=st.session_state.match_log.empty):
    c1, c2, c3 = st.columns(3)
    with c1:
        gw = st.number_input("Gameweek", min_value=1, max_value=38, value=1, step=1)
    with c2:
        home_team = st.selectbox("Home Team", PL_TEAMS, index=0)
    with c3:
        away_team = st.selectbox("Away Team", PL_TEAMS, index=1)

    ingest_tab1, ingest_tab2 = st.tabs(["📄 365Scores Web Text Parser", "✍️ Manual Form Entry"])

    # TAB 1: ZERO-AI TEXT PARSER
    with ingest_tab1:
        st.caption("Upload your saved match report `.txt` file or paste the text copied directly from the expanded 365Scores page.")

        input_mode = st.radio("Input Format:", ["📁 Upload .txt File", "📋 Paste Copied Text"], horizontal=True)

        raw_report_text = ""

        if input_mode == "📁 Upload .txt File":
            uploaded_txt = st.file_uploader("Upload Match Report File", type=["txt"], label_visibility="collapsed")
            if uploaded_txt is not None:
                raw_report_text = uploaded_txt.read().decode("utf-8", errors="ignore")
                st.success("Text report loaded successfully!")
        else:
            raw_report_text = st.text_area(
                "Paste Report Text Here:",
                placeholder="Actual 60:58\nTotal 96:20\nGame Stops 85\n...",
                height=180
            )

        st.write("")
        btn_c1, btn_c2 = st.columns([2, 1])
        with btn_c1:
            parse_pressed = st.button("🚀 Extract & Record Fixture", type="primary", use_container_width=True)
        with btn_c2:
            undo_pressed = st.button("↩️ Undo Last Entry", type="secondary", use_container_width=True)

        if undo_pressed:
            if not st.session_state.match_log.empty:
                removed_row = st.session_state.match_log.iloc[-1]
                st.session_state.match_log = st.session_state.match_log.iloc[:-1].reset_index(drop=True)
                st.session_state.match_log.to_csv(DATA_FILE, index=False, encoding="utf-8")
                st.warning(f"Undid: {removed_row['Home Team']} vs {removed_row['Away Team']} (Gameweek {removed_row['Gameweek']})")
                st.rerun()
            else:
                st.info("No fixtures to undo.")

        if parse_pressed:
            if home_team == away_team:
                st.error("Home and Away teams must be different.")
            elif not raw_report_text.strip():
                st.error("Please upload a .txt file or paste report text first.")
            else:
                parsed = parse_365_raw_text(raw_report_text)

                if parsed["actual_in_play"] == "00:00" and parsed["home_total_wasted"] == "00:00":
                    st.error("Could not find stoppage metrics. Make sure 'See More' was clicked on 365Scores prior to copying.")
                else:
                    new_entry = {
                        "Gameweek": int(gw),
                        "Home Team": home_team,
                        "Away Team": away_team,
                        "Actual In-Play": parsed["actual_in_play"],
                        "Total Match Time": parsed["total_time"],
                        "VAR Checks": parsed["var_checks"],
                        "Game Stops": parsed["game_stops"],
                        "Longest In-Play": parsed["longest_in_play"],
                        "Announced Added": parsed["announced_added"],
                        "Actual Added": parsed["actual_added"],
                        "Played Added": parsed["played_added"],
                        "Home Goal Kicks": parsed["home_goal_kicks"],
                        "Away Goal Kicks": parsed["away_goal_kicks"],
                        "Home Free Kicks": parsed["home_free_kicks"],
                        "Away Free Kicks": parsed["away_free_kicks"],
                        "Home Throw Ins": parsed["home_throw_ins"],
                        "Away Throw Ins": parsed["away_throw_ins"],
                        "Home Corners": parsed["home_corners"],
                        "Away Corners": parsed["away_corners"],
                        "Home Other": parsed["home_other"],
                        "Away Other": parsed["away_other"],
                        "Home Total Wasted": parsed["home_total_wasted"],
                        "Away Total Wasted": parsed["away_total_wasted"]
                    }

                    st.session_state.match_log = pd.concat(
                        [st.session_state.match_log, pd.DataFrame([new_entry])],
                        ignore_index=True
                    )
                    st.session_state.match_log.to_csv(DATA_FILE, index=False, encoding="utf-8")
                    st.success(f"Recorded {home_team} vs {away_team} successfully!")
                    st.rerun()

    # TAB 2: MANUAL ENTRY FORM
    with ingest_tab2:
        with st.form("manual_entry_form", clear_on_submit=True):
            st.markdown("##### Match In-Play & Flow")
            m1, m2, m3, m4, m5 = st.columns(5)
            with m1:
                man_inplay = st.text_input("Actual In-Play", placeholder="60:58")
            with m2:
                man_total = st.text_input("Total Match Time", placeholder="96:20")
            with m3:
                man_var = st.text_input("VAR Checks", placeholder="00:00")
            with m4:
                man_stops = st.number_input("Game Stops", min_value=0, step=1, value=0)
            with m5:
                man_longest = st.text_input("Longest In-Play", placeholder="04:31")

            st.markdown("##### Added Time Breakdown")
            at1, at2, at3 = st.columns(3)
            with at1:
                man_ann = st.text_input("Announced Added", placeholder="06:00")
            with at2:
                man_act_add = st.text_input("Actual Added", placeholder="06:20")
            with at3:
                man_ply_add = st.text_input("Played Added", placeholder="00:00")

            st.markdown("##### Dead-Ball Time Wasted (Home vs Away)")
            tw1, tw2, tw3, tw4, tw5, tw6 = st.columns(6)
            with tw1:
                st.caption("Goal Kicks")
                man_hgk = st.text_input("Home GK", placeholder="03:46")
                man_agk = st.text_input("Away GK", placeholder="02:53")
            with tw2:
                st.caption("Free Kicks")
                man_hfk = st.text_input("Home FK", placeholder="04:31")
                man_afk = st.text_input("Away FK", placeholder="07:14")
            with tw3:
                st.caption("Throw Ins")
                man_hti = st.text_input("Home TI", placeholder="03:01")
                man_ati = st.text_input("Away TI", placeholder="02:37")
            with tw4:
                st.caption("Corners")
                man_hco = st.text_input("Home Cor", placeholder="02:59")
                man_aco = st.text_input("Away Cor", placeholder="02:02")
            with tw5:
                st.caption("Other")
                man_hot = st.text_input("Home Oth", placeholder="03:29")
                man_aot = st.text_input("Away Oth", placeholder="02:08")
            with tw6:
                st.caption("Total Wasted")
                man_htot = st.text_input("Home Tot", placeholder="17:46")
                man_atot = st.text_input("Away Tot", placeholder="16:54")

            if st.form_submit_button("Save Record Manually", type="primary"):
                manual_row = {
                    "Gameweek": int(gw),
                    "Home Team": home_team,
                    "Away Team": away_team,
                    "Actual In-Play": clean_val(man_inplay),
                    "Total Match Time": clean_val(man_total or "90:00"),
                    "VAR Checks": clean_val(man_var),
                    "Game Stops": int(man_stops),
                    "Longest In-Play": clean_val(man_longest),
                    "Announced Added": clean_val(man_ann),
                    "Actual Added": clean_val(man_act_add),
                    "Played Added": clean_val(man_ply_add),
                    "Home Goal Kicks": clean_val(man_hgk),
                    "Away Goal Kicks": clean_val(man_agk),
                    "Home Free Kicks": clean_val(man_hfk),
                    "Away Free Kicks": clean_val(man_afk),
                    "Home Throw Ins": clean_val(man_hti),
                    "Away Throw Ins": clean_val(man_ati),
                    "Home Corners": clean_val(man_hco),
                    "Away Corners": clean_val(man_aco),
                    "Home Other": clean_val(man_hot),
                    "Away Other": clean_val(man_aot),
                    "Home Total Wasted": clean_val(man_htot),
                    "Away Total Wasted": clean_val(man_atot)
                }
                st.session_state.match_log = pd.concat([st.session_state.match_log, pd.DataFrame([manual_row])], ignore_index=True)
                st.session_state.match_log.to_csv(DATA_FILE, index=False, encoding="utf-8")
                st.success(f"Recorded {home_team} vs {away_team} manually!")
                st.rerun()

st.divider()

# --- STANDINGS & VISUAL ANALYTICS ---
if st.session_state.match_log.empty:
    st.info("No fixtures recorded yet. Upload a spreadsheet in the sidebar or record a match above.")
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
        st.markdown("💡 **Tip:** Double-click any cell to edit numbers directly. Select rows using the checkboxes on the left and hit `Delete` on your keyboard to remove specific fixtures.")

        edited_df = st.data_editor(
            st.session_state.match_log,
            num_rows="dynamic",
            use_container_width=True,
            key="match_data_editor"
        )

        if not edited_df.equals(st.session_state.match_log):
            st.session_state.match_log = edited_df.reset_index(drop=True)
            st.session_state.match_log.to_csv(DATA_FILE, index=False, encoding="utf-8")
            st.success("Changes saved to database!")
            st.rerun()

        st.write("")
        csv_export = st.session_state.match_log.to_csv(index=False, encoding="utf-8").encode('utf-8')
        st.download_button("📥 Download Full CSV Database", data=csv_export, file_name="effective_mins_database.csv", mime="text/csv")
