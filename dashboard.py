import streamlit as st
import os
import json
import subprocess
import time

if "pipeline_proc" not in st.session_state:
    st.session_state["pipeline_proc"] = None
if "audit_proc" not in st.session_state:
    st.session_state["audit_proc"] = None

# Configuration
st.set_page_config(page_title="InvoHydra Enterprise SEO", layout="wide")

DATA_DIR = "data"
BLOGS_DIR = os.path.join(DATA_DIR, "blogs")
DIFFICULTY_REPORT = os.path.join(DATA_DIR, "difficulty_report.json")
AUDIT_REPORT = os.path.join(DATA_DIR, "audit_report.json")
STATE_FILE = os.path.join(DATA_DIR, "pipeline_state.json")

# Helper to read JSON
def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

# ─── SIDEBAR: GLOBAL CONTROLS ──────────────────────────────────────────
with st.sidebar:
    st.title("InvoHydra SEO")
    st.markdown("Enterprise SEO Pipeline Control")
    st.divider()
    
    st.subheader("System Actions")
    if st.button("Execute AI Pipeline", type="primary", width="stretch"):
        st.info("Pipeline Execution Started.")
        os.makedirs("data", exist_ok=True)
        log_file = open("data/pipeline_run.log", "w", encoding="utf-8")
        st.session_state["pipeline_proc"] = subprocess.Popen(
            ["python", "-X", "utf8", "main.py"],
            stdout=log_file,
            stderr=subprocess.STDOUT
        )
        st.rerun()
        
    if st.button("Run SEO Rank Audit", width="stretch"):
        st.info("Audit Execution Started.")
        os.makedirs("data", exist_ok=True)
        log_file = open("data/audit_run.log", "w", encoding="utf-8")
        st.session_state["audit_proc"] = subprocess.Popen(
            ["python", "-X", "utf8", "agents/auditor.py"],
            stdout=log_file,
            stderr=subprocess.STDOUT
        )
        st.rerun()
        
    st.divider()
    st.caption("System Status: Online")
    st.caption("Version: 2.1.0 (Enterprise)")

# ─── HEADER & GLOBAL METRICS ───────────────────────────────────────────
st.title("Search Engine Operations")
st.markdown("Centralized monitoring and control system for automated content generation and ranking analytics.")
st.divider()

# Load Data for Metrics
state = load_json(STATE_FILE)
diff_report = load_json(DIFFICULTY_REPORT)
audit = load_json(AUDIT_REPORT)

passed_kw = len(diff_report.get('surviving_keywords', []))
failed_kw = len(diff_report.get('failed', []))
total_blogs = len([f for f in os.listdir(BLOGS_DIR) if f.endswith('.json')]) if os.path.exists(BLOGS_DIR) else 0
top_10_ranks = audit.get("metrics", {}).get("top_10", 0)

# Top Metrics Row
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Blogs Published", total_blogs)
col2.metric("Top 10 Rankings", top_10_ranks)
col3.metric("Approved Keywords", passed_kw)
col4.metric("Current Campaign", state.get('current_topic', 'Idle'))

st.write("") # Spacing

# ─── TABS ────────────────────────────────────────────────────────────
tab_system, tab_intelligence, tab_library, tab_analytics, tab_config = st.tabs([
    "System Overview", 
    "Keyword Intelligence", 
    "Content Management", 
    "Ranking Analytics",
    "Configuration"
])

# ─── TAB 1: SYSTEM OVERVIEW ──────────────────────────────────────────
with tab_system:
    st.subheader("Pipeline Configuration & Status")
    
    with st.container(border=True):
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Last Execution Date:**")
            st.write(state.get('last_run_date', 'No records found.'))
            st.markdown("**Current Active Campaign:**")
            st.write(state.get('current_topic', 'No active campaign.'))
        with col_b:
            st.markdown("**Target Domain:**")
            st.write(audit.get('target_domain', 'invohydra.com'))
            st.markdown("**Infrastructure Status:**")
            st.write("All agents operational and reporting.")
            
    st.write("")
    st.info("To trigger a new weekly generation cycle, use the 'Execute AI Pipeline' button in the sidebar.")

    # Live execution feedback section
    pipeline_active = st.session_state["pipeline_proc"] is not None and st.session_state["pipeline_proc"].poll() is None
    audit_active = st.session_state["audit_proc"] is not None and st.session_state["audit_proc"].poll() is None
    
    if pipeline_active or audit_active:
        st.divider()
        st.subheader("⚙️ Live Process Monitor")
        if pipeline_active:
            st.info("Pipeline is actively running...")
            log_path = "data/pipeline_run.log"
        else:
            st.info("SEO Rank Audit is actively running...")
            log_path = "data/audit_run.log"
            
        # Display the log live
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                log_content = f.read()
            st.code(log_content[-5000:], language="text") # show last 5000 chars
            
        if st.button("🔄 Refresh Logs"):
            st.rerun()
    else:
        # If runs just completed, show static log of last run
        if os.path.exists("data/pipeline_run.log"):
            with st.expander("📄 View Last Pipeline Execution Log"):
                with open("data/pipeline_run.log", "r", encoding="utf-8", errors="ignore") as f:
                    st.code(f.read(), language="text")
        if os.path.exists("data/audit_run.log"):
            with st.expander("📄 View Last Audit Execution Log"):
                with open("data/audit_run.log", "r", encoding="utf-8", errors="ignore") as f:
                    st.code(f.read(), language="text")

