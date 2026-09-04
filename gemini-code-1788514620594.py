import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import json
import os
import io
import base64
import traceback
from PIL import Image
from streamlit_paste_button import paste_image_button

# Conditional imports for engines
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

st.set_page_config(page_title="EffectiveMins Tracker", layout="wide")

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

PROMPT_TEXT = """
Extract the match stoppage statistics from this 365scores graphic into this exact JSON structure:
{
    "actual_in_play": "MM:SS",
    "total_time": "MM:SS",
    "var_checks": "MM:SS",
    "game_stops": 0,
    "longest_in_play": "MM:SS",
    "announced_added": "MM:SS",
    "actual_added": "MM:SS",
    "played_added": "MM:SS",
    "home_goal_kicks": "MM:SS",
    "away_goal_kicks": "MM:SS",
    "home_free_kicks": "MM:SS",
    "away_free_kicks": "MM:SS",
    "home_throw_ins": "MM:SS",
    "away_throw_ins": "MM:SS",
    "home_corners": "MM:SS",
    "away_corners": "MM:SS",
    "home_other": "MM:SS",
    "away_other": "MM:SS",
    "home_total_wasted": "MM:SS",
    "away_total_wasted": "MM:SS"
}
Rules:
- In 'Time Wasted On', left column is Home side, right column is Away side.
- 'game_stops' must be an integer.
- Format all durations as 'MM:SS' strings.
- Return pure JSON only. Do not include markdown ticks, intros, or explanations.
"""

# --- HELPER TIME CONVERSIONS ---
def clean_val(val) -> str:
    """Sanitises unicode characters like dashes into standard ascii equivalents."""
    if val is None:
        return "--"
    return str(val).replace("–", "-").replace("—", "-").strip()

def time_to_seconds(val: str) -> int:
    """Converts MM:SS or M:SS to integer seconds safely."""
    s_val = clean_val(val)
    if not s_val or ":" not in s_val or s_val.startswith("-"):
        return 0
    try:
        parts = s_val.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return 0

def seconds_to_time(seconds: int) -> str:
    """Converts seconds back to MM:SS."""
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
    try:
        st.session_state.match_log = pd.read_csv(DATA_FILE, encoding="utf-8")
    except Exception:
        st.session_state.match_log = pd.read_csv(DATA_FILE, encoding="latin1")
else:
    st.session_state.match_log = pd.DataFrame(columns=MATCH_COLUMNS)

st.title("⏱️ EffectiveMins: Premier League Stoppage Tracker")

# --- SIDEBAR: ENGINE & KEY CONFIG ---
with st.sidebar:
    st.header("⚙️ Configuration")
    ai_engine = st.radio("Choose AI Engine:", ["Google Gemini (1,500/day free)", "Groq Llama Vision"], index=0)

    if ai_engine == "Google Gemini (1,500/day free)":
        default_gemini = st.secrets.get("GEMINI_API_KEY", "")
        api_key = st.text_input("Gemini API Key", value=default_gemini, type="password")
        st.caption("Using model: **`gemini-2.0-flash`** (1,500 free queries/day)")
    else:
        default_groq = st.secrets.get("GROQ_API_KEY", "")
        api_key = st.text_input("Groq API Key (Free)", value=default_groq, type="password")
        st.caption("Obtain key at [console.groq.com](https://console.groq.com/)")

    st.divider()
    st.header("🛠️ Database Admin")
    st.write(f"Logged Fixtures: `{len(st.session_state.match_log)}`")
    
    with st.expander("⚠️ Danger Zone"):
        if st.button("🗑️ Reset Entire Database", type="secondary"):
            st.session_state.match_log = pd.DataFrame(columns=MATCH_COLUMNS)
            if os.path.exists(DATA_FILE):
                os.remove(DATA_FILE)
            st.warning("All records wiped.")
            st.rerun()

    st.divider()
    st.markdown("**@EffectiveMins** Stoppage Analytics")

