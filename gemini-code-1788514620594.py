import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os
import io
import re
import html

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

# Club alias mapping for resilient filename and text detection
CLUB_PATTERNS = [
    ("Nottingham Forest", ["nottingham forest", "nottingham", "nott'm forest", "forest"]),
    ("Manchester United", ["manchester united", "manchester utd", "man utd", "man united"]),
    ("Manchester City", ["manchester city", "man city"]),
    ("Newcastle United", ["newcastle united", "newcastle utd", "newcastle"]),
    ("Crystal Palace", ["crystal palace", "palace"]),
    ("Tottenham", ["tottenham hotspur", "tottenham", "spurs"]),
    ("Aston Villa", ["aston villa", "villa"]),
    ("Coventry City", ["coventry city", "coventry"]),
    ("Hull City", ["hull city", "hull"]),
    ("Ipswich Town", ["ipswich town", "ipswich"]),
    ("Leeds United", ["leeds united", "leeds"]),
    ("Arsenal", ["arsenal"]),
    ("Bournemouth", ["bournemouth", "afc bournemouth"]),
    ("Brentford", ["brentford"]),
    ("Brighton", ["brighton & hove albion", "brighton and hove albion", "brighton"]),
    ("Chelsea", ["chelsea"]),
    ("Everton", ["everton"]),
    ("Fulham", ["fulham"]),
    ("Liverpool", ["liverpool"]),
    ("Sunderland", ["sunderland"])
]

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

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# --- UTILITY HELPERS ---
def clean_val(val) -> str:
    if pd.isna(val) or val is None:
        return "00:00"
    s = str(val).strip().replace("–", "-").replace("—", "-")
    return s if s else "00:00"

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

def clean_html_to_text(html_str: str) -> str:
    """Robust regex-based HTML text extractor that never stalls on unclosed tags."""
    # Strip scripts, styles, and head metadata completely
    clean = re.sub(r'<(script|style|head|noscript|svg)[^>]*>.*?</\1>', ' ', html_str, flags=re.DOTALL | re.IGNORECASE)
    # Convert block elements to linebreaks
    clean = re.sub(r'<(p|div|br|li|tr|h[1-6]|section|article|table)[^>]*>', '\n', clean, flags=re.IGNORECASE)
    # Strip remaining HTML tags
    clean = re.sub(r'<[^>]+>', ' ', clean)
    # Decode HTML entities (&nbsp;, &#39;, etc.)
    clean = html.unescape(clean)
    # Normalise whitespace
    clean = re.sub(r'[ \t]+', ' ', clean)
    clean = re.sub(r'\n\s*\n+', '\n\n', clean)
    return clean

def detect_clubs(filename: str, text: str):
    """
    Detects Home and Away teams. 
    Prioritises the filename order first; falls back to text parsing if missing.
    """
    fn_lower = filename.lower()
    found_in_fn = []

    for canonical, aliases in CLUB_PATTERNS:
        for alias in aliases:
            # Word boundary matching in filename
            pos = fn_lower.find(alias)
            if pos != -1:
                found_in_fn.append((pos, canonical))
                break

    # Deduplicate keeping earliest index per club
    seen = set()
    deduped_fn = []
    for pos, canonical in sorted(found_in_fn):
        if canonical not in seen:
            seen.add(canonical)
            deduped_fn.append((pos, canonical))

    if len(deduped_fn) >= 2:
        return deduped_fn[0][1], deduped_fn[1][1]

    # Fallback to text search directly before 'Actual Play Time'
    header_section = text.split("Actual Play Time")[0] if "Actual Play Time" in text else text
    all_fixtures = list(re.finditer(r"([A-Za-z0-9\s&.-]+?)\s+[Vv]s\s+([A-Za-z0-9\s&.-]+?)(?:\r?\n|<)", header_section))
    if all_fixtures:
        raw_h = all_fixtures[-1].group(1).lower().strip()
        raw_a = all_fixtures[-1].group(2).lower().strip()
        h_club, a_club = None, None
        for canonical, aliases in CLUB_PATTERNS:
            if any(al in raw_h for al in aliases):
                h_club = canonical
            if any(al in raw_a for al in aliases):
                a_club = canonical
        if h_club and a_club:
            return h_club, a_club

    return "Arsenal", "Aston Villa"

