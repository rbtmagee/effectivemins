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

# Comprehensive Domestic & European Club Badge CDN Library
CLUB_BADGES = {
    # Premier League
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
    "Tottenham": "https://resources.premierleague.com/premierleague/badges/t6.png",

    # UEFA Champions League Contenders
    "Real Madrid": "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/131",
    "Barcelona": "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/133",
    "Bayern Munich": "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/156",
    "Paris Saint-Germain": "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/164",
    "Borussia Dortmund": "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/157",
    "Bayer Leverkusen": "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/154",
    "RB Leipzig": "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/6321",
    "Inter Milan": "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/118",
    "AC Milan": "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/121",
    "Juventus": "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/128",
    "Atalanta": "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/119",
    "Atletico Madrid": "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/132",
    "Sporting CP": "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/549",
    "Benfica": "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/550",
    "Porto": "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/551",
    "PSV Eindhoven": "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/541",
    "Feyenoord": "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/540",
    "Celtic": "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/570",
    "Monaco": "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/166"
}

ALL_KNOWN_TEAMS = sorted(list(CLUB_BADGES.keys()))

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
    ("Sunderland", ["sunderland"]),
    ("Real Madrid", ["real madrid", "madrid"]),
    ("Barcelona", ["barcelona", "barca"]),
    ("Bayern Munich", ["bayern munich", "bayern münchen", "bayern"]),
    ("Paris Saint-Germain", ["paris saint-germain", "paris saint germain", "psg", "paris sg"]),
    ("Borussia Dortmund", ["borussia dortmund", "dortmund", "bvb"]),
    ("Bayer Leverkusen", ["bayer leverkusen", "leverkusen"]),
    ("RB Leipzig", ["rb leipzig", "leipzig"]),
    ("Inter Milan", ["inter milan", "internazionale", "inter"]),
    ("AC Milan", ["ac milan", "milan"]),
    ("Juventus", ["juventus", "juve"]),
    ("Atalanta", ["atalanta"]),
    ("Atletico Madrid", ["atletico madrid", "atlético madrid", "atletico"]),
    ("Sporting CP", ["sporting cp", "sporting lisbon", "sporting"]),
    ("Benfica", ["benfica", "sl benfica"]),
    ("Porto", ["fc porto", "porto"]),
    ("PSV Eindhoven", ["psv eindhoven", "psv"]),
    ("Feyenoord", ["feyenoord"]),
    ("Celtic", ["celtic"]),
    ("Monaco", ["as monaco", "monaco"])
]

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
    # Match Performance & Creation Metrics
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

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# --- UTILITY HELPERS ---
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

def to_int(val, default=0) -> int:
    try:
        s = str(val).replace("%", "").strip()
        return int(float(s))
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

