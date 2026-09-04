import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import json
import os
import io
import re
import base64
import traceback
import requests
from PIL import Image
from streamlit_paste_button import paste_image_button

# Dynamic AI provider imports
try:
    from google import genai
    from google.genai import types
    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

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
- In 'Time Wasted On', left column is Home team, right column is Away team.
- 'game_stops' must be an integer.
- Format all durations as 'MM:SS' strings.
- Return valid JSON only without markdown ticks or commentary.
"""

# --- UTILITY & SANITISATION FUNCTIONS ---
def sanitize_text(val) -> str:
    if val is None:
        return "--"
    s = str(val).strip().replace("–", "-").replace("—", "-")
    cleaned = re.sub(r"[^\x20-\x7E]", "", s)
    return cleaned if cleaned else "--"

def time_to_seconds(val: str) -> int:
    s_val = sanitize_text(val)
    if not s_val or ":" not in s_val or s_val.startswith("-"):
        return 0
    try:
        parts = s_val.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return 0

def seconds_to_time(seconds: int) -> str:
    m, s = divmod(int(round(seconds)), 60)
    return f"{m:02d}:{s:02d}"

@st.cache_data(ttl=1800)
def fetch_live_openrouter_free_models():
    """Dynamically fetches models currently online and free on OpenRouter."""
    try:
        res = requests.get("https://openrouter.ai/api/v1/models", timeout=8)
        if res.status_code == 200:
            data = res.json().get("data", [])
            # Filter for free models supporting multimodal/vision
            free_models = [
                m["id"] for m in data 
                if ":free" in m.get("id", "") and any(term in m.get("id", "").lower() for term in ["vl", "vision", "flash", "gemini"])
            ]
            if free_models:
                return free_models
    except Exception:
        pass
    # Reliable fallback list if OpenRouter API discovery is slow
    return [
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.2-11b-vision-instruct:free",
        "google/gemini-2.0-pro-exp-02-05:free"
    ]

# --- LOAD DATABASE ---
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

# --- SIDEBAR CONFIGURATION ---
with st.sidebar:
    st.header("⚙️ Scanner Configuration")
    provider = st.selectbox(
        "AI Provider",
        ["OpenRouter (Free Vision)", "Google AI Studio"]
    )

    if provider == "OpenRouter (Free Vision)":
        api_key = st.text_input("OpenRouter Key", value=st.secrets.get("OPENROUTER_API_KEY", ""), type="password")
        st.caption("Obtain key at [openrouter.ai/keys](https://openrouter.ai/keys)")
        
        live_free_models = fetch_live_openrouter_free_models()
        selected_model = st.selectbox("Active Free Vision Models", live_free_models)
        st.caption("Only models currently online appear above.")
        
    else:
        api_key = st.text_input("Google API Key", value=st.secrets.get("GEMINI_API_KEY", ""), type="password")
        selected_model = st.text_input("Model ID", value="gemini-3.6-flash")
        if st.button("Check Active Google Models"):
            if api_key and HAS_GOOGLE:
                try:
                    c = genai.Client(api_key=api_key.strip())
                    g_models = [m.name.replace("models/", "") for m in c.models.list() if "generateContent" in m.supported_actions]
                    st.write("Active models for your key:")
                    st.code("\n".join(g_models[:8]))
                except Exception as e:
                    st.error(str(e))

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
    st.markdown("**@EffectiveMins** Analytics Engine")

# --- FIXTURE INGESTION SECTION ---
with st.expander("➕ Log New Fixture", expanded=True):
    gw_col, h_col, a_col = st.columns(3)
    with gw_col:
        gw = st.number_input("Gameweek", min_value=1, max_value=38, value=1, step=1)
    with h_col:
        home_team = st.selectbox("Home Team", PL_TEAMS, index=0)
    with a_col:
        away_team = st.selectbox("Away Team", PL_TEAMS, index=1)

    ingest_tab1, ingest_tab2 = st.tabs(["⚡ AI Graphic Scanner", "✍️ 30-Second Manual Fallback"])

    # TAB 1: AI SCANNER
    with ingest_tab1:
        st.markdown("### Image Input")
        upload_method = st.radio("Input Mode:", ["📋 Paste Screenshot", "📁 Upload Image File"], horizontal=True)

        active_image_bytes = None
        if upload_method == "📋 Paste Screenshot":
            paste_result = paste_image_button(
                label="📋 Click to Paste Screenshot",
                text_color="#ffffff",
                background_color="#007acc",
                hover_background_color="#005999",
                errors="raise"
            )
            if paste_result.image_data is not None:
                buf = io.BytesIO()
                paste_result.image_data.save(buf, format="PNG")
                active_image_bytes = buf.getvalue()
                st.image(paste_result.image_data, caption="Screenshot Loaded", width=320)
        else:
            uploaded_img = st.file_uploader("Upload 365Scores Graphic", type=["png", "jpg", "jpeg", "webp"])
            if uploaded_img is not None:
                active_image_bytes = uploaded_img.getvalue()
                st.image(uploaded_img, caption="Graphic Loaded", width=320)

        st.write("")
        btn1, btn2 = st.columns([2, 1])
        with btn1:
            extract_pressed = st.button("🚀 Extract & Save Match Record", type="primary", use_container_width=True)
        with btn2:
            undo_pressed = st.button("↩️ Undo Last Entry", type="secondary", use_container_width=True)

        if undo_pressed:
            if not st.session_state.match_log.empty:
                removed_row = st.session_state.match_log.iloc[-1]
                st.session_state.match_log = st.session_state.match_log.iloc[:-1].reset_index(drop=True)
                st.session_state.match_log.to_csv(DATA_FILE, index=False, encoding="utf-8")
                st.warning(f"Undid: {removed_row['Home Team']} vs {removed_row['Away Team']}")
                st.rerun()

        if extract_pressed:
            clean_key = api_key.strip() if api_key else ""
            if not clean_key:
                st.error("Please enter your API key in the left sidebar.")
            elif home_team == away_team:
                st.error("Home and Away teams cannot be identical.")
            elif active_image_bytes is None:
                st.error("Please paste or upload a 365Scores graphic first.")
            else:
                with st.spinner(f"Extracting with {selected_model}..."):
                    try:
                        pil_img = Image.open(io.BytesIO(active_image_bytes))
                        if pil_img.mode in ("RGBA", "P"):
                            pil_img = pil_img.convert("RGB")
                        pil_img.thumbnail((1000, 1000))
                        img_buf = io.BytesIO()
                        pil_img.save(img_buf, format="JPEG", quality=80)
                        jpeg_bytes = img_buf.getvalue()

                        raw_json = ""

                        if provider == "Google AI Studio":
                            c = genai.Client(api_key=clean_key)
                            resp = c.models.generate_content(
                                model=selected_model.strip(),
                                contents=[
                                    types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"),
                                    PROMPT_TEXT
                                ],
                                config=types.GenerateContentConfig(response_mime_type="application/json")
                            )
                            raw_json = resp.text
                        else:
                            client_or = OpenAI(
                                api_key=clean_key,
                                base_url="https://openrouter.ai/api/v1",
                                default_headers={
                                    "HTTP-Referer": "https://effectivemins.streamlit.app",
                                    "X-Title": "EffectiveMins"
                                }
                            )
                            b64 = base64.b64encode(jpeg_bytes).decode("ascii")

                            completion = client_or.chat.completions.create(
                                model=selected_model.strip(),
                                messages=[{
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": PROMPT_TEXT},
                                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                                    ]
                                }],
                                response_format={"type": "json_object"}
                            )
                            raw_json = completion.choices[0].message.content

                        stats = json.loads(raw_json)

                        new_entry = {
                            "Gameweek": int(gw),
                            "Home Team": sanitize_text(home_team),
                            "Away Team": sanitize_text(away_team),
                            "Actual In-Play": sanitize_text(stats.get("actual_in_play", "00:00")),
                            "Total Match Time": sanitize_text(stats.get("total_time", "90:00")),
                            "VAR Checks": sanitize_text(stats.get("var_checks", "00:00")),
                            "Game Stops": int(stats.get("game_stops", 0)),
                            "Longest In-Play": sanitize_text(stats.get("longest_in_play", "00:00")),
                            "Announced Added": sanitize_text(stats.get("announced_added", "00:00")),
                            "Actual Added": sanitize_text(stats.get("actual_added", "00:00")),
                            "Played Added": sanitize_text(stats.get("played_added", "00:00")),
                            "Home Goal Kicks": sanitize_text(stats.get("home_goal_kicks", "00:00")),
                            "Away Goal Kicks": sanitize_text(stats.get("away_goal_kicks", "00:00")),
                            "Home Free Kicks": sanitize_text(stats.get("home_free_kicks", "00:00")),
                            "Away Free Kicks": sanitize_text(stats.get("away_free_kicks", "00:00")),
                            "Home Throw Ins": sanitize_text(stats.get("home_throw_ins", "00:00")),
                            "Away Throw Ins": sanitize_text(stats.get("away_throw_ins", "00:00")),
                            "Home Corners": sanitize_text(stats.get("home_corners", "00:00")),
                            "Away Corners": sanitize_text(stats.get("away_corners", "00:00")),
                            "Home Other": sanitize_text(stats.get("home_other", "00:00")),
                            "Away Other": sanitize_text(stats.get("away_other", "00:00")),
                            "Home Total Wasted": sanitize_text(stats.get("home_total_wasted", "00:00")),
                            "Away Total Wasted": sanitize_text(stats.get("away_total_wasted", "00:00"))
                        }

                        st.session_state.match_log = pd.concat(
                            [st.session_state.match_log, pd.DataFrame([new_entry])],
                            ignore_index=True
                        )
                        st.session_state.match_log.to_csv(DATA_FILE, index=False, encoding="utf-8")
                        st.success(f"Recorded {home_team} vs {away_team}!")
                        st.rerun()

                    except Exception as err:
                        st.error(f"Extraction error: {str(err)}")
                        with st.expander("Diagnostic Traceback"):
                            st.code(traceback.format_exc())

    # TAB 2: MANUAL ENTRY FORM
    with ingest_tab2:
        with st.form("complete_manual_form"):
            st.markdown("##### Match In-Play & Stoppages")
            f1, f2, f3, f4, f5 = st.columns(5)
            with f1:
                man_inplay = st.text_input("Actual In-Play", placeholder="57:29")
            with f2:
                man_total = st.text_input("Total Match Time", placeholder="99:01")
            with f3:
                man_var = st.text_input("VAR Checks", placeholder="02:30")
            with f4:
                man_stops = st.number_input("Game Stops", min_value=0, step=1, value=0)
            with f5:
                man_longest = st.text_input("Longest In-Play", placeholder="03:50")

            st.markdown("##### Added Time Breakdown")
            at1, at2, at3 = st.columns(3)
            with at1:
                man_ann = st.text_input("Announced Added", placeholder="08:00")
            with at2:
                man_act_add = st.text_input("Actual Added", placeholder="09:01")
            with at3:
                man_ply_add = st.text_input("Played Added", placeholder="06:33")

            st.markdown("##### Dead-Ball Time Wasted (Home vs Away)")
            tw1, tw2, tw3, tw4, tw5, tw6 = st.columns(6)
            with tw1:
                st.caption("Goal Kicks")
                man_hgk = st.text_input("Home GK", placeholder="01:13")
                man_agk = st.text_input("Away GK", placeholder="05:45")
            with tw2:
                st.caption("Free Kicks")
                man_hfk = st.text_input("Home FK", placeholder="04:06")
                man_afk = st.text_input("Away FK", placeholder="10:32")
            with tw3:
                st.caption("Throw Ins")
                man_hti = st.text_input("Home TI", placeholder="02:49")
                man_ati = st.text_input("Away TI", placeholder="06:06")
            with tw4:
                st.caption("Corners")
                man_hco = st.text_input("Home Cor", placeholder="01:24")
                man_aco = st.text_input("Away Cor", placeholder="02:50")
            with tw5:
                st.caption("Other")
                man_hot = st.text_input("Home Oth", placeholder="02:33")
                man_aot = st.text_input("Away Oth", placeholder="03:30")
            with tw6:
                st.caption("Total Wasted")
                man_htot = st.text_input("Home Tot", placeholder="12:05")
                man_atot = st.text_input("Away Tot", placeholder="28:43")

            if st.form_submit_button("Save Match Record Manually", type="primary"):
                manual_row = {
                    "Gameweek": int(gw),
                    "Home Team": sanitize_text(home_team),
                    "Away Team": sanitize_text(away_team),
                    "Actual In-Play": sanitize_text(man_inplay or "00:00"),
                    "Total Match Time": sanitize_text(man_total or "90:00"),
                    "VAR Checks": sanitize_text(man_var or "00:00"),
                    "Game Stops": int(man_stops),
                    "Longest In-Play": sanitize_text(man_longest or "00:00"),
                    "Announced Added": sanitize_text(man_ann or "00:00"),
                    "Actual Added": sanitize_text(man_act_add or "00:00"),
                    "Played Added": sanitize_text(man_ply_add or "00:00"),
                    "Home Goal Kicks": sanitize_text(man_hgk or "00:00"),
                    "Away Goal Kicks": sanitize_text(man_agk or "00:00"),
                    "Home Free Kicks": sanitize_text(man_hfk or "00:00"),
                    "Away Free Kicks": sanitize_text(man_afk or "00:00"),
                    "Home Throw Ins": sanitize_text(man_hti or "00:00"),
                    "Away Throw Ins": sanitize_text(man_ati or "00:00"),
                    "Home Corners": sanitize_text(man_hco or "00:00"),
                    "Away Corners": sanitize_text(man_aco or "00:00"),
                    "Home Other": sanitize_text(man_hot or "00:00"),
                    "Away Other": sanitize_text(man_aot or "00:00"),
                    "Home Total Wasted": sanitize_text(man_htot or "00:00"),
                    "Away Total Wasted": sanitize_text(man_atot or "00:00")
                }
                st.session_state.match_log = pd.concat([st.session_state.match_log, pd.DataFrame([manual_row])], ignore_index=True)
                st.session_state.match_log.to_csv(DATA_FILE, index=False, encoding="utf-8")
                st.success(f"Recorded {home_team} vs {away_team} manually!")
                st.rerun()

st.divider()

# --- STANDINGS TABLE & TWITTER GRAPHIC ---
if st.session_state.match_log.empty:
    st.info("No fixtures recorded yet. Add a match above to populate the league table.")
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

        # TWITTER GRAPHIC
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

    with tab2:
        st.markdown("Double-click any cell to edit numbers directly. Select rows using the checkboxes on the left and press Delete on your keyboard to remove fixtures.")
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
        st.download_button("📥 Download Full CSV Database", data=csv_export, file_name="effective_mins_database.csv", mime="text/csv")
