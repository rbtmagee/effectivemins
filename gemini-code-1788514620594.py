import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="EffectiveMins Dashboard", layout="wide")

# Styling to match the dark analytical aesthetic of 365scores
st.markdown("""
    <style>
    .main { background-color: #0b1118; }
    h1, h2, h3 { color: #00d2ff; }
    </style>
""", unsafe_allow_html=True)

st.title("⏱️ EffectiveMins: Premier League Stoppage Tracker")

# Initialise demo session dataset if not present
if "match_db" not in st.session_state:
    st.session_state.match_db = pd.DataFrame([
        {
            "Team": "Arsenal", "Matches": 3, 
            "Avg In-Play %": 58.2, "Avg In-Play (mins)": "55:10",
            "Wasted: Goal Kicks": "03:12", "Wasted: Free Kicks": "08:45",
            "Wasted: Throw-Ins": "04:15", "Wasted: Corners": "02:10",
            "Avg Total Wasted": "21:32", "Raw_Wasted_Sec": 1292
        },
        {
            "Team": "Brighton", "Matches": 3, 
            "Avg In-Play %": 62.4, "Avg In-Play (mins)": "60:40",
            "Wasted: Goal Kicks": "01:45", "Wasted: Free Kicks": "05:20",
            "Wasted: Throw-Ins": "02:50", "Wasted: Corners": "01:30",
            "Avg Total Wasted": "14:15", "Raw_Wasted_Sec": 855
        },
        {
            "Team": "Newcastle", "Matches": 3, 
            "Avg In-Play %": 52.1, "Avg In-Play (mins)": "50:18",
            "Wasted: Goal Kicks": "05:40", "Wasted: Free Kicks": "10:15",
            "Wasted: Throw-Ins": "06:05", "Wasted: Corners": "03:10",
            "Avg Total Wasted": "27:40", "Raw_Wasted_Sec": 1660
        }
    ])

# Sidebar Controls
with st.sidebar:
    st.header("Match Ingestion")
    upload_type = st.radio("Ingestion Method", ["Manual Entry", "Upload CSV", "Screenshot"])
    st.divider()
    st.caption("Maintained for @EffectiveMins")

# Interactive League Table
st.subheader("Premier League Time-Wasting Standings")

col1, col2 = st.columns([3, 1])
with col1:
    sort_metric = st.selectbox(
        "Sort Table By:", 
        ["Raw_Wasted_Sec", "Avg In-Play %"],
        format_func=lambda x: "Total Time Wasted (Highest First)" if x == "Raw_Wasted_Sec" else "Effective Playing %"
    )

display_df = st.session_state.match_db.sort_values(
    by=sort_metric, 
    ascending=(sort_metric != "Raw_Wasted_Sec")
).drop(columns=["Raw_Wasted_Sec"])

st.dataframe(
    display_df, 
    use_container_width=True,
    hide_index=True
)

st.divider()

# Twitter Graphic Generator Section
st.subheader("Generate Graphic for @EffectiveMins")
c1, c2 = st.columns([1, 1])

with c1:
    selected_team = st.selectbox("Select Team for Matchday Breakdown", display_df["Team"])
    team_data = display_df[display_df["Team"] == selected_team].iloc[0]
    
    # Generate Matplotlib Infographic formatted for X (16:9 landscape)
    fig, ax = plt.subplots(figsize=(10, 5.625), facecolor="#0e1621")
    ax.set_facecolor("#0e1621")
    
    categories = ["Goal Kicks", "Free Kicks", "Throw-Ins", "Corners"]
    # Mock relative proportions for illustration
    times = [float(team_data[f"Wasted: {cat}"].split(":")[0]) for cat in categories]
    
    bars = ax.barh(categories, times, color="#00d2ff", edgecolor="#ffffff", height=0.55)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('#888888')
    ax.spines['left'].set_color('#888888')
    ax.tick_params(colors='#ffffff', labelsize=11)
    ax.set_xlabel("Average Minutes Spent per Match", color="#ffffff", fontsize=12)
    ax.set_title(f"{selected_team.upper()} — Where Did The Minutes Go?", color="#ffffff", fontsize=16, weight="bold", pad=15)
    
    # Signature watermark for Twitter
    fig.text(0.85, 0.03, "@EffectiveMins", color="#777777", fontsize=10, style='italic')

    st.pyplot(fig)

with c2:
    st.write("### Ready-to-Post Copy")
    tweet_text = f"""📊 Average Dead-Ball Breakdown: {selected_team}

⏱️ Avg Effective In-Play: {team_data['Avg In-Play %']}% ({team_data['Avg In-Play (mins)']})
🚫 Time Lost to Delays: {team_data['Avg Total Wasted']} per 90

Highest stoppage factor: Free Kicks ({team_data['Wasted: Free Kicks']})

#PL #PremierLeague #EffectiveMins"""
    st.text_area("Draft Tweet", value=tweet_text, height=180)