def parse_match_data(filename: str, raw_content: str) -> dict:
    """Parses all match stoppage stats with zero AI dependencies."""
    text = clean_html_to_text(raw_content) if ("<html" in raw_content.lower() or "<body" in raw_content.lower()) else raw_content
    stats = {}

    # 1. Teams Detection
    home_team, away_team = detect_clubs(filename, text)
    stats["Home Team"] = home_team
    stats["Away Team"] = away_team

    # 2. Gameweek Detection (Filename first, then text)
    gw_m = re.search(r"(?:Round|GW|Gameweek)\s*(\d+)", filename, re.IGNORECASE)
    if not gw_m:
        gw_m = re.search(r"Round\s+(\d+)", text, re.IGNORECASE)
    stats["Gameweek"] = int(gw_m.group(1)) if gw_m else 1

    # 3. Match Durations
    act_m = re.search(r"Actual\s+(\d{1,2}:\d{2})", text, re.IGNORECASE)
    tot_m = re.search(r"Total\s+(\d{1,2}:\d{2})", text, re.IGNORECASE)
    stats["Actual In-Play"] = act_m.group(1) if act_m else "00:00"
    stats["Total Match Time"] = tot_m.group(1) if tot_m else "90:00"

    # 4. Game Flow Metrics
    stops_m = re.search(r"Game\s*Stops\s*(?:\r?\n|\s+)*(\d+)", text, re.IGNORECASE)
    longest_m = re.search(r"Longest\s*In-Play\s*(?:\r?\n|\s+)*(\d{1,2}:\d{2})", text, re.IGNORECASE)
    stats["Game Stops"] = int(stops_m.group(1)) if stops_m else 0
    stats["Longest In-Play"] = longest_m.group(1) if longest_m else "00:00"

    # 5. Added Time Splits
    ann_m = re.search(r"(\d{1,2}:\d{2})\s*(?:\r?\n|\s+)*Announced", text, re.IGNORECASE)
    act_add_m = re.search(r"(\d{1,2}:\d{2})\s*(?:\r?\n|\s+)*Actual\s+Added", text, re.IGNORECASE)
    stats["Announced Added"] = ann_m.group(1) if ann_m else "00:00"
    stats["Actual Added"] = act_add_m.group(1) if act_add_m else "00:00"
    stats["Played Added"] = "00:00"
    stats["VAR Checks"] = "00:00"

    var_m = re.search(r"(?:Significant\s+)?VAR\s*Checks\s*(?:\r?\n|\s+)*(\d{1,2}:\d{2})", text, re.IGNORECASE)
    if var_m:
        stats["VAR Checks"] = var_m.group(1)

    # 6. Dead-Ball Time Wasted Splits
    wasted_section = text
    if "Time Wasted On" in text:
        wasted_section = text.split("Time Wasted On", 1)[1]

    categories = [
        ("Goal Kicks", r"Goal\s+Kicks"),
        ("Free Kicks", r"Free\s+Kicks"),
        ("Throw Ins", r"Throw\s+Ins"),
        ("Corners", r"Corners"),
        ("Other", r"Other"),
        ("Total Wasted", r"Total")
    ]

    for label, pattern in categories:
        m = re.search(rf"(\d{{1,2}}:\d{{2}})\s*(?:\r?\n|\s+)*{pattern}\s*(?:\r?\n|\s+)*(\d{{1,2}}:\d{{2}})", wasted_section, re.IGNORECASE)
        if m:
            stats[f"Home {label}"] = m.group(1)
            stats[f"Away {label}"] = m.group(2)
        else:
            stats[f"Home {label}"] = "00:00"
            stats[f"Away {label}"] = "00:00"

    return stats

# --- DATABASE INITIALISATION ---
if os.path.exists(DATA_FILE):
    try:
        st.session_state.match_log = pd.read_csv(DATA_FILE, encoding="utf-8")
    except Exception:
        st.session_state.match_log = pd.read_csv(DATA_FILE, encoding="latin1")
else:
    st.session_state.match_log = pd.DataFrame(columns=MATCH_COLUMNS)

for col in MATCH_COLUMNS:
    if col not in st.session_state.match_log.columns:
        st.session_state.match_log[col] = "00:00" if "Time" in col or "In-Play" in col or "Added" in col or "Wasted" in col else 0

st.title("⏱️ EffectiveMins: Premier League Stoppage Tracker")

