import streamlit as st
import os
import json
import subprocess
import time
import re

if "pipeline_proc" not in st.session_state:
    st.session_state["pipeline_proc"] = None
if "audit_proc" not in st.session_state:
    st.session_state["audit_proc"] = None

# Configuration
st.set_page_config(page_title="InvoHydra Enterprise SEO", layout="wide")

# CSS Styling for SaaS Reporting & Steppers
st.markdown("""
<style>
    /* Global styles */
    .report-title {
        font-family: 'Inter', -apple-system, sans-serif;
        font-weight: 800;
        color: #1e293b;
        margin-bottom: 2px;
    }
    .report-subtitle {
        color: #64748b;
        font-size: 1.05rem;
        margin-bottom: 20px;
    }
    
    /* Card layout */
    .agent-grid {
        display: flex;
        flex-direction: column;
        gap: 12px;
        margin-top: 15px;
        margin-bottom: 20px;
    }
    
    .agent-card {
        border-radius: 10px;
        padding: 16px 20px;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        display: flex;
        align-items: center;
        justify-content: space-between;
        transition: all 0.2s ease-in-out;
    }
    
    /* Dark mode adjustments via Streamlit custom components theme compatibility */
    @media (prefers-color-scheme: dark) {
        .agent-card {
            background: #1e293b;
            border-color: #334155;
        }
        .agent-title {
            color: #f1f5f9 !important;
        }
        .agent-desc {
            color: #cbd5e1 !important;
        }
    }
    
    .agent-info {
        display: flex;
        flex-direction: column;
        gap: 4px;
        flex-grow: 1;
        margin-right: 20px;
    }
    
    .agent-header-row {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .agent-title {
        font-weight: 700;
        font-size: 1.05rem;
        color: #0f172a;
        margin: 0;
    }
    
    .agent-desc {
        font-size: 0.9rem;
        color: #475569;
        margin: 0;
    }
    
    /* Status Badge styling */
    .status-badge {
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }
    
    .status-pending {
        background-color: #f1f5f9;
        color: #64748b;
        border: 1px solid #cbd5e1;
    }
    
    .status-running {
        background-color: #dbeafe;
        color: #2563eb;
        border: 1px solid #bfdbfe;
        animation: pulse-border 1.5s infinite alternate;
    }
    
    .status-completed {
        background-color: #dcfce7;
        color: #16a34a;
        border: 1px solid #bbf7d0;
    }
    
    .status-failed {
        background-color: #fee2e2;
        color: #dc2626;
        border: 1px solid #fecaca;
    }
    
    @keyframes pulse-border {
        0% {
            box-shadow: 0 0 0 0px rgba(37, 99, 235, 0.4);
        }
        100% {
            box-shadow: 0 0 0 6px rgba(37, 99, 235, 0);
        }
    }
</style>
""", unsafe_allow_html=True)

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

