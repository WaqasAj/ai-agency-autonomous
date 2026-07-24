import streamlit as st
import database as db
import styles
import os

st.set_page_config(
    page_title="Kahani AI Agency Dashboard",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(styles.load_css(), unsafe_allow_html=True)

# Your GitHub credentials
GITHUB_USERNAME = "WaqasAj"
GITHUB_REPO = "ai-agency-autonomous"

st.sidebar.title("🎨 Kahani AI Agency")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["📊 Dashboard", "📱 Pages", "🔑 Tokens", "📜 Run History", "⚙️ Settings"]
)

st.sidebar.markdown("---")
st.sidebar.info("💡 Your autonomous AI content agency dashboard.")


def trigger_workflow_for_page(page_id):
    """Helper function to trigger workflow - defined once, used everywhere."""
    github_token = os.getenv("WORKFLOW_TRIGGER_TOKEN")
    
    if not github_token:
        st.error("❌ WORKFLOW_TRIGGER_TOKEN not set in Streamlit secrets!")
        return
    
    with st.spinner("Triggering workflow..."):
        result = db.trigger_github_workflow(
            page_id=page_id,
            github_token=github_token,
            repo_owner=GITHUB_USERNAME,
            repo_name=GITHUB_REPO
        )
        
        if result["success"]:
            st.success(f"✅ Workflow triggered! Run ID: {result['run_id']}")
            st.info("Check GitHub Actions for progress. Takes 5-10 minutes.")
        else:
            st.error(f"❌ Failed: {result['error']}")


def render_page_card(p):
    """Render a page card with action buttons."""
    st.markdown(
        styles.create_page_card(
            p['name'],
            p.get('niche', 'No niche'),
            p['status'],
            p['created_at'].strftime('%Y-%m-%d'),
            p.get('description', '')
        ),
        unsafe_allow_html=True
    )
    
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        if st.button("🚀 Run Now", key=f"run_{p['id']}", type="primary"):
            trigger_workflow_for_page(p['id'])
    with b2:
        if st.button("📜 View Logs", key=f"logs_{p['id']}"):
            st.session_state.viewing_logs = p["id"]
            st.rerun()
    with b3:
        if st.button("✏️ Edit", key=f"edit_{p['id']}"):
            st.session_state.editing_page = p["id"]
    with b4:
        if st.button("🗑️ Delete", key=f"del_{p['id']}"):
            st.session_state.deleting_page = p["id"]