# --- MATCH INGESTION SECTION ---
with st.expander("📸 Scan New Match Breakdown", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        gw = st.number_input("Gameweek", min_value=1, max_value=38, value=1, step=1)
    with col2:
        home_team = st.selectbox("Home Team", PL_TEAMS, index=0)
    with col3:
        away_team = st.selectbox("Away Team", PL_TEAMS, index=1)

    st.markdown("### Image Input")
    upload_method = st.radio("Choose Input Mode:", ["📋 Paste Screenshot", "📁 Upload Image File"], horizontal=True)

    active_image_bytes = None

    if upload_method == "📋 Paste Screenshot":
        paste_result = paste_image_button(
            label="📋 Click to Paste from Clipboard",
            text_color="#ffffff",
            background_color="#007acc",
            hover_background_color="#005999",
            errors="raise"
        )
        if paste_result.image_data is not None:
            buf = io.BytesIO()
            paste_result.image_data.save(buf, format="PNG")
            active_image_bytes = buf.getvalue()
            st.image(paste_result.image_data, caption="Clipboard Graphic Loaded", width=340)
    else:
        uploaded_img = st.file_uploader("Upload 365Scores Graphic", type=["png", "jpg", "jpeg", "webp"])
        if uploaded_img is not None:
            active_image_bytes = uploaded_img.getvalue()
            st.image(uploaded_img, caption="Uploaded Graphic Loaded", width=340)

    st.write("")
    
    btn_c1, btn_c2 = st.columns([2, 1])
    with btn_c1:
        extract_pressed = st.button("🚀 Extract & Save Match Record", type="primary", use_container_width=True)
    with btn_c2:
        undo_pressed = st.button("↩️ Undo Last Entry", type="secondary", use_container_width=True)

    if undo_pressed:
        if not st.session_state.match_log.empty:
            removed_row = st.session_state.match_log.iloc[-1]
            st.session_state.match_log = st.session_state.match_log.iloc[:-1].reset_index(drop=True)
            st.session_state.match_log.to_csv(DATA_FILE, index=False, encoding="utf-8")
            st.warning(f"Undid: **{removed_row['Home Team']} vs {removed_row['Away Team']}** (Gameweek {removed_row['Gameweek']})")
            st.rerun()
        else:
            st.info("No entries to undo.")

    if extract_pressed:
        clean_key = api_key.strip() if api_key else ""
        if not clean_key:
            st.error("Please provide an API Key in the left sidebar.")
        elif home_team == away_team:
            st.error("Home and Away teams must be different.")
        elif active_image_bytes is None:
            st.error("Please paste or upload a 365Scores graphic first.")
        else:
            with st.spinner("Extracting match metrics..."):
                try:
                    # Normalise and compress image to clean JPEG
                    pil_img = Image.open(io.BytesIO(active_image_bytes))
                    if pil_img.mode in ("RGBA", "P"):
                        pil_img = pil_img.convert("RGB")
                    pil_img.thumbnail((1200, 1200))
                    
                    img_buf = io.BytesIO()
                    pil_img.save(img_buf, format="JPEG", quality=85)
                    jpeg_bytes = img_buf.getvalue()

                    raw_json_text = ""

                    if ai_engine == "Google Gemini (1,500/day free)":
                        client = genai.Client(api_key=clean_key)
                        response = client.models.generate_content(
                            model="gemini-2.0-flash",
                            contents=[
                                types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"),
                                PROMPT_TEXT
                            ],
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json"
                            )
                        )
                        raw_json_text = response.text
                    else:
                        client = Groq(api_key=clean_key)
                        b64_str = base64.b64encode(jpeg_bytes).decode("ascii")
                        completion = client.chat.completions.create(
                            model="llama-3.2-11b-vision-preview",
                            messages=[{
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": PROMPT_TEXT},
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_str}"}}
                                ]
                            }],
                            temperature=0.1,
                            response_format={"type": "json_object"}
                        )
                        raw_json_text = completion.choices[0].message.content

                    stats = json.loads(raw_json_text)

                    new_entry = {
                        "Gameweek": int(gw),
                        "Home Team": str(home_team),
                        "Away Team": str(away_team),
                        "Actual In-Play": clean_val(stats.get("actual_in_play", "00:00")),
                        "Total Match Time": clean_val(stats.get("total_time", "90:00")),
                        "VAR Checks": clean_val(stats.get("var_checks", "00:00")),
                        "Game Stops": int(stats.get("game_stops", 0)),
                        "Longest In-Play": clean_val(stats.get("longest_in_play", "00:00")),
                        "Announced Added": clean_val(stats.get("announced_added", "00:00")),
                        "Actual Added": clean_val(stats.get("actual_added", "00:00")),
                        "Played Added": clean_val(stats.get("played_added", "00:00")),
                        "Home Goal Kicks": clean_val(stats.get("home_goal_kicks", "00:00")),
                        "Away Goal Kicks": clean_val(stats.get("away_goal_kicks", "00:00")),
                        "Home Free Kicks": clean_val(stats.get("home_free_kicks", "00:00")),
                        "Away Free Kicks": clean_val(stats.get("away_free_kicks", "00:00")),
                        "Home Throw Ins": clean_val(stats.get("home_throw_ins", "00:00")),
                        "Away Throw Ins": clean_val(stats.get("away_throw_ins", "00:00")),
                        "Home Corners": clean_val(stats.get("home_corners", "00:00")),
                        "Away Corners": clean_val(stats.get("away_corners", "00:00")),
                        "Home Other": clean_val(stats.get("home_other", "00:00")),
                        "Away Other": clean_val(stats.get("away_other", "00:00")),
                        "Home Total Wasted": clean_val(stats.get("home_total_wasted", "00:00")),
                        "Away Total Wasted": clean_val(stats.get("away_total_wasted", "00:00"))
                    }

                    st.session_state.match_log = pd.concat(
                        [st.session_state.match_log, pd.DataFrame([new_entry])],
                        ignore_index=True
                    )
                    st.session_state.match_log.to_csv(DATA_FILE, index=False, encoding="utf-8")
                    st.success(f"Recorded {home_team} vs {away_team} (Gameweek {gw}) successfully!")
                    st.rerun()

                except Exception as err:
                    st.error(f"Error parsing graphic: {str(err)}")
                    with st.expander("Show Diagnostic Details"):
                        st.code(traceback.format_exc())

st.divider()

# --- STANDINGS & VISUAL ANALYTICS ---
if st.session_state.match_log.empty:
    st.info("No fixture data recorded yet. Paste or upload your first 365Scores graphic above.")
else:
    tab1, tab2 = st.tabs(["🏆 Team Standings (Averages)", "📝 Editable Match Log & Export"])

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
        st.markdown("💡 **Tip:** Double-click any cell to edit numbers directly. Select rows using the checkboxes on the left and press `Delete` on your keyboard to remove specific fixtures.")
        
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