# Log parsing utility for Pipeline Run
def parse_pipeline_logs(log_path):
    state = {
        "active_phase": 0,
        "phases": {
            1: {"status": "pending", "details": "Awaiting keyword exploration..."},
            2: {"status": "pending", "details": "Awaiting difficulty & volume checks..."},
            3: {"status": "pending", "details": "Awaiting product capability mapping..."},
            4: {"status": "pending", "details": "Awaiting SEO article generation..."},
            5: {"status": "pending", "details": "Awaiting header image downloads & layout formatting..."},
            6: {"status": "pending", "details": "Awaiting repository commit & pull request submission..."}
        }
    }
    if not os.path.exists(log_path):
        return state

    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except:
        return state

    # Parse Agent 1
    if "PHASE 1 — AGENT 1" in content:
        state["phases"][1]["status"] = "running"
        state["active_phase"] = 1
        seeds = re.findall(r"Seed topics configured: (\d+)", content)
        kw_saved = re.findall(r"Combined total across \d+ seed topics: (\d+) unique keywords", content)
        if kw_saved:
            state["phases"][1]["status"] = "completed"
            state["phases"][1]["details"] = f"✅ Success: Discovered {kw_saved[-1]} unique search opportunities."
        elif seeds:
            state["phases"][1]["details"] = f"🔍 Active: Mining search terms from Serper API (Topics config: {seeds[-1]})...."
        else:
            state["phases"][1]["details"] = "🔍 Starting Keyword Discovery..."

    # Parse Agent 2
    if "PHASE 2 — AGENT 2" in content:
        state["phases"][1]["status"] = "completed"
        state["phases"][2]["status"] = "running"
        state["active_phase"] = 2
        passed = re.findall(r"Passed:\s*(\d+)", content)
        failed = re.findall(r"Failed \(Too Hard\):\s*(\d+)", content)
        winnable = re.findall(r"Passing (\d+) winnable keywords", content)
        if winnable:
            state["phases"][2]["status"] = "completed"
            state["phases"][2]["details"] = f"✅ Success: Passed {winnable[-1]} low-competition terms. (Filtered: Failed {failed[-1] if failed else 0})."
        elif passed or failed:
            state["phases"][2]["details"] = f"⚡ Active: Filtering search volume & difficulty (Passed: {passed[-1] if passed else 0}, Failed: {failed[-1] if failed else 0})...."
        else:
            state["phases"][2]["details"] = "⚡ Active: Fetching SERP metrics & assessing winnability..."

    # Parse Agent 3
    if "PHASE 3 — AGENT 3" in content:
        state["phases"][2]["status"] = "completed"
        state["phases"][3]["status"] = "running"
        state["active_phase"] = 3
        clusters = re.findall(r"Clustered into (\d+) topic clusters", content)
        rejected = re.findall(r"Rejected (\d+) keywords", content)
        if clusters:
            state["phases"][3]["status"] = "completed"
            state["phases"][3]["details"] = f"✅ Success: Grouped into {clusters[-1]} editorial clusters. (Rejected {rejected[-1] if rejected else 0} due to lack of product fit)."
        else:
            state["phases"][3]["details"] = "🧠 Active: Matching terms with InvoHydra product capabilities..."

    # Parse Agent 4
    if "PHASE 4 — AGENT 4" in content:
        state["phases"][3]["status"] = "completed"
        state["phases"][4]["status"] = "running"
        state["active_phase"] = 4
        writing_for = re.findall(r"Generating blog for:\s*'([^']+)'", content)
        saved_blog = re.findall(r"Saved blog post to:\s*([^\n]+)", content)
        total_clusters = re.findall(r"Total clusters:\s*(\d+)", content)
        limit = re.findall(r"Limiting generation to (\d+) new blog posts", content)
        
        tot_target = limit[-1] if limit else (total_clusters[-1] if total_clusters else "?")
        done_count = len(saved_blog)
        
        if "ILLUSTRATION COMPLETE" in content or "Found" in content and "blogs to illustrate" in content:
            state["phases"][4]["status"] = "completed"
            state["phases"][4]["details"] = f"✅ Success: Authored {done_count} premium articles."
        elif writing_for:
            state["phases"][4]["details"] = f"✍️ Active: Writing article {done_count + 1} of {tot_target}: '{writing_for[-1]}'"
        else:
            state["phases"][4]["details"] = "✍️ Active: Preparing blog structures and outline schemas..."

    # Parse Agent 4.5
    if "blogs to illustrate" in content or "Fetching unique Unsplash header image" in content or "📸" in content:
        state["phases"][4]["status"] = "completed"
        state["phases"][5]["status"] = "running"
        state["active_phase"] = 5
        illustrated = re.findall(r"Successfully fetched and saved Unsplash image", content)
        to_illustrate = re.findall(r"Found (\d+) blogs to illustrate", content)
        tot_illustrate = to_illustrate[-1] if to_illustrate else "?"
        
        if "ILLUSTRATION COMPLETE" in content or "PHASE 5 — AUTO-PUBLISHER" in content:
            state["phases"][5]["status"] = "completed"
            state["phases"][5]["details"] = f"✅ Success: Gathered header illustrations for all {tot_illustrate} articles."
        else:
            state["phases"][5]["details"] = f"📸 Active: Querying Unsplash for matching media (Completed: {len(illustrated)} of {tot_illustrate})..."

    # Parse Agent 5
    if "PHASE 5 — AUTO-PUBLISHER" in content:
        state["phases"][5]["status"] = "completed"
        state["phases"][6]["status"] = "running"
        state["active_phase"] = 6
        if "PIPELINE RUN COMPLETE" in content:
            state["phases"][6]["status"] = "completed"
            state["phases"][6]["details"] = "✅ Success: Content synced, branch pushed, and Pull Request generated."
        else:
            state["phases"][6]["details"] = "🚀 Active: Cloning website repository and pushing changes..."

    return state