# --- SIDEBAR: EXCEL MASTER SYNC ---
with st.sidebar:
    st.header("📂 Master Spreadsheet Sync")
    st.caption("Upload your master Excel (.xlsx) or CSV file to update all records instantly.")

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
            st.success(f"Synced {len(df_imported)} fixtures from spreadsheet!")
            st.rerun()
        except Exception as e:
            st.error(f"Error reading file: {str(e)}")

    st.divider()

    blank_template = pd.DataFrame(columns=MATCH_COLUMNS)
    template_buffer = io.BytesIO()
    with pd.ExcelWriter(template_buffer, engine='openpyxl') as writer:
        blank_template.to_excel(writer, index=False, sheet_name="EffectiveMins")

    st.download_button(
        label="📥 Download Blank Template",
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
with st.expander("➕ Log New Fixtures", expanded=st.session_state.match_log.empty):
    ingest_tab1, ingest_tab2 = st.tabs(["📁 Batch File Upload (.html / .txt)", "✍️ Manual Entry Form"])

    # TAB 1: BATCH FILE UPLOADER
    with ingest_tab1:
        st.markdown("Drop one or multiple match reports (**`.html`**, **`.htm`**, or **`.txt`**). **Clubs and Gameweeks are extracted from the file names automatically.**")

        uploaded_files = st.file_uploader(
            "Select match files",
            type=["html", "htm", "txt"],
            accept_multiple_files=True,
            label_visibility="collapsed",
            key=f"batch_uploader_{st.session_state.uploader_key}"
        )

        if uploaded_files:
            parsed_batch = []
            for f in uploaded_files:
                f.seek(0)
                bytes_data = f.read()
                try:
                    content_str = bytes_data.decode("utf-8")
                except UnicodeDecodeError:
                    content_str = bytes_data.decode("latin1", errors="ignore")

                parsed = parse_match_data(f.name, content_str)
                parsed["_filename"] = f.name
                parsed_batch.append(parsed)

            df_preview = pd.DataFrame(parsed_batch)

            st.write("---")
            st.markdown(f"##### 🔍 Staged Matches ({len(df_preview)} Found)")
            st.caption("Review the extracted fixtures below before committing them to the database:")

            preview_cols = ["Gameweek", "Home Team", "Away Team", "Actual In-Play", "Total Match Time", "Home Total Wasted", "Away Total Wasted"]
            st.dataframe(df_preview[preview_cols], use_container_width=True, hide_index=True)

            st.write("")
            btn_c1, btn_c2 = st.columns([2, 1])
            with btn_c1:
                save_batch_btn = st.button(f"🚀 Save All {len(df_preview)} Matches to Database", type="primary", use_container_width=True)
            with btn_c2:
                undo_btn = st.button("↩️ Undo Last Logged Entry", type="secondary", use_container_width=True)

            if undo_btn:
                if not st.session_state.match_log.empty:
                    removed = st.session_state.match_log.iloc[-1]
                    st.session_state.match_log = st.session_state.match_log.iloc[:-1].reset_index(drop=True)
                    st.session_state.match_log.to_csv(DATA_FILE, index=False, encoding="utf-8")
                    st.warning(f"Undid: {removed['Home Team']} vs {removed['Away Team']}")
                    st.rerun()
                else:
                    st.info("No records to undo.")

            if save_batch_btn:
                for match in parsed_batch:
                    clean_entry = {col: match.get(col, "00:00") for col in MATCH_COLUMNS}
                    clean_entry["Gameweek"] = int(clean_entry["Gameweek"])
                    clean_entry["Game Stops"] = int(clean_entry["Game Stops"])

                    existing_mask = (
                        (st.session_state.match_log["Gameweek"] == clean_entry["Gameweek"]) &
                        (st.session_state.match_log["Home Team"] == clean_entry["Home Team"]) &
                        (st.session_state.match_log["Away Team"] == clean_entry["Away Team"])
                    )

                    if existing_mask.any():
                        for k, v in clean_entry.items():
                            st.session_state.match_log.loc[existing_mask, k] = v
                    else:
                        st.session_state.match_log = pd.concat(
                            [st.session_state.match_log, pd.DataFrame([clean_entry])],
                            ignore_index=True
                        )

                st.session_state.match_log.to_csv(DATA_FILE, index=False, encoding="utf-8")
                st.session_state.uploader_key += 1
                st.success(f"Recorded {len(parsed_batch)} matches successfully!")
                st.rerun()

    # TAB 2: MANUAL ENTRY FORM
    with ingest_tab2:
        with st.form("manual_entry_form", clear_on_submit=True):
            mc1, mc2, mc3 = st.columns(3)
            with mc1:
                man_gw = st.number_input("Gameweek", min_value=1, max_value=38, value=1, step=1)
            with mc2:
                man_home = st.selectbox("Home Team", PL_TEAMS, index=0)
            with mc3:
                man_away = st.selectbox("Away Team", PL_TEAMS, index=1)

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
                    "Gameweek": int(man_gw),
                    "Home Team": man_home,
                    "Away Team": man_away,
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
                st.success(f"Recorded {man_home} vs {man_away} manually!")
                st.rerun()

st.divider()

# --- STANDINGS & VISUAL ANALYTICS ---
if st.session_state.match_log.empty:
    st.info("No fixtures recorded yet. Upload match files above to populate the league table.")
else:
    tab1, tab2 = st.tabs(["🏆 Team Standings (Averages)", "📝 Live Spreadsheet Editor & Export"])

    with tab1:
        team_rows = []
        for _, r in st.session_state.match_log.iterrows():
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

        # --- TWITTER CARD GENERATOR ---
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
