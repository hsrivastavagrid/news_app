import os
import base64
import time
import datetime
from pathlib import Path
import streamlit as st
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

from app.config import (
    DB_PATH,
    DOMAIN_TAGS,
    TAG_METADATA,
)
from app.database import db
from app.services.news_fetcher import fetch_and_process_news

# Page Configuration
st.set_page_config(
    page_title="NewsPulse - Real-Time News Sentiment Analysis",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=60000, limit=None, key="hourly_news_pulse_refresher")
except ImportError:
    st.markdown('<meta http-equiv="refresh" content="60">', unsafe_allow_html=True)

# Load background image to base64
def get_base64_image(image_path: str) -> str:
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return ""

img_path = str(Path(__file__).resolve().parent / "image.png")
if not os.path.exists(img_path):
    img_path = str(Path(__file__).resolve().parent.parent / "image.png")

img_base64 = get_base64_image(img_path)

# Custom CSS: Force Times New Roman font, remove default padding, set image.png background
custom_css = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Times+New+Roman&display=swap');

html, body, [class*="css"], [class*="st-"], div, span, p, h1, h2, h3, h4, h5, h6, button, input, select, textarea, label {{
    font-family: 'Times New Roman', Times, serif !important;
}}

.stApp {{
    background: linear-gradient(rgba(15, 12, 41, 0.82), rgba(26, 22, 58, 0.88), rgba(36, 36, 62, 0.92)),
                url("data:image/png;base64,{img_base64}");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
    color: #F8FAFC;
}}

/* Custom Glassmorphism Box */
.glass-box {{
    background: rgba(255, 255, 255, 0.05);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
}}

/* Hero Section */
.hero-box {{
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 14px;
    padding: 24px;
    margin-bottom: 24px;
}}

.hero-title {{
    font-size: 36px;
    font-weight: bold;
    letter-spacing: -0.5px;
    margin-bottom: 4px;
}}

.hero-subtitle {{
    font-size: 16px;
    color: #94A3B8;
}}

/* Clock Box on Top Right */
.clock-box {{
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 10px;
    padding: 10px 16px;
    text-align: right;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
}}

.clock-label {{
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
    color: #818CF8;
    text-transform: uppercase;
}}

.clock-time {{
    font-size: 18px;
    font-weight: bold;
    color: #F8FAFC;
    margin-top: 2px;
}}