# Log parsing utility for Auditor Run
def parse_audit_logs(log_path):
    state = {
        "status": "pending",
        "details": "Awaiting rank audit trigger..."
    }
    if not os.path.exists(log_path):
        return state

    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except:
        return state

    if "🕵️  AGENT 6: PERFORMANCE AUDITOR" in content:
        state["status"] = "running"
        found_blogs = re.findall(r"Found (\d+) published blogs", content)
        checking_lines = re.findall(r"Checking rank for keyword:", content)
        checked_count = len(checking_lines)
        tot_blogs = found_blogs[-1] if found_blogs else "?"
        
        if "Auditing completed" in content or "Saved audit report" in content:
            state["status"] = "completed"
            state["details"] = f"✅ Success: Audited all {tot_blogs} blogs against target SERPs."
        else:
            state["details"] = f"🕵️ Active: Checking live Google positions... (Audited: {checked_count} of {tot_blogs})"
    return state

# Helper to render status badge HTML
def render_status(status):
    if status == "running":
        return '<span class="status-badge status-running">● Running</span>'
    elif status == "completed":
        return '<span class="status-badge status-completed">✓ Done</span>'
    elif status == "failed":
        return '<span class="status-badge status-failed">✗ Failed</span>'
    else:
        return '<span class="status-badge status-pending">○ Pending</span>'

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

