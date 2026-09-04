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

# Official Premier League CDN Badges
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
    clean = re.sub(r'<(script|style|head|noscript|svg)[^>]*>.*?</\1>', ' ', html_str, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<(p|div|br|li|tr|h[1-6]|section|article|table)[^>]*>', '\n', clean, flags=re.IGNORECASE)
    clean = re.sub(r'<[^>]+>', ' ', clean)
    clean = html.unescape(clean)
    clean = re.sub(r'[ \t]+', ' ', clean)
    clean = re.sub(r'\n\s*\n+', '\n\n', clean)
    return clean

def detect_clubs(filename: str, text: str):
    fn_lower = filename.lower()
    found_in_fn = []

    for canonical, aliases in CLUB_PATTERNS:
        for alias in aliases:
            pos = fn_lower.find(alias)
            if pos != -1:
                found_in_fn.append((pos, canonical))
                break

    seen = set()
    deduped_fn = []
    for pos, canonical in sorted(found_in_fn):
        if canonical not in seen:
            seen.add(canonical)
            deduped_fn.append((pos, canonical))

    if len(deduped_fn) >= 2:
        return deduped_fn[0][1], deduped_fn[1][1]

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
    text = clean_html_to_text(raw_content) if ("<html" in raw_content.lower() or "<body" in raw_content.lower()) else raw_content
    stats = {}

    home_team, away_team = detect_clubs(filename, text)
    stats["Home Team"] = home_team
    stats["Away Team"] = away_team

    gw_m = re.search(r"Premier\s+League,?\s+Round\s+(\d+)", text, re.IGNORECASE)
    if not gw_m:
        gw_m = re.search(r"(?:Round|GW|Gameweek)\s*(\d+)", filename, re.IGNORECASE)
    stats["Gameweek"] = int(gw_m.group(1)) if gw_m else 1

    play_section = text
    if "Actual Play Time" in text:
        play_section = text.split("Actual Play Time", 1)[1]
        split_m = re.search(r"Time\s+Wasted", play_section, re.IGNORECASE)
        if split_m:
            play_section = play_section[:split_m.start()]

    act_m = re.search(r"Actual\s+(\d+:\d{2})", play_section, re.IGNORECASE)
    tot_m = re.search(r"Total\s+(\d+:\d{2})", play_section, re.IGNORECASE)
    stats["Actual In-Play"] = act_m.group(1) if act_m else "00:00"
    stats["Total Match Time"] = tot_m.group(1) if tot_m else "90:00"

    stops_m = re.search(r"Game\s*Stops\s*(?:\r?\n|\s+)*(\d+)", text, re.IGNORECASE)
    longest_m = re.search(r"Longest\s*In-Play\s*(?:\r?\n|\s+)*(\d+:\d{2})", text, re.IGNORECASE)
    stats["Game Stops"] = int(stops_m.group(1)) if stops_m else 0
    stats["Longest In-Play"] = longest_m.group(1) if longest_m else "00:00"

    ann_m = re.search(r"(\d+:\d{2})\s*(?:\r?\n|\s+)*Announced", text, re.IGNORECASE)
    act_add_m = re.search(r"(\d+:\d{2})\s*(?:\r?\n|\s+)*Actual\s+Added", text, re.IGNORECASE)
    ply_add_m = re.search(r"(\d+:\d{2})\s*(?:\r?\n|\s+)*Played", text, re.IGNORECASE)
    stats["Announced Added"] = ann_m.group(1) if ann_m else "00:00"
    stats["Actual Added"] = act_add_m.group(1) if act_add_m else "00:00"
    stats["Played Added"] = ply_add_m.group(1) if ply_add_m else "00:00"
    stats["VAR Checks"] = "00:00"

    var_m = re.search(r"(?:Significant\s+)?VAR\s*Checks\s*(?:\r?\n|\s+)*(\d+:\d{2})", text, re.IGNORECASE)
    if var_m:
        stats["VAR Checks"] = var_m.group(1)

    wasted_match = re.search(r"Time\s+Wasted(?:\s+On)?", text, re.IGNORECASE)
    wasted_section = text[wasted_match.end():] if wasted_match else text

    categories = [
        ("Goal Kicks", r"Goal\s+Kicks"),
        ("Free Kicks", r"Free\s+Kicks"),
        ("Throw Ins", r"Throw\s+Ins"),
        ("Corners", r"Corners"),
        ("Other", r"Other"),
        ("Total Wasted", r"Total(?:\s+Wasted)?")
    ]

    for label, pattern in categories:
        m = re.search(rf"(\d+:\d{{2}})\s*(?:\r?\n|\s+)+{pattern}\s*(?:\r?\n|\s+)+(\d+:\d{{2}})", wasted_section, re.IGNORECASE)
        if m:
            stats[f"Home {label}"] = m.group(1)
            stats[f"Away {label}"] = m.group(2)
        else:
            stats[f"Home {label}"] = "00:00"
            stats[f"Away {label}"] = "00:00"

    stats["_is_valid"] = not (stats["Actual In-Play"] == "00:00" and stats["Home Total Wasted"] == "00:00")
    return stats

# --- DATABASE LOAD ---
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
        if "confirm_delete" not in st.session_state:
            st.session_state.confirm_delete = False

        if not st.session_state.confirm_delete:
            if st.button("🗑️ Reset Entire Database", type="secondary", use_container_width=True):
                st.session_state.confirm_delete = True
                st.rerun()
        else:
            st.error("⚠️ Are you sure? This will permanently erase all saved fixtures.")
            del_c1, del_c2 = st.columns(2)
            with del_c1:
                if st.button("Yes, Delete All", type="primary", use_container_width=True):
                    st.session_state.match_log = pd.DataFrame(columns=MATCH_COLUMNS)
                    if os.path.exists(DATA_FILE):
                        os.remove(DATA_FILE)
                    st.session_state.confirm_delete = False
                    st.warning("All records cleared.")
                    st.rerun()
            with del_c2:
                if st.button("Cancel", type="secondary", use_container_width=True):
                    st.session_state.confirm_delete = False
                    st.rerun()

    st.divider()
    st.markdown("**@EffectiveMins** Analytics Engine")

# --- MATCH INGESTION SECTION ---
with st.expander("➕ Log New Fixtures", expanded=st.session_state.match_log.empty):
    ingest_tab1, ingest_tab2 = st.tabs(["📁 Batch File Upload (.txt / .html)", "✍️ Manual Entry Form"])

    with ingest_tab1:
        st.markdown("""
        Drag and drop your saved match files.
        > **Firefox Tip:** Save reports using **Save as type: Text Files (*.txt)** so stoppage numbers are included.
        """)

        uploaded_files = st.file_uploader(
            "Select match files",
            type=["txt", "html", "htm"],
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
                parsed["Status"] = "Ready" if parsed["_is_valid"] else "⚠️ Missing Stoppage Data"
                parsed_batch.append(parsed)

            df_preview = pd.DataFrame(parsed_batch)

            st.write("---")
            st.markdown(f"##### 🔍 Staged Matches ({len(df_preview)} Detected)")

            preview_cols = ["Status", "Gameweek", "Home Team", "Away Team", "Actual In-Play", "Total Match Time", "Home Total Wasted", "Away Total Wasted"]
            st.dataframe(df_preview[preview_cols], use_container_width=True, hide_index=True)

            valid_matches = [m for m in parsed_batch if m["_is_valid"]]
            invalid_count = len(parsed_batch) - len(valid_matches)

            if invalid_count > 0:
                st.warning(f"{invalid_count} file(s) lack stoppage numbers. Only the {len(valid_matches)} valid fixture(s) will be committed.")

            st.write("")
            btn_c1, btn_c2 = st.columns([2, 1])
            with btn_c1:
                save_batch_btn = st.button(
                    f"🚀 Save {len(valid_matches)} Valid Match(es) to Database",
                    type="primary",
                    use_container_width=True,
                    disabled=(len(valid_matches) == 0)
                )
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
                for match in valid_matches:
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
                st.success(f"Successfully recorded {len(valid_matches)} fixtures!")
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
                man_aco 