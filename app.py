import os
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import snowflake.connector
import yaml
from dotenv import load_dotenv

load_dotenv(override=True)

# ---------------------------------------------------------
# Page Configuration & Styling
# ---------------------------------------------------------
st.set_page_config(
    page_title="CI/CD Failure Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background-color: #0b0e14;
        color: #f1f5f9;
    }

    [data-testid="stSidebar"] {
        background-color: #080a0f !important;
        border-right: 1px solid #1e2433;
    }

    .brand-card {
        background: #111520;
        border: 1px solid #1f2738;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
    }

    .brand-title {
        font-size: 24px;
        font-weight: 900;
        letter-spacing: 2px;
        color: #ef4444;
        text-transform: uppercase;
        margin-bottom: 12px;
    }

    .brand-meta {
        font-size: 13px;
        color: #94a3b8;
        line-height: 1.8;
    }

    .brand-meta strong {
        color: #f8fafc;
    }

    .credit-box {
        margin-top: 15px;
        padding-top: 15px;
        border-top: 1px solid #1f2738;
        font-size: 12px;
        color: #64748b;
    }

    .kpi-container {
        display: flex;
        gap: 15px;
        margin-bottom: 25px;
    }

    .kpi-card {
        flex: 1;
        background: #111520;
        border: 1px solid #1f2738;
        border-radius: 10px;
        padding: 16px 20px;
        position: relative;
        overflow: hidden;
    }

    .kpi-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 4px;
        height: 100%;
    }

    .kpi-blue::before { background: #00b4d8; }
    .kpi-red::before { background: #ef4444; }
    .kpi-purple::before { background: #a855f7; }
    .kpi-green::before { background: #10b981; }

    .kpi-title {
        font-size: 11px;
        font-weight: 700;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }

    .kpi-value {
        font-size: 26px;
        font-weight: 800;
        color: #f8fafc;
        margin-top: 4px;
        font-family: 'JetBrains Mono', monospace;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
    }

    .stTabs [data-baseweb="tab"] {
        background-color: #111520;
        border: 1px solid #1f2738;
        border-radius: 8px;
        padding: 8px 18px;
        color: #94a3b8;
        font-weight: 600;
        font-size: 13px;
    }

    .stTabs [aria-selected="true"] {
        background-color: #1f2738 !important;
        color: #38bdf8 !important;
        border-color: #38bdf8 !important;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Data Engine
# ---------------------------------------------------------
@st.cache_data(ttl=30)
def fetch_telemetry_data():
    profile_path = Path.home() / ".dbt" / "profiles.yml"
    if profile_path.exists():
        with open(profile_path, "r") as f:
            profiles = yaml.safe_load(f)
        creds = profiles["telemetry_dbt"]["outputs"]["dev"]
        user = creds["user"]
        password = creds["password"]
        account = creds["account"]
        warehouse = creds.get("warehouse", "TELEMETRY_WH")
        database = creds.get("database", "TELEMETRY_DB")
        role = creds.get("role", "ACCOUNTADMIN")
    else:
        user = os.getenv("SNOWFLAKE_USER", "SHREEYA")
        password = os.getenv("SNOWFLAKE_PASSWORD")
        account = os.getenv("SNOWFLAKE_ACCOUNT", "ejtkakp-kc39074")
        warehouse = os.getenv("SNOWFLAKE_WAREHOUSE", "TELEMETRY_WH")
        database = os.getenv("SNOWFLAKE_DATABASE", "TELEMETRY_DB")
        role = os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN")

    conn = snowflake.connector.connect(
        user=user,
        password=password,
        account=account,
        warehouse=warehouse,
        database=database,
        schema="SILVER",
        role=role
    )
    query = "SELECT * FROM TELEMETRY_DB.SILVER.FCT_ACTIONABLE_FAILURES"
    df_failures = pd.read_sql(query, conn)
    conn.close()
    return df_failures

try:
    df = fetch_telemetry_data()
    df.columns = [col.upper() for col in df.columns]

    # Map column schema
    if "CATEGORY" in df.columns and "FAILURE_CATEGORY" not in df.columns:
        df["FAILURE_CATEGORY"] = df["CATEGORY"]
    if "FAILURE_REASON" in df.columns and "ERROR_MESSAGE" not in df.columns:
        df["ERROR_MESSAGE"] = df["FAILURE_REASON"]
    if "PRIORITY" in df.columns and "SEVERITY" not in df.columns:
        df["SEVERITY"] = df["PRIORITY"].apply(lambda p: "CRITICAL" if p in [1, 99] else "MEDIUM")

    # ---------------------------------------------------------
    # Sidebar Branding
    # ---------------------------------------------------------
    with st.sidebar:
        st.markdown("""
        <div class="brand-card">
            <div class="brand-title">⚡ TELEMETRY</div>
            <div class="brand-meta">
                <div><strong>Domain:</strong> Cloud & CI/CD Intelligence</div>
                <div><strong>Warehouse:</strong> TELEMETRY_WH</div>
                <div><strong>Target Schema:</strong> SILVER</div>
                <div><strong>Engine:</strong> dbt Core + Snowflake</div>
            </div>
            <div class="credit-box">
                <div>👨‍💻 <strong>Pipeline:</strong> Shreeya K. Shiva</div>
                <div>📡 <strong>Source:</strong> GitHub Actions & AWS S3</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### 🔍 Filter Insights")
        
        team_opts = sorted(df["ASSIGNED_TEAM"].dropna().unique().tolist()) if "ASSIGNED_TEAM" in df.columns else []
        selected_teams = st.multiselect("Assigned Team", options=team_opts, default=[], key="filter_team")

        cat_opts = sorted(df["FAILURE_CATEGORY"].dropna().unique().tolist()) if "FAILURE_CATEGORY" in df.columns else []
        selected_cats = st.multiselect("Failure Category", options=cat_opts, default=[], key="filter_cat")

        source_opts = sorted(df["CLASSIFICATION_SOURCE"].dropna().unique().tolist()) if "CLASSIFICATION_SOURCE" in df.columns else []
        selected_sources = st.multiselect("Classification Source", options=source_opts, default=[], key="filter_src")

        st.markdown("---")
        if st.button("🔄 Clear Cache & Rerun", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # Filter Application
    filtered_df = df.copy()
    if selected_teams and "ASSIGNED_TEAM" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["ASSIGNED_TEAM"].isin(selected_teams)]
    if selected_cats and "FAILURE_CATEGORY" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["FAILURE_CATEGORY"].isin(selected_cats)]
    if selected_sources and "CLASSIFICATION_SOURCE" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["CLASSIFICATION_SOURCE"].isin(selected_sources)]

    # Metrics
    total_failures = len(filtered_df)
    critical_failures = len(filtered_df[filtered_df["SEVERITY"].astype(str).str.upper() == "CRITICAL"]) if "SEVERITY" in filtered_df.columns else 0
    rule_classified = len(filtered_df[filtered_df["CLASSIFICATION_SOURCE"].astype(str).str.contains("RULE", case=False, na=False)]) if "CLASSIFICATION_SOURCE" in filtered_df.columns else 0
    llm_classified = len(filtered_df[filtered_df["CLASSIFICATION_SOURCE"].astype(str).str.contains("LLM", case=False, na=False)]) if "CLASSIFICATION_SOURCE" in filtered_df.columns else 0

    # ---------------------------------------------------------
    # Main Header & Top Metric Badges
    # ---------------------------------------------------------
    st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 20px;">
        <div>
            <h1 style="margin: 0; font-size: 28px; font-weight: 800; color: #ffffff;">CI/CD Observability & Failure Intelligence</h1>
            <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 14px;">Automated pipeline failure root-cause extraction, rule matching, and LLM triage fallback.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="kpi-card kpi-blue">
            <div class="kpi-title">Total Actionable Failures</div>
            <div class="kpi-value">{total_failures}</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="kpi-card kpi-red">
            <div class="kpi-title">Critical Incidents</div>
            <div class="kpi-value" style="color: #ef4444;">{critical_failures}</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="kpi-card kpi-green">
            <div class="kpi-title">Deterministic Rule Matches</div>
            <div class="kpi-value" style="color: #10b981;">{rule_classified}</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="kpi-card kpi-purple">
            <div class="kpi-title">LLM Fallback Classifications</div>
            <div class="kpi-value" style="color: #c084fc;">{llm_classified}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)

    # ---------------------------------------------------------
    # Tabs
    # ---------------------------------------------------------
    tab_trends, tab_teams, tab_queue = st.tabs(["📈 Pipeline Trends & Categories", "👥 Team Allocation & Priority", "📋 Incident Triage Queue"])

    with tab_trends:
        chart_col1, chart_col2 = st.columns([6, 4])
        
        with chart_col1:
            st.markdown("#### ⚡ Failure Distribution by Category")
            if not filtered_df.empty and "FAILURE_CATEGORY" in filtered_df.columns:
                cat_bar = filtered_df["FAILURE_CATEGORY"].value_counts().reset_index()
                cat_bar.columns = ["Category", "Count"]
                fig_cat = px.bar(
                    cat_bar, x="Category", y="Count", text="Count",
                    color="Count", color_continuous_scale=["#00b4d8", "#ef4444"]
                )
                fig_cat.update_layout(
                    paper_bgcolor="#111520",
                    plot_bgcolor="#111520",
                    font=dict(color="#94a3b8"),
                    margin=dict(t=20, b=20, l=20, r=20),
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=True, gridcolor="#1f2738"),
                    coloraxis_showscale=False
                )
                st.plotly_chart(fig_cat, use_container_width=True, key="fig_cat")

        with chart_col2:
            st.markdown("#### 🍩 Classification Breakdown")
            if not filtered_df.empty and "FAILURE_CATEGORY" in filtered_df.columns:
                cat_counts = filtered_df["FAILURE_CATEGORY"].value_counts().reset_index()
                cat_counts.columns = ["Category", "Count"]
                fig_donut = px.pie(
                    cat_counts, names="Category", values="Count", hole=0.6,
                    color_discrete_sequence=["#ef4444", "#00b4d8", "#a855f7", "#10b981", "#f59e0b"]
                )
                fig_donut.update_layout(
                    paper_bgcolor="#111520",
                    plot_bgcolor="#111520",
                    font=dict(color="#94a3b8"),
                    margin=dict(t=30, b=20, l=20, r=20),
                    legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center")
                )
                st.plotly_chart(fig_donut, use_container_width=True, key="fig_donut")

    with tab_teams:
        st.markdown("#### 👥 Team Workload & Incident Ownership")
        if not filtered_df.empty and "ASSIGNED_TEAM" in filtered_df.columns:
            team_counts = filtered_df["ASSIGNED_TEAM"].value_counts().reset_index()
            team_counts.columns = ["Team", "Incidents"]
            
            fig_bar = px.bar(
                team_counts, x="Team", y="Incidents", text="Incidents",
                color="Incidents",
                color_continuous_scale=["#10b981", "#f59e0b", "#ef4444"]
            )
            fig_bar.update_layout(
                paper_bgcolor="#111520",
                plot_bgcolor="#111520",
                font=dict(color="#94a3b8"),
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="#1f2738"),
                coloraxis_showscale=False,
                margin=dict(t=20, b=20, l=20, r=20)
            )
            st.plotly_chart(fig_bar, use_container_width=True, key="fig_bar")

    with tab_queue:
        st.markdown("#### 🚨 Actionable Incident Queue & Fix Prescriptions")
        if not filtered_df.empty:
            display_cols = [
                "JOB_ID", "JOB_NAME", "WORKFLOW_NAME", "FAILURE_CATEGORY", 
                "SEVERITY", "ASSIGNED_TEAM", "CLASSIFICATION_SOURCE", "RECOMMENDED_FIX"
            ]
            available_cols = [c for c in display_cols if c in filtered_df.columns]
            st.dataframe(filtered_df[available_cols], use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("#### 🔍 Root-Cause Inspection Drilldown")
            for idx, row in filtered_df.iterrows():
                job_id = row.get("JOB_ID", idx)
                job_name = row.get("JOB_NAME", "Unknown Job")
                cat = row.get("FAILURE_CATEGORY", "Unknown")
                team = row.get("ASSIGNED_TEAM", "Platform Triage")
                src = row.get("CLASSIFICATION_SOURCE", "UNKNOWN")
                fix = row.get("RECOMMENDED_FIX", "Inspect logs")
                err = row.get("ERROR_MESSAGE", "No error captured")

                with st.expander(f"📍 Job #{job_id}: {job_name} | {cat}"):
                    c_a, c_b = st.columns([1, 1])
                    with c_a:
                        st.markdown(f"**Assigned Team:** `{team}`")
                        st.markdown(f"**Source:** `{src}`")
                    with c_b:
                        st.markdown(f"**Recommended Action:** `{fix}`")
                    st.markdown("**Error Log Pattern:**")
                    st.code(err, language="bash")

        else:
            st.info("No actionable failures found.")

except Exception as e:
    st.error(f"Failed to connect or render: {str(e)}")