# Check active states
pipeline_active = st.session_state["pipeline_proc"] is not None and st.session_state["pipeline_proc"].poll() is None
audit_active = st.session_state["audit_proc"] is not None and st.session_state["audit_proc"].poll() is None

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
    col_info_a, col_info_b = st.columns([2, 1])
    
    with col_info_a:
        st.subheader("⚡ Live Agent Workspace")
        st.markdown("Monitor automated agent interactions during campaign execution.")
        
        # Render the Stepper Pipeline
        log_path = "data/pipeline_run.log"
        pipeline_status = parse_pipeline_logs(log_path)
        
        st.markdown('<div class="agent-grid">', unsafe_allow_html=True)
        
        # Agent 1
        a1_status = pipeline_status["phases"][1]["status"]
        a1_details = pipeline_status["phases"][1]["details"]
        st.markdown(f"""
        <div class="agent-card">
            <div class="agent-info">
                <div class="agent-header-row">
                    <p class="agent-title">Agent 1: Keyword Discoverer</p>
                </div>
                <p class="agent-desc">{a1_details}</p>
            </div>
            {render_status(a1_status)}
        </div>
        """, unsafe_allow_html=True)
        
        # Agent 2
        a2_status = pipeline_status["phases"][2]["status"]
        a2_details = pipeline_status["phases"][2]["details"]
        st.markdown(f"""
        <div class="agent-card">
            <div class="agent-info">
                <div class="agent-header-row">
                    <p class="agent-title">Agent 2: Difficulty Analyst</p>
                </div>
                <p class="agent-desc">{a2_details}</p>
            </div>
            {render_status(a2_status)}
        </div>
        """, unsafe_allow_html=True)
        
        # Agent 3
        a3_status = pipeline_status["phases"][3]["status"]
        a3_details = pipeline_status["phases"][3]["details"]
        st.markdown(f"""
        <div class="agent-card">
            <div class="agent-info">
                <div class="agent-header-row">
                    <p class="agent-title">Agent 3: Semantic Clusterer</p>
                </div>
                <p class="agent-desc">{a3_details}</p>
            </div>
            {render_status(a3_status)}
        </div>
        """, unsafe_allow_html=True)
        
        # Agent 4
        a4_status = pipeline_status["phases"][4]["status"]
        a4_details = pipeline_status["phases"][4]["details"]
        st.markdown(f"""
        <div class="agent-card">
            <div class="agent-info">
                <div class="agent-header-row">
                    <p class="agent-title">Agent 4: Blog Writer</p>
                </div>
                <p class="agent-desc">{a4_details}</p>
            </div>
            {render_status(a4_status)}
        </div>
        """, unsafe_allow_html=True)
        
        # Agent 4.5
        a5_status = pipeline_status["phases"][5]["status"]
        a5_details = pipeline_status["phases"][5]["details"]
        st.markdown(f"""
        <div class="agent-card">
            <div class="agent-info">
                <div class="agent-header-row">
                    <p class="agent-title">Agent 4.5: Media Illustrator</p>
                </div>
                <p class="agent-desc">{a5_details}</p>
            </div>
            {render_status(a5_status)}
        </div>
        """, unsafe_allow_html=True)
        
        # Agent 5
        a6_status = pipeline_status["phases"][6]["status"]
        a6_details = pipeline_status["phases"][6]["details"]
        st.markdown(f"""
        <div class="agent-card">
            <div class="agent-info">
                <div class="agent-header-row">
                    <p class="agent-title">Agent 5: Auto-Publisher</p>
                </div>
                <p class="agent-desc">{a6_details}</p>
            </div>
            {render_status(a6_status)}
        </div>
        """, unsafe_allow_html=True)
        
        # Agent 6 (Performance Auditor) - Show if Auditor is active or has run previously
        audit_log_path = "data/audit_run.log"
        audit_status = parse_audit_logs(audit_log_path)
        if audit_active or audit_status["status"] != "pending":
            st.markdown(f"""
            <div class="agent-card">
                <div class="agent-info">
                    <div class="agent-header-row">
                        <p class="agent-title">Agent 6: Performance Auditor</p>
                    </div>
                    <p class="agent-desc">{audit_status["details"]}</p>
                </div>
                {render_status(audit_status["status"])}
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col_info_b:
        st.subheader("📋 Pipeline Context")
        with st.container(border=True):
            st.markdown("**Campaign Active:**")
            st.write(state.get('current_topic', 'None (Idle)'))
            st.markdown("**Last Action Date:**")
            st.write(state.get('last_run_date', 'None'))
            st.markdown("**Domain Host:**")
            st.write(audit.get('target_domain', 'invohydra.com'))
            st.markdown("**Health Status:**")
            if pipeline_active:
                st.info("⚡ Execution In Progress")
            elif audit_active:
                st.info("🕵️ Rank Auditing In Progress")
            else:
                st.success("🟢 Ready / Idle")

    # Terminal Log Tail
    if pipeline_active or audit_active:
        active_log = "data/pipeline_run.log" if pipeline_active else "data/audit_run.log"
        st.subheader("🖥️ Live Operations Feed")
        if os.path.exists(active_log):
            with open(active_log, "r", encoding="utf-8", errors="ignore") as f:
                log_data = f.read()
            st.code(log_data[-4000:], language="text")
        
        # Rerun automatically to stream logs
        time.sleep(1.5)
        st.rerun()
    else:
        # Show past runs
        st.write("")
        col_logs_a, col_logs_b = st.columns(2)
        with col_logs_a:
            if os.path.exists("data/pipeline_run.log"):
                with st.expander("📄 Last Pipeline Logs"):
                    with open("data/pipeline_run.log", "r", encoding="utf-8", errors="ignore") as f:
                        st.code(f.read()[-6000:], language="text")
        with col_logs_b:
            if os.path.exists("data/audit_run.log"):
                with st.expander("📄 Last Auditor Logs"):
                    with open("data/audit_run.log", "r", encoding="utf-8", errors="ignore") as f:
                        st.code(f.read()[-6000:], language="text")

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