# ============ DASHBOARD ============
if page == "📊 Dashboard":
    st.markdown('<p class="main-header">📊 Dashboard Overview</p>', unsafe_allow_html=True)
    
    try:
        pages = db.get_all_pages()
        total_pages = len(pages)
        active_pages = sum(1 for p in pages if p["status"] == "active")
        recent_runs = db.get_run_history(limit=10)
        successful_runs = sum(1 for r in recent_runs if r["status"] == "success")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(styles.create_metric_card(total_pages, "Total Pages", "📱"), unsafe_allow_html=True)
        with col2:
            st.markdown(styles.create_metric_card(active_pages, "Active Pages", "✅"), unsafe_allow_html=True)
        with col3:
            st.markdown(styles.create_metric_card(len(recent_runs), "Recent Runs", "🚀"), unsafe_allow_html=True)
        with col4:
            success_rate = (successful_runs / len(recent_runs) * 100) if recent_runs else 0
            st.markdown(styles.create_metric_card(f"{success_rate:.0f}%", "Success Rate", "📈"), unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown(styles.create_section_header("Your Pages", "📱"), unsafe_allow_html=True)
        
        if pages:
            for p in pages:
                render_page_card(p)
        else:
            st.info("No pages yet. Go to **📱 Pages** to add your first page!")
        
        st.markdown(styles.create_section_header("Recent Activity", "📜"), unsafe_allow_html=True)
        if recent_runs:
            for run in recent_runs[:5]:
                status_emoji = "✅" if run["status"] == "success" else "❌" if run["status"] == "failed" else "⏳"
                st.markdown(f"{status_emoji} **{run['run_type']}** - {run['started_at'].strftime('%Y-%m-%d %H:%M')}")
        else:
            st.info("No runs yet.")
    
    except Exception as e:
        st.error(f"Database connection error: {e}")


# ============ PAGES ============
elif page == "📱 Pages":
    st.markdown('<p class="main-header">📱 Pages Manager</p>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📋 All Pages", "➕ Add New Page"])
    
    with tab1:
        try:
            pages = db.get_all_pages()
            if pages:
                for p in pages:
                    render_page_card(p)
            else:
                st.info("No pages yet. Add your first page in the **➕ Add New Page** tab!")
        except Exception as e:
            st.error(f"Error: {e}")
    
    with tab2:
        with st.form("add_page_form"):
            name = st.text_input("Page Name *", placeholder="e.g., Kahani AI")
            niche = st.text_input("Niche *", placeholder="e.g., Parenting & Kids Stories")
            description = st.text_area("Description", placeholder="Brief description...")
            
            submitted = st.form_submit_button("➕ Create Page", use_container_width=True)
            
            if submitted:
                if not name or not niche:
                    st.error("Name and niche are required!")
                else:
                    try:
                        page_id = db.create_page(name, niche, description)
                        st.success(f"✅ Page '{name}' created!")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Error: {e}")


# ============ TOKENS ============
elif page == "🔑 Tokens":
    st.markdown('<p class="main-header">🔑 Access Tokens</p>', unsafe_allow_html=True)
    
    try:
        pages = db.get_all_pages()
        if not pages:
            st.warning("No pages yet. Add a page first!")
        else:
            selected_page = st.selectbox(
                "Select Page",
                options=pages,
                format_func=lambda p: f"{p['name']} ({p['niche']})"
            )
            
            if selected_page:
                page_id = selected_page["id"]
                page_data = db.get_page_with_tokens(page_id)
                tokens = page_data.get("tokens", [])
                
                st.markdown(styles.create_section_header("Connected Accounts", "📋"), unsafe_allow_html=True)
                
                if tokens:
                    for t in tokens:
                        platform_emoji = "📘" if t["platform"] == "facebook" else "📸" if t["platform"] == "instagram" else "📝"
                        
                        with st.container():
                            col1, col2, col3 = st.columns([3, 2, 1])
                            
                            with col1:
                                st.markdown(f"### {platform_emoji} {t['platform'].title()}")
                                st.caption(f"External ID: `{t.get('external_id', 'N/A')}`")
                                st.caption(f"Connected: {t['connected_at'].strftime('%Y-%m-%d %H:%M')}")
                            
                            with col2:
                                if st.button("🔍 Test Connection", key=f"test_{t['id']}"):
                                    with st.spinner("Testing..."):
                                        if t["platform"] == "facebook":
                                            result = db.test_facebook_connection(t["access_token"], t["external_id"])
                                        elif t["platform"] == "instagram":
                                            fb_token = next((tok for tok in tokens if tok["platform"] == "facebook"), None)
                                            if fb_token:
                                                result = db.test_instagram_connection(fb_token["access_token"], t["external_id"])
                                            else:
                                                result = {"valid": False, "error": "Facebook token required"}
                                        else:
                                            result = {"valid": True, "message": "Notion assumed valid"}
                                        
                                        if result["valid"]:
                                            if t["platform"] == "facebook":
                                                st.success(f"✅ Valid! Page: {result['page_name']}")
                                            elif t["platform"] == "instagram":
                                                st.success(f"✅ Valid! Username: @{result['username']}")
                                            else:
                                                st.success("✅ Valid!")
                                        else:
                                            st.error(f"❌ Invalid: {result['error']}")
                            
                            with col3:
                                if st.button("🗑️ Remove", key=f"remove_{t['id']}"):
                                    st.session_state.removing_token = t["id"]
                            
                            st.markdown("---")
                else:
                    st.info("No accounts connected yet.")
                
                st.markdown("---")
                st.markdown(styles.create_section_header("Connect New Account", "➕"), unsafe_allow_html=True)
                
                with st.form("add_token_form"):
                    platform = st.selectbox("Platform", ["facebook", "instagram", "notion"])
                    
                    if platform == "facebook":
                        st.info("💡 Get token from [Graph API Explorer](https://developers.facebook.com/tools/explorer/)")
                        access_token = st.text_input("Page Access Token *", type="password")
                        external_id = st.text_input("Facebook Page ID *", placeholder="e.g., 1201839566347724")
                    elif platform == "instagram":
                        st.info("💡 Get Instagram Business Account ID from Graph API Explorer")
                        access_token = st.text_input("Access Token *", type="password")
                        external_id = st.text_input("Instagram Business Account ID *", placeholder="e.g., 17841443468123904")
                    else:
                        access_token = st.text_input("Notion Integration Token *", type="password")
                        external_id = st.text_input("Notion Database ID *")
                    
                    submitted = st.form_submit_button("💾 Save & Test Connection", use_container_width=True)
                    
                    if submitted:
                        if not access_token or not external_id:
                            st.error("All fields are required!")
                        else:
                            with st.spinner("Testing connection..."):
                                if platform == "facebook":
                                    test_result = db.test_facebook_connection(access_token, external_id)
                                elif platform == "instagram":
                                    fb_token = next((t for t in tokens if t["platform"] == "facebook"), None)
                                    if fb_token:
                                        test_result = db.test_instagram_connection(fb_token["access_token"], external_id)
                                    else:
                                        test_result = {"valid": False, "error": "Add Facebook token first"}
                                else:
                                    test_result = {"valid": True}
                                
                                if test_result["valid"]:
                                    try:
                                        db.save_token(page_id, platform, access_token, external_id)
                                        if platform == "facebook":
                                            st.success(f"✅ Connected to: {test_result['page_name']}")
                                        elif platform == "instagram":
                                            st.success(f"✅ Connected to: @{test_result['username']}")
                                        else:
                                            st.success("✅ Token saved!")
                                        st.balloons()
                                    except Exception as e:
                                        st.error(f"Error: {e}")
                                else:
                                    st.error(f"❌ Connection failed: {test_result['error']}")
    except Exception as e:
        st.error(f"Error: {e}")


# ============ RUN HISTORY ============
elif page == "📜 Run History":
    st.markdown('<p class="main-header">📜 Run History</p>', unsafe_allow_html=True)
    
    try:
        pages = db.get_all_pages()
        page_options = [None] + pages
        selected_page = st.selectbox(
            "Filter by Page",
            options=page_options,
            format_func=lambda p: "All Pages" if p is None else f"{p['name']} ({p['niche']})"
        )
        
        page_id = selected_page["id"] if selected_page else None
        runs = db.get_run_history(page_id=page_id, limit=50)
        
        if runs:
            for run in runs:
                status_emoji = "✅" if run["status"] == "success" else "❌" if run["status"] == "failed" else "⏳"
                with st.expander(f"{status_emoji} {run['run_type']} - {run['started_at'].strftime('%Y-%m-%d %H:%M')}"):
                    st.markdown(f"**Status:** {run['status']}")
                    if run.get('details'):
                        st.json(run['details'])
                    if run.get('error_message'):
                        st.error(run['error_message'])
        else:
            st.info("No runs yet.")
    except Exception as e:
        st.error(f"Error: {e}")


# ============ SETTINGS ============
elif page == "⚙️ Settings":
    st.markdown('<p class="main-header">⚙️ Settings</p>', unsafe_allow_html=True)
    
    st.markdown(styles.create_section_header("Connection Status", "🔌"), unsafe_allow_html=True)
    
    try:
        pages = db.get_all_pages()
        st.success(f"✅ Neon Database: Connected ({len(pages)} pages)")
    except Exception as e:
        st.error(f"❌ Neon Database: {e}")
    
    st.markdown(styles.create_section_header("Environment Variables", "🔐"), unsafe_allow_html=True)
    env_vars = ["NOTION_API_KEY", "NOTION_DATABASE_ID", "MISTRAL_API_KEY", 
                "FACEBOOK_PAGE_ID", "FACEBOOK_ACCESS_TOKEN", "INSTAGRAM_ACCOUNT_ID",
                "STRATEGY_DB_ID", "MEMORY_DB_ID", "DATABASE_URL", "WORKFLOW_TRIGGER_TOKEN"]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            masked = value[:5] + "..." + value[-5:] if len(value) > 10 else "***"
            st.success(f"✅ {var}: `{masked}`")
        else:
            st.warning(f"⚠️ {var}: Not set")
    
    st.markdown("---")
    st.info("💡 Phase 3 complete! Trigger workflows directly from this dashboard.")