# ─── TAB 2: KEYWORD INTELLIGENCE ─────────────────────────────────────
with tab_intelligence:
    st.subheader("Keyword Difficulty & Viability Analysis")
    st.markdown("Automated SERP analysis filtering high-competition queries.")
    
    if diff_report:
        col_pass, col_fail = st.columns(2)
        
        with col_pass:
            st.markdown(f"**Approved Targets ({passed_kw})**")
            surviving = diff_report.get('surviving_keywords', [])
            if surviving:
                st.dataframe([{"Approved Keyword": kw} for kw in surviving], width="stretch", hide_index=True)
                
        with col_fail:
            st.markdown(f"**Rejected Targets ({failed_kw})**")
            failed_kws = diff_report.get('failed', [])
            if failed_kws:
                full_report = diff_report.get('full_report', [])
                failed_data = []
                for kw in failed_kws:
                    reason = "Too competitive"
                    # Find reason in full report
                    for item in full_report:
                        if item.get("keyword") == kw:
                            reason = item.get("reason", reason)
                            break
                    failed_data.append({"Keyword": kw, "Rejection Reason": reason})
                st.dataframe(failed_data, width="stretch", hide_index=True)
                
        st.divider()
        st.markdown("**Detailed Winnability Report**")
        full_report = diff_report.get('full_report', [])
        if full_report:
            report_data = []
            for item in full_report:
                report_data.append({
                    "Keyword": item.get("keyword"),
                    "Verdict": item.get("verdict"),
                    "Score": item.get("score"),
                    "Reason": item.get("reason")
                })
            st.dataframe(report_data, width="stretch", hide_index=True)
            
        CLUSTERS_FILE = os.path.join(DATA_DIR, "clustered_keywords.json")
        if os.path.exists(CLUSTERS_FILE):
            clusters_data = load_json(CLUSTERS_FILE)
            if clusters_data and "clusters" in clusters_data:
                st.divider()
                st.markdown("**Semantic Clusters & Capability Alignment**")
                cluster_rows = []
                for cluster in clusters_data["clusters"]:
                    cluster_rows.append({
                        "Hub Topic": cluster.get("hub_topic"),
                        "Demand": cluster.get("demand"),
                        "Intent": cluster.get("intent"),
                        "Product Fit Rationale": cluster.get("product_fit_rationale"),
                        "Keywords": ", ".join(cluster.get("keywords", []))
                    })
                st.dataframe(cluster_rows, width="stretch", hide_index=True)
    else:
        st.warning("No keyword intelligence data available. Execute the pipeline to populate this section.")

# ─── TAB 3: CONTENT MANAGEMENT ──────────────────────────────────────────
with tab_library:
    st.subheader("Content Management System")
    st.markdown("Review and manage AI-generated editorial content before final deployment.")
    
    if os.path.exists(BLOGS_DIR) and total_blogs > 0:
        blog_files = [f for f in os.listdir(BLOGS_DIR) if f.endswith('.json')]
        
        for file in blog_files:
            blog_data = load_json(os.path.join(BLOGS_DIR, file))
            title = blog_data.get("meta_title", "Untitled Document")
            
            with st.expander(f"{title}"):
                col_meta, col_content = st.columns([1, 2])
                with col_meta:
                    st.markdown("**Target Keyword**")
                    st.write(f"`{blog_data.get('target_keyword', 'N/A')}`")
                    st.markdown("**Meta Description**")
                    st.write(blog_data.get('meta_description', 'N/A'))
                    st.markdown("**File System Reference**")
                    st.code(file)
                with col_content:
                    st.markdown("**Markdown Body Preview**")
                    st.markdown(blog_data.get("markdown_body", "No content available."))
    else:
        st.warning("Content library is currently empty.")

# ─── TAB 4: RANKING ANALYTICS ──────────────────────────────────────────────
with tab_analytics:
    st.subheader("Search Engine Performance")
    st.markdown("Continuous monitoring of target keywords against the primary domain.")
    
    if audit:
        with st.container(border=True):
            metrics = audit.get("metrics", {})
            m1, m2, m3 = st.columns(3)
            m1.metric("Pages in Top 10", metrics.get("top_10", 0))
            m2.metric("Pages on Page 2 (Needs Refresh)", metrics.get("page_2", 0))
            m3.metric("Pages Unranked", metrics.get("not_found", 0))
            
        st.write("")
        st.markdown("**Detailed Position Tracking**")
        if audit.get("detailed_results"):
            results = [{"Target Keyword": k, "SERP Position": v["position"], "Resolved URL": v["url"]} for k, v in audit["detailed_results"].items()]
            st.dataframe(results, width="stretch", hide_index=True)
    else:
        st.warning("Analytics data unavailable. Execute an SEO Rank Audit from the sidebar.")

# ─── TAB 5: CONFIGURATION ──────────────────────────────────────────────────
with tab_config:
    st.subheader("GitHub Automation Settings")
    st.markdown("Configure your remote GitHub connection to enable 100% cloud automation.")
    
    from dotenv import load_dotenv, set_key
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(env_path)
    
    current_repo = os.getenv("GITHUB_REPO", "")
    current_token = os.getenv("GITHUB_TOKEN", "")
    
    with st.form("github_settings"):
        st.markdown("**1. Landing Page Repository Name**")
        repo_input = st.text_input("Format: username/repo-name (e.g., invohydra/landing-page)", value=current_repo)
        
        st.markdown("**2. GitHub Personal Access Token (PAT)**")
        token_input = st.text_input("Needs 'repo' scope permissions.", value=current_token, type="password")
        
        submitted = st.form_submit_button("Save Automation Settings", type="primary")
        if submitted:
            if not os.path.exists(env_path):
                open(env_path, "a").close()
            set_key(env_path, "GITHUB_REPO", repo_input)
            set_key(env_path, "GITHUB_TOKEN", token_input)
            st.success("GitHub Settings Saved Successfully!")