/* Mode Colors */
.mode-good {{ color: #10B981; }}
.mode-bad {{ color: #EF4444; }}
.mode-ugly {{ color: #7C3AED; }}
.mode-neutral {{ color: #9CA3AF; }}

/* Custom Button */
div.stButton > button {{
    font-family: 'Times New Roman', Times, serif !important;
    background: linear-gradient(135deg, #6366F1, #4F46E5);
    color: #FFFFFF !important;
    border: none;
    border-radius: 8px;
    padding: 8px 18px;
    font-size: 14px;
    font-weight: bold;
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4);
}}

div.stButton > button:hover {{
    background: linear-gradient(135deg, #4F46E5, #4338CA);
    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6);
}}

/* Card Container */
.metric-card {{
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 16px;
    text-align: center;
}}

.metric-card-title {{
    font-size: 13px;
    font-weight: bold;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 8px;
}}

.metric-card-value {{
    font-size: 32px;
    font-weight: bold;
}}

.metric-card-pct {{
    font-size: 14px;
    color: #94A3B8;
}}

/* Article Card */
.article-item {{
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 12px;
}}

.article-title-link {{
    font-size: 18px;
    font-weight: bold;
    color: #F8FAFC;
    text-decoration: none;
}}

.article-title-link:hover {{
    color: #818CF8;
    text-decoration: underline;
}}

.article-meta-text {{
    font-size: 13px;
    color: #94A3B8;
    margin-top: 4px;
    margin-bottom: 8px;
}}

.badge-tag {{
    display: inline-block;
    background: rgba(255, 255, 255, 0.08);
    color: #CBD5E1;
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 4px;
    margin-right: 6px;
}}

.alert-banner {{
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(124, 58, 237, 0.25));
    border: 1px solid rgba(239, 68, 68, 0.5);
    border-radius: 10px;
    padding: 16px 20px;
    color: #FCA5A5;
    font-size: 15px;
    margin-bottom: 20px;
}}
</style>
"""

st.markdown(custom_css, unsafe_allow_html=True)

# Ensure Database initialized
db.init_db()

# Session State Initialization for Hourly Fetching
now_ts = time.time()
if "last_fetch_time" not in st.session_state:
    # Trigger initial hourly fetch on startup
    fetch_and_process_news()
    st.session_state["last_fetch_time"] = now_ts
    st.session_state["last_fetch_formatted"] = datetime.datetime.now().strftime("%H:%M:%S")

# Check if 1 hour (3600 seconds) has passed since last fetch to auto-fetch hourly news
if (now_ts - st.session_state.get("last_fetch_time", 0)) >= 3600:
    fetch_and_process_news()
    st.session_state["last_fetch_time"] = now_ts
    st.session_state["last_fetch_formatted"] = datetime.datetime.now().strftime("%H:%M:%S")

# Calculate current time in GMT + 5:30 (Asia/Kolkata timezone)
ist_offset = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
ist_now = datetime.datetime.now(ist_offset)
ist_time_str = ist_now.strftime("%d %b %Y, %I:%M:%S %p")

import streamlit.components.v1 as components

# Header Bar
col_h1, col_h2 = st.columns([2.5, 1.5])

with col_h1:
    st.markdown('<div class="hero-title">NewsPulse</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">Hourly News Sentiment Intelligence</div>', unsafe_allow_html=True)

with col_h2:
    # Continuously Ticking Live Clock Component (GMT +5:30)
    clock_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Times+New+Roman&display=swap');
            body {{
                margin: 0;
                padding: 0;
                background: transparent;
                font-family: 'Times New Roman', Times, serif;
            }}
            .clock-box {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 10px;
                padding: 8px 14px;
                text-align: right;
                color: #F8FAFC;
                box-sizing: border-box;
            }}
            .clock-label {{
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1px;
                color: #818CF8;
                text-transform: uppercase;
            }}
            .clock-time {{
                font-size: 17px;
                font-weight: bold;
                color: #F8FAFC;
                margin-top: 2px;
            }}
            .clock-status {{
                font-size: 11px;
                color: #94A3B8;
                margin-top: 2px;
            }}
        </style>
    </head>
    <body>
        <div class="clock-box">
            <div class="clock-label">Current Time (GMT +5:30)</div>
            <div id="live-ist-clock" class="clock-time">--:--:--</div>
            <div class="clock-status">Auto-fetch every hour • Last: {st.session_state.get("last_fetch_formatted", "Just now")}</div>
        </div>
        <script>
            function updateClock() {{
                const options = {{
                    timeZone: 'Asia/Kolkata',
                    hour12: true,
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                    day: '2-digit',
                    month: 'short',
                    year: 'numeric'
                }};
                const el = document.getElementById('live-ist-clock');
                if (el) {{
                    el.innerText = new Date().toLocaleString('en-US', options) + ' (GMT+5:30)';
                }}
            }}
            updateClock();
            setInterval(updateClock, 1000);
        </script>
    </body>
    </html>
    """
    components.html(clock_html, height=80)

    if st.button("Fetch Last Hour News"):
        with st.spinner("Fetching news of the last hour..."):
            count = fetch_and_process_news()
            st.session_state["last_fetch_time"] = time.time()
            st.session_state["last_fetch_formatted"] = datetime.datetime.now().strftime("%H:%M:%S")
            st.success(f"Processed {count} news articles of the last hour.")
            st.rerun()

st.markdown("---")

# Contagion Warnings Section
alerts = db.get_active_contagion_alerts()
if alerts:
    for alert in alerts:
        st.markdown(f'<div class="alert-banner">{alert.message}</div>', unsafe_allow_html=True)

# Broader View (Overall Mood calculated hourly)
overall_dashboard = db.get_dashboard_mode(tags=None, hours=1)

mode_colors = {
    "good": "#10B981",
    "bad": "#EF4444",
    "ugly": "#7C3AED",
    "neutral": "#9CA3AF",
}

overall_mode_str = overall_dashboard.dominant_mode.upper()
overall_color = mode_colors.get(overall_dashboard.dominant_mode, "#9CA3AF")

st.markdown('<div class="hero-box">', unsafe_allow_html=True)
st.markdown('<div style="font-size: 12px; font-weight: bold; letter-spacing: 1.5px; color: #818CF8;">BROADER VIEW (LAST HOUR OVERALL MOOD)</div>', unsafe_allow_html=True)

col_hero1, col_hero2, col_hero3, col_hero4 = st.columns([2, 1, 1, 1])

with col_hero1:
    st.markdown(f'<div style="font-size: 32px; font-weight: bold; color: {overall_color};">{overall_mode_str}</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size: 14px; color: #94A3B8;">Global news sentiment calculated for the last hour</div>', unsafe_allow_html=True)

with col_hero2:
    st.metric("Compound Score", f"{overall_dashboard.avg_compound:+.2f}")

with col_hero3:
    st.metric("Last Hour News", overall_dashboard.total_articles)

with col_hero4:
    ugly_pct = round((overall_dashboard.ugly_count / max(overall_dashboard.total_articles, 1)) * 100)
    st.metric("Ugly Index", f"{ugly_pct}%")

st.markdown('</div>', unsafe_allow_html=True)

# Domain Tags Section & Per-Tag Badges (Calculated Hourly)
st.markdown('<div style="font-size: 20px; font-weight: bold; margin-bottom: 12px;">DOMAIN TAGS (HOURLY MODES)</div>', unsafe_allow_html=True)

# Fetch current tag metadata & per-tag modes for the last hour
tags_metadata = db.get_all_tags_with_metadata(hours=1)

# Display Per-Tag Mode Badges in Columns
tag_cols = st.columns(len(DOMAIN_TAGS))
for idx, tag_info in enumerate(tags_metadata):
    with tag_cols[idx]:
        t_color = mode_colors.get(tag_info.dominant_mode, "#9CA3AF")
        st.markdown(
            f"""
            <div style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 8px; text-align: center;">
                <div style="font-size: 14px; font-weight: bold;">{tag_info.label}</div>
                <div style="font-size: 11px; font-weight: bold; color: {t_color}; margin-top: 4px;">{tag_info.dominant_mode.upper()}</div>
                <div style="font-size: 11px; color: #94A3B8; margin-top: 2px;">{tag_info.article_count} articles</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)

# Multi-Select Domain Tags Filter (Intersection Subset)
selected_tags = st.multiselect(
    "Select Domain Tags (Multi-Select Intersection Subset):",
    options=DOMAIN_TAGS,
    default=[],
    format_func=lambda x: TAG_METADATA.get(x, {}).get("label", x.title()),
)

# Fetch Dynamic Dashboard Mode based on Selected Tags (Hourly calculation)
selected_dashboard = db.get_dashboard_mode(tags=selected_tags, hours=1)

st.markdown("---")

if selected_tags:
    st.markdown(f'<div style="font-size: 22px; font-weight: bold; margin-bottom: 16px;">Intersection Subset Breakdown ({ " AND ".join([t.title() for t in selected_tags]) }) — Hourly Mode</div>', unsafe_allow_html=True)
else:
    st.markdown('<div style="font-size: 22px; font-weight: bold; margin-bottom: 16px;">Overall Hourly Sentiment Breakdown</div>', unsafe_allow_html=True)

# 4 Mode Metrics Cards
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
total_sel = max(selected_dashboard.total_articles, 1)

with col_m1:
    pct = round((selected_dashboard.good_count / total_sel) * 100)
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-card-title mode-good">GOOD</div>
            <div class="metric-card-value">{selected_dashboard.good_count}</div>
            <div class="metric-card-pct">{pct}%</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_m2:
    pct = round((selected_dashboard.bad_count / total_sel) * 100)
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-card-title mode-bad">BAD</div>
            <div class="metric-card-value">{selected_dashboard.bad_count}</div>
            <div class="metric-card-pct">{pct}%</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_m3:
    pct = round((selected_dashboard.ugly_count / total_sel) * 100)
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-card-title mode-ugly">UGLY</div>
            <div class="metric-card-value">{selected_dashboard.ugly_count}</div>
            <div class="metric-card-pct">{pct}%</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_m4:
    pct = round((selected_dashboard.neutral_count / total_sel) * 100)
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-card-title mode-neutral">NEUTRAL</div>
            <div class="metric-card-value">{selected_dashboard.neutral_count}</div>
            <div class="metric-card-pct">{pct}%</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# Charts Section (Plotly Donut & 24h Trend Line)
col_chart1, col_chart2 = st.columns([1, 2])

with col_chart1:
    st.markdown('<div style="font-size: 16px; font-weight: bold; margin-bottom: 12px;">Hourly Sentiment Distribution</div>', unsafe_allow_html=True)
    fig_donut = go.Figure(
        data=[
            go.Pie(
                labels=["Good", "Bad", "Ugly", "Neutral"],
                values=[
                    selected_dashboard.good_count,
                    selected_dashboard.bad_count,
                    selected_dashboard.ugly_count,
                    selected_dashboard.neutral_count,
                ],
                hole=0.6,
                marker=dict(colors=["#10B981", "#EF4444", "#7C3AED", "#6B7280"]),
                textinfo="percent+label",
            )
        ]
    )
    fig_donut.update_layout(
        font=dict(family="Times New Roman, Times, serif", color="#F8FAFC"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
    )
    st.plotly_chart(fig_donut, use_container_width=True)

with col_chart2:
    st.markdown('<div style="font-size: 16px; font-weight: bold; margin-bottom: 12px;">24-Hour Sentiment Velocity Trend</div>', unsafe_allow_html=True)
    trend_points = db.get_trends(tags=selected_tags, hours=24)
    
    if trend_points:
        times = [p.snapshot_time for p in trend_points]
        scores = [p.avg_compound for p in trend_points]
        
        fig_line = go.Figure(
            data=[
                go.Scatter(
                    x=times,
                    y=scores,
                    mode="lines+markers",
                    line=dict(color="#6366F1", width=3),
                    marker=dict(color="#818CF8", size=6),
                    fill="tozeroy",
                    fillcolor="rgba(99, 102, 241, 0.1)",
                )
            ]
        )
        fig_line.update_layout(
            font=dict(family="Times New Roman, Times, serif", color="#F8FAFC"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", title=None),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", range=[-1.0, 1.0], title=None),
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("No trend data available for selected criteria.")

st.markdown("---")

# Article Feed Section
st.markdown('<div style="font-size: 20px; font-weight: bold; margin-bottom: 16px;">Live News Feed (Last Hour)</div>', unsafe_allow_html=True)

col_f1, col_f2 = st.columns([1, 3])
with col_f1:
    sentiment_filter = st.selectbox(
        "Filter by Mode:",
        options=["All", "Good", "Bad", "Ugly", "Neutral"],
        index=0,
    )

sent_param = sentiment_filter.lower() if sentiment_filter != "All" else None
articles = db.get_articles(tags=selected_tags, sentiment=sent_param, limit=50)

st.markdown(f'<div style="font-size: 14px; color: #94A3B8; margin-bottom: 16px;">Showing {len(articles)} articles</div>', unsafe_allow_html=True)

if articles:
    for art in articles:
        label_color = mode_colors.get(art.sentiment_label, "#9CA3AF")
        tags_html = " ".join([f'<span class="badge-tag">{t.title()}</span>' for t in art.tags])
        pub_time = art.published_at or art.fetched_at
        
        st.markdown(
            f"""
            <div class="article-item">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 12px; font-weight: bold; color: {label_color}; text-transform: uppercase;">[{art.sentiment_label}]</span>
                    <span style="font-size: 13px; color: #94A3B8;">{art.source_name or 'News'} • {pub_time}</span>
                </div>
                <div style="margin-top: 6px;">
                    <a href="{art.url}" target="_blank" class="article-title-link">{art.title}</a>
                </div>
                <div style="font-size: 14px; color: #CBD5E1; margin-top: 6px;">{art.description or ''}</div>
                <div style="margin-top: 10px;">{tags_html}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
else:
    st.info("No articles found matching the selected criteria.")