def clean_html_to_text(html_str: str) -> str:
    clean = re.sub(r'<(script|style|head|noscript|svg)[^>]*>.*?</\1>', ' ', html_str, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<(p|div|br|li|tr|h[1-6]|section|article|table)[^>]*>', '\n', clean, flags=re.IGNORECASE)
    clean = re.sub(r'<[^>]+>', ' ', clean)
    clean = html.unescape(clean)
    clean = re.sub(r'[ \t]+', ' ', clean)
    clean = re.sub(r'\n\s*\n+', '\n\n', clean)
    return clean

def detect_competition(filename: str, text: str) -> str:
    combined = f"{filename} {text}".lower()
    if any(marker in combined for marker in ["champions league", "champions-league", "ucl", "uefa champions"]):
        return "Champions League"
    return "Premier League"

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

def extract_metric_pair(text: str, label_regex: str, default=("0", "0")):
    """Extracts [HomeValue]\n[Label]\n[AwayValue] from 365Scores statistics sections."""
    pattern = rf"([^\r\n]+)\r?\n\s*{label_regex}\s*\r?\n\s*([^\r\n]+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return default

def parse_match_data(filename: str, raw_content: str) -> dict:
    text = clean_html_to_text(raw_content) if ("<html" in raw_content.lower() or "<body" in raw_content.lower()) else raw_content
    stats = {}

    stats["Competition"] = detect_competition(filename, text)

    home_team, away_team = detect_clubs(filename, text)
    stats["Home Team"] = home_team
    stats["Away Team"] = away_team

    gw_m = re.search(r"(?:Premier\s+League|Champions\s+League),?\s+(?:Round|Matchday|MD)\s+(\d+)", text, re.IGNORECASE)
    if not gw_m:
        gw_m = re.search(r"(?:Round|Matchday|MD|GW|Gameweek)\s*(\d+)", filename, re.IGNORECASE)
    if not gw_m:
        gw_m = re.search(r"(?:Round|Matchday)\s+(\d+)", text, re.IGNORECASE)
    stats["Gameweek"] = int(gw_m.group(1)) if gw_m else 1

    # 1. Stoppage & Timing Section
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

    # 2. Performance, Territory & Chance Creation Section
    stats_section = text.split("Top Stats", 1)[1] if "Top Stats" in text else text

    stats["Home Possession"], stats["Away Possession"] = extract_metric_pair(stats_section, r"Possession", ("50%", "50%"))
    stats["Home xG"], stats["Away xG"] = extract_metric_pair(stats_section, r"Expected\s+Goals", ("0.00", "0.00"))
    stats["Home Total Shots"], stats["Away Total Shots"] = extract_metric_pair(stats_section, r"Total\s+Shots", ("0", "0"))
    stats["Home Shots On Target"], stats["Away Shots On Target"] = extract_metric_pair(stats_section, r"Shots\s+On\s+Target", ("0", "0"))

    # Granular passing & shooting sections
    stats["Home xGOT"], stats["Away xGOT"] = extract_metric_pair(stats_section, r"Expected\s+Goals\s+On\s+Target", (stats["Home xG"], stats["Away xG"]))
    stats["Home Shots Inside Box"], stats["Away Shots Inside Box"] = extract_metric_pair(stats_section, r"Shots\s+Inside\s+The\s+Box", ("0", "0"))
    stats["Home Passes Opp Half"], stats["Away Passes Opp Half"] = extract_metric_pair(stats_section, r"Passes\s+Opposition\s+Half", ("0", "0"))
    stats["Home Passes Final Third"], stats["Away Passes Final Third"] = extract_metric_pair(stats_section, r"Passes\s+Into\s+Final\s+Third", ("0", "0"))
    stats["Home Key Passes"], stats["Away Key Passes"] = extract_metric_pair(stats_section, r"Key\s+Passes", ("0", "0"))
    stats["Home Final Third Won"], stats["Away Final Third Won"] = extract_metric_pair(stats_section, r"Final\s+Third\s+Possession\s+Won", ("0", "0"))
    stats["Home Possession Lost"], stats["Away Possession Lost"] = extract_metric_pair(stats_section, r"Possession\s+Lost", ("0", "0"))
    stats["Home Fouls"], stats["Away Fouls"] = extract_metric_pair(stats_section, r"Fouls", ("0", "0"))
    stats["Home Yellow Cards"], stats["Away Yellow Cards"] = extract_metric_pair(stats_section, r"Yellow\s+Cards", ("0", "0"))
    stats["Home Red Cards"], stats["Away Red Cards"] = extract_metric_pair(stats_section, r"Red\s+Cards", ("0", "0"))

    stats["_is_valid"] = not (stats["Actual In-Play"] == "00:00" and stats["Home Total Wasted"] == "00:00")
    return stats

# --- DATABASE LOAD WITH SCHEMA RECOVERY ---
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

# Backfill new metric columns if loading an older CSV database
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

# --- SIDEBAR: COMPETITION FILTER & DATA SYNC ---
with st.sidebar:
    st.header("🏆 Competition Filter")
    active_competition = st.radio(
        "Active Dashboard:",
        ["Premier League", "Champions League", "All Competitions"],
        index=0
    )

    st.divider()
    st.header("📂 Master Spreadsheet Sync")
    st.caption("Upload your master Excel (.xlsx) or CSV file to update all records instantly.")

    uploaded_master = st.file_uploader("Upload Spreadsheet", type=["xlsx", "csv"], label_visibility="collapsed")
    if uploaded_master is not None:
        try:
            if uploaded_master.name.endswith(".xlsx"):
                df_imported = pd.read_excel(uploaded_master)
            else:
                df_imported = pd.read_csv(uploaded_master)

            if "Competition" not in df_imported.columns:
                df_imported.insert(0, "Competition", "Premier League")
            else:
                df_imported["Competition"] = df_imported["Competition"].fillna("Premier League").replace("", "Premier League")

            for col in MATCH_COLUMNS:
                if col not in df_imported.columns:
                    df_imported[col] = "00:00" if "Time" in col else "0"

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
    st.write(f"Total Logged Fixtures: `{len(st.session_state.match_log)}`")

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
    st.markdown("**@EffectiveMins** Analytics Platform")

# --- MATCH INGESTION SECTION ---
with st.expander("➕ Log New Fixtures", expanded=st.session_state.match_log.empty):
    ingest_tab1, ingest_tab2 = st.tabs(["📁 Batch File Upload (.txt / .html)", "✍️ Manual Entry Form"])

    with ingest_tab1:
        st.markdown("""
        Drag and drop your saved 365Scores match files.
        > **Full Stats Extraction:** Automatically extracts in-play times, dead-ball waste, $xG$, $xGOT$, territory, turnovers, and discipline.
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

            preview_cols = [
                "Status", "Competition", "Gameweek", "Home Team", "Away Team",
                "Actual In-Play", "Home xG", "Away xG", "Home Total Wasted", "Away Total Wasted"
            ]
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
                        (st.session_state.match_log["Competition"] == clean_entry["Competition"]) &
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
            mc0, mc1, mc2, mc3 = st.columns(4)
            with mc0:
                man_comp = st.selectbox("Competition", ["Premier League", "Champions League"])
            with mc1:
                man_gw = st.number_input("Round / Matchday", min_value=1, max_value=38, value=1, step=1)
            with mc2:
                man_home = st.selectbox("Home Team", ALL_KNOWN_TEAMS, index=0)
            with mc3:
                man_away = st.selectbox("Away Team", ALL_KNOWN_TEAMS, index=1)

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

            st.markdown("##### Performance & Shot Quality (Home vs Away)")
            sh1, sh2, sh3, sh4 = st.columns(4)
            with sh1:
                st.caption("xG")
                man_hxg = st.text_input("Home xG", placeholder="1.88")
                man_axg = st.text_input("Away xG", placeholder="0.20")
            with sh2:
                st.caption("Possession %")
                man_hpos = st.text_input("Home Pos %", placeholder="64%")
                man_apos = st.text_input("Away Pos %", placeholder="36%")
            with sh3:
                st.caption("Final Third Possession Won")
                man_hftw = st.text_input("Home FT Won", placeholder="6")
                man_aftw = st.text_input("Away FT Won", placeholder="2")
            with sh4:
                st.caption("Fouls Committed")
                man_hfl = st.text_input("Home Fouls", placeholder="10")
                man_afl = st.text_input("Away Fouls", placeholder="13")

            if st.form_submit_button("Save Record Manually", type="primary"):
                manual_row = {
                    "Competition": man_comp,
                    "Gameweek": int(man_gw),
                    "Home Team": man_home,
                    "Away Team": man_away,
                    "Actual In-Play": clean_val(man_inplay),
                    "Total Match Time": clean_val(man_total, "90:00"),
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
                    "Away Total Wasted": clean_val(man_atot),
                    "Home Possession": clean_val(man_hpos, "50%"),
                    "Away Possession": clean_val(man_apos, "50%"),
                    "Home xG": clean_val(man_hxg, "0.00"),
                    "Away xG": clean_val(man_axg, "0.00"),
                    "Home xGOT": clean_val(man_hxg, "0.00"),
                    "Away xGOT": clean_val(man_axg, "0.00"),
                    "Home Total Shots": "0", "Away Total Shots": "0",
                    "Home Shots On Target": "0", "Away Shots On Target": "0",
                    "Home Shots Inside Box": "0", "Away Shots Inside Box": "0",
                    "Home Passes Opp Half": "0", "Away Passes Opp Half": "0",
                    "Home Passes Final Third": "0", "Away Passes Final Third": "0",
                    "Home Key Passes": "0", "Away Key Passes": "0",
                    "Home Final Third Won": clean_val(man_hftw, "0"),
                    "Away Final Third Won": clean_val(man_aftw, "0"),
                    "Home Possession Lost": "0", "Away Possession Lost": "0",
                    "Home Fouls": clean_val(man_hfl, "0"),
                    "Away Fouls": clean_val(man_afl, "0"),
                    "Home Yellow Cards": "0", "Away Yellow Cards": "0",
                    "Home Red Cards": "0", "Away Red Cards": "0"
                }
                st.session_state.match_log = pd.concat([st.session_state.match_log, pd.DataFrame([manual_row])], ignore_index=True)
                st.session_state.match_log.to_csv(DATA_FILE, index=False, encoding="utf-8")
                st.success(f"Recorded {man_home} vs {man_away} ({man_comp}) manually!")
                st.rerun()

st.divider()

# --- FILTER DATA BY SELECTED COMPETITION ---
if active_competition == "All Competitions":
    active_df = st.session_state.match_log.copy()
else:
    active_df = st.session_state.match_log[st.session_state.match_log["Competition"] == active_competition].copy()

# --- STANDINGS & VISUAL ANALYTICS ---
if active_df.empty:
    st.info(f"No fixtures recorded for **{active_competition}** yet. Select **All Competitions** in the sidebar or upload match files above.")
else:
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        f"🏆 {active_competition} Standings",
        "🎯 Control, xG & Territory",
        "🌊 Flow & Disruption",
        "⏱️ Added Time Integrity",
        "📺 VAR Stoppage Impact",
        "📝 Live Spreadsheet Editor & Export"
    ])

    # ==========================
    # TAB 1: MAIN STANDINGS
    # ==========================
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
            avg_stops = round(total_stops / total_matches, 1)

            avg_home_wasted_sec = h_wasted / h_count if h_count > 0 else 0
            avg_away_wasted_sec = a_wasted / a_count if a_count > 0 else 0

            standings_rows.append({
                "Team": team,
                "Badge": CLUB_BADGES.get(team, "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/default"),
                "Matches": total_matches,
                "Home_Matches": h_count,
                "Away_Matches": a_count,
                "Total_Stops": total_stops,
                "Avg_Stops": avg_stops,
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
            "Badge", "Team", "Matches", "Effective In-Play %", "Avg In-Play",
            "Avg Total Wasted", "Avg Home Wasted", "Avg Away Wasted",
            "Avg Free Kicks Delay", "Avg Goal Kicks Delay",
            "Avg Throw Ins Delay", "Avg Corners Delay", "Avg Other Delay"
        ]

        st.dataframe(
            standings[display_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Badge": st.column_config.ImageColumn("Badge", width="small")
            }
        )

        st.divider()

        # --- TWITTER INFOGRAPHIC GENERATOR ---
        st.subheader("Generate Graphic for @EffectiveMins")

        col_select, col_type = st.columns([1, 1.8])
        with col_select:
            alphabetical_teams = sorted(standings["Team"].unique())
            selected_team = st.selectbox("Select Club", alphabetical_teams)
        with col_type:
            chart_type = st.radio(
                "Select Graphic Type:",
                [
                    "Dead-Ball Delay Profile (Bar Chart)",
                    "In-Play Trend Across Rounds (Line Chart)",
                    "Time Wasting Trend Across Rounds (Line Chart)",
                    "High Press & Chance Creation (Bar Chart)"
                ],
                horizontal=False
            )

        t_row = standings[standings["Team"] == selected_team].iloc[0]
        badge_url = CLUB_BADGES.get(selected_team, "")

        cg1, cg2 = st.columns([1.3, 1])

        team_fixtures = active_df[
            (active_df["Home Team"] == selected_team) |
            (active_df["Away Team"] == selected_team)
        ].copy()
        team_fixtures = team_fixtures.sort_values(by="Gameweek").reset_index(drop=True)

        if chart_type == "Dead-Ball Delay Profile (Bar Chart)":
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
                ax.set_title(f"{selected_team.upper()} — Dead-Ball Delay Profile ({active_competition})", color="#ffffff", fontsize=15, weight="bold", pad=15)
                fig.text(0.82, 0.02, "@EffectiveMins", color="#888888", fontsize=10, style='italic')

                st.pyplot(fig)

            with cg2:
                if badge_url:
                    st.image(badge_url, width=70)
                st.markdown("### Ready-to-Post Copy")
                comp_tag = "#UCL" if "Champions" in active_competition else "#PremierLeague #PL"
                post_text = f"""⏱️ Stoppage Breakdown: {selected_team} ({active_competition})

• Effective Playing Time: {t_row['Effective In-Play %']}% ({t_row['Avg In-Play']})
• Average Time Lost: {t_row['Avg Total Wasted']} per 90
• Home Delay Avg: {t_row['Avg Home Wasted']} | Away Delay Avg: {t_row['Avg Away Wasted']}

Biggest delay factors:
1. Free Kicks: {t_row['Avg Free Kicks Delay']}
2. Goal Kicks: {t_row['Avg Goal Kicks Delay']}
3. Throw Ins: {t_row['Avg Throw Ins Delay']}

Data tracked by @EffectiveMins {comp_tag}"""
                st.text_area("Draft Post", value=post_text, height=200)

        elif chart_type == "In-Play Trend Across Rounds (Line Chart)":
            with cg1:
                fig, ax = plt.subplots(figsize=(10, 5.5), facecolor="#0e1621")
                ax.set_facecolor("#0e1621")

                x_labels = []
                y_vals = []
                time_strings = []

                for _, match in team_fixtures.iterrows():
                    is_home = (match["Home Team"] == selected_team)
                    opp = match["Away Team"] if is_home else match["Home Team"]
                    venue = "H" if is_home else "A"
                    label_prefix = "MD" if "Champions" in match["Competition"] else "GW"
                    x_labels.append(f"{label_prefix}{match['Gameweek']}\nvs {opp[:3].upper()} ({venue})")
                    inplay_secs = time_to_seconds(match["Actual In-Play"])
                    y_vals.append(inplay_secs / 60.0)
                    time_strings.append(match["Actual In-Play"])

                ax.plot(range(len(x_labels)), y_vals, color="#00d2ff", linewidth=2.8, marker="o", markersize=9, markerfacecolor="#ffffff", markeredgecolor="#00d2ff", zorder=4)
                ax.axhline(60.0, color="#ff495c", linestyle="--", alpha=0.55, linewidth=1.5, label="60-Min Benchmark", zorder=2)

                for idx, (val, t_str) in enumerate(zip(y_vals, time_strings)):
                    ax.annotate(
                        t_str,
                        (idx, val),
                        textcoords="offset points",
                        xytext=(0, 11),
                        ha="center",
                        color="#ffffff",
                        fontsize=10,
                        weight="bold"
                    )

                ax.set_xticks(range(len(x_labels)))
                ax.set_xticklabels(x_labels, color="#ffffff", fontsize=10)
                ax.tick_params(colors="#ffffff", labelsize=10)
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                ax.spines['bottom'].set_color('#888888')
                ax.spines['left'].set_color('#888888')
                ax.set_ylabel("In-Play Minutes", color="#ffffff", fontsize=11)
                ax.set_title(f"{selected_team.upper()} — In-Play Fluctuations ({active_competition})", color="#ffffff", fontsize=15, weight="bold", pad=15)
                ax.grid(color="#ffffff", alpha=0.08, linestyle=":")
                ax.legend(loc="lower right", facecolor="#151e22", edgecolor="#3a4145", labelcolor="#ffffff")
                fig.text(0.82, 0.02, "@EffectiveMins", color="#888888", fontsize=10, style='italic')

                if y_vals:
                    ax.set_ylim(min(y_vals) - 4, max(y_vals) + 5)

                st.pyplot(fig)

            with cg2:
                if badge_url:
                    st.image(badge_url, width=70)
                st.markdown("### Ready-to-Post Copy")

                breakdown_lines = []
                for _, match in team_fixtures.iterrows():
                    is_home = (match["Home Team"] == selected_team)
                    opp = match["Away Team"] if is_home else match["Home Team"]
                    loc = "H" if is_home else "A"
                    label_prefix = "MD" if "Champions" in match["Competition"] else "GW"
                    breakdown_lines.append(f"• {label_prefix}{match['Gameweek']} vs {opp} ({loc}): {match['Actual In-Play']}")

                formatted_breakdown = "\n".join(breakdown_lines)
                comp_tag = "#UCL" if "Champions" in active_competition else "#PremierLeague #PL"

                trend_post = f"""📈 Effective Playing Time Trend: {selected_team} ({active_competition})

Round-by-round breakdown:
{formatted_breakdown}

• Average: {t_row['Avg In-Play']} ({t_row['Effective In-Play %']}% of 90)
• High: {seconds_to_time(max(time_to_seconds(m['Actual In-Play']) for _, m in team_fixtures.iterrows()))}
• Low: {seconds_to_time(min(time_to_seconds(m['Actual In-Play']) for _, m in team_fixtures.iterrows()))}

Follow @EffectiveMins for full stoppage analytics {comp_tag} #{selected_team.replace(' ', '')}"""
                st.text_area("Draft Trend Post", value=trend_post, height=230)

        elif chart_type == "Time Wasting Trend Across Rounds (Line Chart)":
            with cg1:
                fig, ax = plt.subplots(figsize=(10, 5.5), facecolor="#0e1621")
                ax.set_facecolor("#0e1621")

                x_labels = []
                waste_vals = []
                waste_strings = []

                for _, match in team_fixtures.iterrows():
                    is_home = (match["Home Team"] == selected_team)
                    opp = match["Away Team"] if is_home else match["Home Team"]
                    venue = "H" if is_home else "A"
                    label_prefix = "MD" if "Champions" in match["Competition"] else "GW"
                    x_labels.append(f"{label_prefix}{match['Gameweek']}\nvs {opp[:3].upper()} ({venue})")

                    waste_col = "Home Total Wasted" if is_home else "Away Total Wasted"
                    waste_secs = time_to_seconds(match[waste_col])
                    waste_vals.append(waste_secs / 60.0)
                    waste_strings.append(match[waste_col])

                ax.plot(range(len(x_labels)), waste_vals, color="#ffb800", linewidth=2.8, marker="s", markersize=9, markerfacecolor="#ffffff", markeredgecolor="#ffb800", zorder=4)

                for idx, (val, t_str) in enumerate(zip(waste_vals, waste_strings)):
                    ax.annotate(
                        t_str,
                        (idx, val),
                        textcoords="offset points",
                        xytext=(0, 11),
                        ha="center",
                        color="#ffffff",
                        fontsize=10,
                        weight="bold"
                    )

                ax.set_xticks(range(len(x_labels)))
                ax.set_xticklabels(x_labels, color="#ffffff", fontsize=10)
                ax.tick_params(colors="#ffffff", labelsize=10)
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                ax.spines['bottom'].set_color('#888888')
                ax.spines['left'].set_color('#888888')
                ax.set_ylabel("Minutes Wasted / Delayed", color="#ffffff", fontsize=11)
                ax.set_title(f"{selected_team.upper()} — Dead-Ball Delay ({active_competition})", color="#ffffff", fontsize=15, weight="bold", pad=15)
                ax.grid(color="#ffffff", alpha=0.08, linestyle=":")
                fig.text(0.82, 0.02, "@EffectiveMins", color="#888888", fontsize=10, style='italic')

                if waste_vals:
                    ax.set_ylim(min(waste_vals) - 3, max(waste_vals) + 4)

                st.pyplot(fig)

            with cg2:
                if badge_url:
                    st.image(badge_url, width=70)
                st.markdown("### Ready-to-Post Copy")

                waste_breakdown = []
                for _, match in team_fixtures.iterrows():
                    is_home = (match["Home Team"] == selected_team)
                    opp = match["Away Team"] if is_home else match["Home Team"]
                    loc = "H" if is_home else "A"
                    w_col = "Home Total Wasted" if is_home else "Away Total Wasted"
                    label_prefix = "MD" if "Champions" in match["Competition"] else "GW"
                    waste_breakdown.append(f"• {label_prefix}{match['Gameweek']} vs {opp} ({loc}): {match[w_col]}")

                formatted_waste = "\n".join(waste_breakdown)
                comp_tag = "#UCL" if "Champions" in active_competition else "#PremierLeague #PL"

                waste_post = f"""⏱️ Dead-Ball Time Wasted: {selected_team} ({active_competition})

Round-by-round stoppage delay:
{formatted_waste}

• Average Lost: {t_row['Avg Total Wasted']} per match
• Home Delay Avg: {t_row['Avg Home Wasted']} | Away Delay Avg: {t_row['Avg Away Wasted']}
• Most Wasted: {seconds_to_time(max(time_to_seconds(m['Home Total Wasted' if m['Home Team'] == selected_team else 'Away Total Wasted']) for _, m in team_fixtures.iterrows()))}

Full stoppage stats tracked by @EffectiveMins {comp_tag} #{selected_team.replace(' ', '')}"""
                st.text_area("Draft Waste Trend Post", value=waste_post, height=230)

        # OPTION 4: HIGH PRESS & CHANCE CREATION PROFILE
        else:
            with cg1:
                fig, ax = plt.subplots(figsize=(10, 5.5), facecolor="#0e1621")
                ax.set_facecolor("#0e1621")

                # Aggregate team advanced performance stats
                t_xg = 0.0
                t_sot = 0.0
                t_ft_won = 0.0
                t_fouls = 0.0
                for _, m in team_fixtures.iterrows():
                    is_h = (m["Home Team"] == selected_team)
                    t_xg += to_float(m["Home xG"] if is_h else m["Away xG"])
                    t_sot += to_float(m["Home Shots On Target"] if is_h else m["Away Shots On Target"])
                    t_ft_won += to_float(m["Home Final Third Won"] if is_h else m["Away Final Third Won"])
                    t_fouls += to_float(m["Home Fouls"] if is_h else m["Away Fouls"])

                m_count = len(team_fixtures) if len(team_fixtures) > 0 else 1
                cat_names = ["xG per 90", "Shots On Target / 90", "High Turnovers Won / 90", "Fouls Committed / 90"]
                cat_vals = [round(t_xg / m_count, 2), round(t_sot / m_count, 1), round(t_ft_won / m_count, 1), round(t_fouls / m_count, 1)]

                ax.bar(cat_names, cat_vals, color=["#00d2ff", "#2194ff", "#5bb849", "#ffb800"], edgecolor="#ffffff", width=0.55)
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                ax.spines['bottom'].set_color('#888888')
                ax.spines['left'].set_color('#888888')
                ax.tick_params(colors='#ffffff', labelsize=10)
                ax.set_title(f"{selected_team.upper()} — Match Control & High-Press Profile", color="#ffffff", fontsize=15, weight="bold", pad=15)
                fig.text(0.82, 0.02, "@EffectiveMins", color="#888888", fontsize=10, style='italic')

                for idx, v in enumerate(cat_vals):
                    ax.annotate(str(v), (idx, v), textcoords="offset points", xytext=(0, 6), ha='center', color='#ffffff', weight='bold')

                st.pyplot(fig)

            with cg2:
                if badge_url:
                    st.image(badge_url, width=70)
                st.markdown("### Ready-to-Post Copy")
                comp_tag = "#UCL" if "Champions" in active_competition else "#PremierLeague #PL"
                post_ctrl = f"""📊 Match Control & Pressing: {selected_team} ({active_competition})

• Expected Goals (xG): {round(t_xg / m_count, 2)} per 90
• Shots on Target: {round(t_sot / m_count, 1)} per 90
• Final Third Poss Won (High Turnovers): {round(t_ft_won / m_count, 1)} per 90
• Tactical Fouls Committed: {round(t_fouls / m_count, 1)} per 90

Follow @EffectiveMins for full match efficiency analytics {comp_tag} #{selected_team.replace(' ', '')}"""
                st.text_area("Draft Control Post", value=post_ctrl, height=200)

    # ==========================================
    # TAB 2: CONTROL, XG & TERRITORY
    # ==========================================
    with tab2:
        st.subheader(f"🎯 {active_competition} Control, xG & High Pressing")
        st.caption("Profiling chance quality, territorial penetration, high-turnover pressing, and possession security.")

        adv_rows = []
        for team in unique_logged_teams:
            h_m = active_df[active_df["Home Team"] == team]
            a_m = active_df[active_df["Away Team"] == team]
            t_count = len(h_m) + len(a_m)
            if t_count == 0:
                continue

            # Parse numeric stats
            xg_tot = h_m["Home xG"].apply(to_float).sum() + a_m["Away xG"].apply(to_float).sum()
            xgot_tot = h_m["Home xGOT"].apply(to_float).sum() + a_m["Away xGOT"].apply(to_float).sum()
            sot_tot = h_m["Home Shots On Target"].apply(to_float).sum() + a_m["Away Shots On Target"].apply(to_float).sum()
            box_tot = h_m["Home Shots Inside Box"].apply(to_float).sum() + a_m["Away Shots Inside Box"].apply(to_float).sum()
            opp_pass_tot = h_m["Home Passes Opp Half"].apply(to_float).sum() + a_m["Away Passes Opp Half"].apply(to_float).sum()
            ft_pass_tot = h_m["Home Passes Final Third"].apply(to_float).sum() + a_m["Away Passes Final Third"].apply(to_float).sum()
            ft_won_tot = h_m["Home Final Third Won"].apply(to_float).sum() + a_m["Away Final Third Won"].apply(to_float).sum()
            pos_lost_tot = h_m["Home Possession Lost"].apply(to_float).sum() + a_m["Away Possession Lost"].apply(to_float).sum()
            fouls_tot = h_m["Home Fouls"].apply(to_float).sum() + a_m["Away Fouls"].apply(to_float).sum()

            adv_rows.append({
                "Badge": CLUB_BADGES.get(team, "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/default"),
                "Team": team,
                "Matches": t_count,
                "Avg xG / 90": round(xg_tot / t_count, 2),
                "Avg xGOT / 90": round(xgot_tot / t_count, 2),
                "Shots on Target / 90": round(sot_tot / t_count, 1),
                "Box Shots / 90": round(box_tot / t_count, 1),
                "Final Third Entries / 90": round(ft_pass_tot / t_count, 1),
                "Opp Half Passes / 90": round(opp_pass_tot / t_count, 1),
                "High Turnovers Won / 90": round(ft_won_tot / t_count, 1),
                "Possession Lost / 90": round(pos_lost_tot / t_count, 1),
                "Fouls Committed / 90": round(fouls_tot / t_count, 1),
            })

        df_adv = pd.DataFrame(adv_rows)

        sort_adv_by = st.selectbox(
            "Sort Performance Table By:",
            [
                ("Avg xG / 90", "Expected Goals (xG per 90 - Highest First)", False),
                ("High Turnovers Won / 90", "High Pressing / Turnovers Won (Highest First)", False),
                ("Final Third Entries / 90", "Territorial Penetration / Final Third Passes (Highest First)", False),
                ("Shots on Target / 90", "Shots on Target (Highest First)", False),
                ("Fouls Committed / 90", "Tactical Fouls (Highest First)", False)
            ],
            format_func=lambda x: x[1]
        )

        df_adv = df_adv.sort_values(by=sort_adv_by[0], ascending=sort_adv_by[2])

        adv_cols_show = [
            "Badge", "Team", "Matches", "Avg xG / 90", "Avg xGOT / 90",
            "Shots on Target / 90", "Box Shots / 90", "Final Third Entries / 90",
            "High Turnovers Won / 90", "Fouls Committed / 90"
        ]

        st.dataframe(
            df_adv[adv_cols_show],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Badge": st.column_config.ImageColumn("Badge", width="small")
            }
        )

    # ==========================================
    # TAB 3: FLOW & DISRUPTION
    # ==========================================
    with tab3:
        st.subheader(f"🌊 {active_competition} Rhythm & Whistle Disruptions")
        st.caption("Measuring game disruption, whistle frequency, and continuous play streaks.")

        df_flow = active_df.copy()
        df_flow["InPlay_Sec"] = df_flow["Actual In-Play"].apply(time_to_seconds)
        df_flow["Total_Sec"] = df_flow["Total Match Time"].apply(time_to_seconds)
        df_flow["Longest_Sec"] = df_flow["Longest In-Play"].apply(time_to_seconds)
        df_flow["Stops"] = df_flow["Game Stops"].astype(int)

        df_flow["Seconds Per Whistle"] = (df_flow["Total_Sec"] / df_flow["Stops"].replace(0, 1)).round(1)
        df_flow["Match"] = df_flow["Home Team"] + " vs " + df_flow["Away Team"]

        fl_c1, fl_c2, fl_c3, fl_c4 = st.columns(4)
        with fl_c1:
            st.metric("Avg Stops per Fixture", round(df_flow["Stops"].mean(), 1))
        with fl_c2:
            st.metric("Competition Pace", f"Whistle every {round(df_flow['Seconds Per Whistle'].mean(), 1)}s")
        with fl_c3:
            longest_run = df_flow.sort_values(by="Longest_Sec", ascending=False).iloc[0]
            st.metric("Longest Continuous Play", f"{longest_run['Longest In-Play']}", f"Round {longest_run['Gameweek']}")
        with fl_c4:
            most_stops = df_flow.sort_values(by="Stops", ascending=False).iloc[0]
            st.metric("Most Fragmented Match", f"{most_stops['Stops']} Stops", f"Round {most_stops['Gameweek']}")

        st.divider()

        st.markdown(f"##### 🏆 Club Stoppages Leaderboard ({active_competition})")
        st.caption("Which clubs generate and experience the most interrupted, whistle-heavy matches?")

        club_stop_rows = []
        for team in unique_logged_teams:
            t_matches = active_df[
                (active_df["Home Team"] == team) |
                (active_df["Away Team"] == team)
            ].copy()
            t_count = len(t_matches)
            if t_count == 0:
                continue

            stops_series = t_matches["Game Stops"].astype(int)
            total_stops = stops_series.sum()
            avg_stops = round(total_stops / t_count, 1)
            max_stops = stops_series.max()
            min_stops = stops_series.min()

            total_match_sec = t_matches["Total Match Time"].apply(time_to_seconds).sum()
            sec_per_whistle = round(total_match_sec / total_stops, 1) if total_stops > 0 else 0

            club_stop_rows.append({
                "Badge": CLUB_BADGES.get(team, "https://imagecache.365scores.com/image/upload/f_auto,w_48,h_48,c_limit,q_auto:eco,dpr_2/v5/competitors/default"),
                "Team": team,
                "Matches": t_count,
                "Cumulative Stops": total_stops,
                "Avg Stops / 90": avg_stops,
                "Max Single Match": max_stops,
                "Min Single Match": min_stops,
                "Whistle Frequency": f"Every {sec_per_whistle}s",
                "_sec_per_whistle": sec_per_whistle
            })

        df_club_stops = pd.DataFrame(club_stop_rows)

        sort_stops_by = st.selectbox(
            "Sort Stoppage Leaderboard By:",
            [
                ("Cumulative Stops", "Cumulative Stops (Highest First)", False),
                ("Avg Stops / 90", "Avg Stops / 90 (Highest First)", False),
                ("_sec_per_whistle", "Most Frequent Whistles (Lowest Seconds Between Whistles)", True),
                ("Max Single Match", "Highest Single-Match Whistle Peak", False)
            ],
            format_func=lambda x: x[1]
        )

        df_club_stops = df_club_stops.sort_values(by=sort_stops_by[0], ascending=sort_stops_by[2])

        show_stop_cols = [
            "Badge", "Team", "Matches", "Cumulative Stops", "Avg Stops / 90",
            "Max Single Match", "Min Single Match", "Whistle Frequency"
        ]

        st.dataframe(
            df_club_stops[show_stop_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Badge": st.column_config.ImageColumn("Badge", width="small")
            }
        )

        st.divider()

        sub1, sub2 = st.columns([1.4, 1])
        with sub1:
            st.markdown("##### 🚨 Individual Fixtures (Ranked by Whistle Stops)")
            fragmented_view = df_flow.sort_values(by="Stops", ascending=False)[[
                "Gameweek", "Match", "Stops", "Seconds Per Whistle", "Actual In-Play", "Longest In-Play"
            ]]
            st.dataframe(fragmented_view, use_container_width=True, hide_index=True)

        with sub2:
            st.markdown("##### 🏃 Unbroken Sequences (Longest Play Runs)")
            smooth_view = df_flow.sort_values(by="Longest_Sec", ascending=False)[[
                "Gameweek", "Match", "Longest In-Play", "Actual In-Play"
            ]]
            st.dataframe(smooth_view, use_container_width=True, hide_index=True)

    # ==========================================
    # TAB 4: ADDED TIME INTEGRITY
    # ==========================================
    with tab4:
        st.subheader(f"⏱️ {active_competition} Added Time Integrity")
        st.caption("Tracking how much extra time was announced, how long matches actually ran, and actual ball-in-play during stoppage.")

        df_at = active_df.copy()
        df_at["Ann_Sec"] = df_at["Announced Added"].apply(time_to_seconds)
        df_at["Act_Sec"] = df_at["Actual Added"].apply(time_to_seconds)
        df_at["Ply_Sec"] = df_at["Played Added"].apply(time_to_seconds)

        df_at["Overrun_Sec"] = df_at["Act_Sec"] - df_at["Ann_Sec"]
        df_at["Overrun"] = df_at["Overrun_Sec"].apply(lambda s: f"+{seconds_to_time(s)}" if s >= 0 else f"-{seconds_to_time(abs(s))}")
        df_at["Match"] = df_at["Home Team"] + " vs " + df_at["Away Team"]

        tot_ann = df_at["Ann_Sec"].sum()
        tot_act = df_at["Act_Sec"].sum()
        tot_ply = df_at["Ply_Sec"].sum()

        at_c1, at_c2, at_c3, at_c4 = st.columns(4)
        with at_c1:
            st.metric("Total Announced Added", seconds_to_time(tot_ann))
        with at_c2:
            st.metric("Total Actual Added", seconds_to_time(tot_act))
        with at_c3:
            net_over = tot_act - tot_ann
            st.metric("Net Added Time Overrun", f"+{seconds_to_time(net_over)}" if net_over >= 0 else f"-{seconds_to_time(abs(net_over))}")
        with at_c4:
            at_pct = round((tot_ply / tot_act * 100), 1) if tot_act > 0 else 0.0
            st.metric("Effective Stoppage Rate", f"{at_pct}%", "In-Play During Added")

        st.divider()

        st.markdown("##### 🔍 Matchday Added Time Performance")
        df_at_view = df_at[[
            "Gameweek", "Match", "Announced Added", "Actual Added", "Overrun", "Played Added", "Total Match Time"
        ]].sort_values(by="Gameweek", ascending=False)
        st.dataframe(df_at_view, use_container_width=True, hide_index=True)

    # ==========================================
    # TAB 5: VAR REVIEW IMPACT
    # ==========================================
    with tab5:
        st.subheader(f"📺 {active_competition} VAR Review Impact")
        st.caption("Tracking how video reviews affect stoppage time, flow, and total dead time per club.")

        var_rows = []
        for _, r in active_df.iterrows():
            var_s = time_to_seconds(r["VAR Checks"])
            tot_s = time_to_seconds(r["Total Match Time"])
            has_var = 1 if var_s > 0 else 0

            var_rows.append({
                "Team": r["Home Team"],
                "VAR_Sec": var_s,
                "Total_Sec": tot_s,
                "Has_VAR": has_var,
                "Max_VAR_Sec": var_s
            })
            var_rows.append({
                "Team": r["Away Team"],
                "VAR_Sec": var_s,
                "Total_Sec": tot_s,
                "Has_VAR": has_var,
                "Max_VAR_Sec": var_s
            })

        df_var_calc = pd.DataFrame(var_rows)

        total_league_var_sec = active_df["VAR Checks"].apply(time_to_seconds).sum()
        matches_with_var = (active_df["VAR Checks"].apply(time_to_seconds) > 0).sum()
        total_fixtures_count = len(active_df)
        pct_var_fixtures = round((matches_with_var / total_fixtures_count * 100), 1) if total_fixtures_count > 0 else 0.0

        longest_var_sec = active_df["VAR Checks"].apply(time_to_seconds).max()
        longest_var_match = active_df[active_df["VAR Checks"].apply(time_to_seconds) == longest_var_sec]
        longest_var_label = "None"
        if not longest_var_match.empty and longest_var_sec > 0:
            top_row = longest_var_match.iloc[0]
            longest_var_label = f"{top_row['VAR Checks']} ({top_row['Home Team'][:3].upper()} vs {top_row['Away Team'][:3].upper()})"

        v_c1, v_c2, v_c3, v_c4 = st.columns(4)
        with v_c1:
            st.metric("Total Season VAR Stoppage", seconds_to_time(total_league_var_sec))
        with v_c2:
            st.metric("Fixtures with VAR Checks", f"{matches_with_var} / {total_fixtures_count} ({pct_var_fixtures}%)")
        with v_c3:
            avg_review_len = round(total_league_var_sec / matches_with_var) if matches_with_var > 0 else 0
            st.metric("Average Review Delay", seconds_to_time(avg_review_len))
        with v_c4:
            st.metric("Longest Single Review", longest_var_label)

        st.divider()

        st.markdown("##### 📊 Club VAR Exposure")
        var_grouped = df_var_calc.groupby("Team").agg({
            "VAR_Sec": ["count", "sum", "mean", "max"],
            "Has_VAR": "sum"
        }).reset_index()

        var_grouped.columns = ["Team", "Matches", "Total_VAR_Sec", "Avg_VAR_Sec", "Max_VAR_Sec", "VAR_Matches"]
        var_grouped["Badge"] = var_grouped["Team"].map(CLUB_BADGES)
        var_grouped["Total VAR Delay"] = var_grouped["Total_VAR_Sec"].apply(seconds_to_time)
        var_grouped["Avg VAR Delay / 90"] = var_grouped["Avg_VAR_Sec"].apply(seconds_to_time)
        var_grouped["Longest Check"] = var_grouped["Max_VAR_Sec"].apply(seconds_to_time)
        var_grouped["VAR Match Rate %"] = ((var_grouped["VAR_Matches"] / var_grouped["Matches"].replace(0, 1)) * 100).round(1)

        sort_var = st.selectbox(
            "Sort VAR Table By:",
            [
                ("Total_VAR_Sec", "Total VAR Stoppage (Highest First)", False),
                ("Avg_VAR_Sec", "Average VAR Delay / 90 (Highest First)", False),
                ("Max_VAR_Sec", "Longest Check (Highest First)", False),
                ("VAR Match Rate %", "VAR Review Rate % (Highest First)", False)
            ],
            format_func=lambda x: x[1]
        )

        var_grouped = var_grouped.sort_values(by=sort_var[0], ascending=sort_var[2])

        var_cols_show = [
            "Badge", "Team", "Matches", "VAR_Matches", "VAR Match Rate %",
            "Total VAR Delay", "Avg VAR Delay / 90", "Longest Check"
        ]

        st.dataframe(
            var_grouped[var_cols_show],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Badge": st.column_config.ImageColumn("Badge", width="small")
            }
        )

        st.divider()

        st.markdown("##### ⏱️ Match Review Log (Ranked by Check Length)")
        match_var_log = active_df.copy()
        match_var_log["VAR_Sec"] = match_var_log["VAR Checks"].apply(time_to_seconds)
        match_var_log["Total_Sec"] = match_var_log["Total Match Time"].apply(time_to_seconds)
        match_var_log = match_var_log[match_var_log["VAR_Sec"] > 0].sort_values(by="VAR_Sec", ascending=False)

        if match_var_log.empty:
            st.info("No fixtures have recorded significant VAR reviews yet.")
        else:
            match_var_log["Match"] = match_var_log["Home Team"] + " vs " + match_var_log["Away Team"]
            match_var_log["VAR Share of Match %"] = ((match_var_log["VAR_Sec"] / match_var_log["Total_Sec"].replace(0, 1)) * 100).round(1)

            show_match_var = match_var_log[[
                "Gameweek", "Match", "VAR Checks", "Total Match Time", "Actual In-Play", "VAR Share of Match %"
            ]]
            st.dataframe(show_match_var, use_container_width=True, hide_index=True)

    # ==========================================
    # TAB 6: LIVE SPREADSHEET EDITOR
    # ==========================================
    with tab6:
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
