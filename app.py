import streamlit as st
import database as db
import styles
import requests
import os
from datetime import datetime

# ============ PAGE CONFIG ============
st.set_page_config(
    page_title="Kahani AI Agency Dashboard",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============ LOAD STYLES ============
st.markdown(styles.load_css(), unsafe_allow_html=True)

# ============ SIDEBAR ============
st.sidebar.title("🎨 Kahani AI Agency")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["📊 Dashboard", "📱 Pages", "🔑 Tokens", "📜 Run History", "⚙️ Settings"]
)

st.sidebar.markdown("---")
st.sidebar.info("💡 Your autonomous AI content agency dashboard. Manage multiple pages, track performance, and trigger workflows.")

# ============ DASHBOARD PAGE ============
if page == "📊 Dashboard":
    st.markdown('<p class="main-header">📊 Dashboard Overview</p>', unsafe_allow_html=True)
    
    try:
        pages = db.get_all_pages()
        total_pages = len(pages)
        active_pages = sum(1 for p in pages if p["status"] == "active")
        
        # Get recent runs
        recent_runs = db.get_run_history(limit=10)
        successful_runs = sum(1 for r in recent_runs if r["status"] == "success")
        
        # Metrics row with styled cards
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
        
        # Pages overview
        st.markdown(styles.create_section_header("Your Pages", "📱"), unsafe_allow_html=True)
        if pages:
            for p in pages:
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
                
                # Action buttons
                b1, b2, b3 = st.columns(3)
                with b1:
                    if st.button("🚀 Run Now", key=f"run_{p['id']}"):
                        st.info("Workflow trigger coming in Phase 3!")
                with b2:
                    if st.button("✏️ Edit", key=f"edit_{p['id']}"):
                        st.session_state.editing_page = p["id"]
                with b3:
                    if st.button("🗑️ Delete", key=f"del_{p['id']}"):
                        st.session_state.deleting_page = p["id"]
        else:
            st.info("No pages yet. Go to **📱 Pages** to add your first page!")
        
        # Recent activity
        st.markdown(styles.create_section_header("Recent Activity", "📜"), unsafe_allow_html=True)
        if recent_runs:
            for run in recent_runs[:5]:
                status_emoji = "✅" if run["status"] == "success" else "❌" if run["status"] == "failed" else "⏳"
                st.markdown(f"{status_emoji} **{run['run_type']}** - {run['started_at'].strftime('%Y-%m-%d %H:%M')}")
        else:
            st.info("No runs yet. Trigger your first workflow from the **📱 Pages** tab!")
    
    except Exception as e:
        st.error(f"Database connection error: {e}")
        st.info("💡 Check that DATABASE_URL is set in Streamlit secrets.")

# ============ PAGES MANAGEMENT ============
elif page == "📱 Pages":
    st.markdown('<p class="main-header">📱 Pages Manager</p>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📋 All Pages", "➕ Add New Page"])
    
    with tab1:
        try:
            pages = db.get_all_pages()
            if pages:
                for p in pages:
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
                    
                    # Action buttons
                    b1, b2, b3 = st.columns(3)
                    with b1:
                        if st.button("🚀 Run Now", key=f"run_all_{p['id']}"):
                            st.info("Workflow trigger coming in Phase 3!")
                    with b2:
                        if st.button("✏️ Edit", key=f"edit_all_{p['id']}"):
                            st.session_state.editing_page = p["id"]
                    with b3:
                        if st.button("🗑️ Delete", key=f"del_all_{p['id']}"):
                            st.session_state.deleting_page = p["id"]
            else:
                st.info("No pages yet. Add your first page in the **➕ Add New Page** tab!")
        except Exception as e:
            st.error(f"Error: {e}")
    
    with tab2:
        with st.form("add_page_form"):
            name = st.text_input("Page Name *", placeholder="e.g., Kahani AI")
            niche = st.text_input("Niche *", placeholder="e.g., Parenting & Kids Stories")
            description = st.text_area("Description", placeholder="Brief description of this page...")
            
            submitted = st.form_submit_button("➕ Create Page", use_container_width=True)
            
            if submitted:
                if not name or not niche:
                    st.error("Name and niche are required!")
                else:
                    try:
                        page_id = db.create_page(name, niche, description)
                        st.success(f"✅ Page '{name}' created successfully!")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Error creating page: {e}")

# ============ TOKENS MANAGEMENT ============
elif page == "🔑 Tokens":
    st.markdown('<p class="main-header">🔑 Access Tokens</p>', unsafe_allow_html=True)
    st.info("💡 Connect your Facebook and Instagram accounts to each page. OAuth auto-connect coming in Phase 2!")
    
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
                
                # Show existing tokens
                st.markdown(styles.create_section_header("Connected Accounts", "📋"), unsafe_allow_html=True)
                tokens = db.get_tokens(page_id)
                if tokens:
                    for t in tokens:
                        platform_emoji = "📘" if t["platform"] == "facebook" else "📸" if t["platform"] == "instagram" else "📝"
                        st.markdown(f"{platform_emoji} **{t['platform'].title()}** - External ID: `{t.get('external_id', 'N/A')}`")
                        st.caption(f"Connected: {t['connected_at'].strftime('%Y-%m-%d %H:%M')}")
                else:
                    st.info("No accounts connected yet.")
                
                st.markdown("---")
                
                # Add new token
                st.markdown(styles.create_section_header("Connect New Account", "➕"), unsafe_allow_html=True)
                with st.form("add_token_form"):
                    platform = st.selectbox("Platform", ["facebook", "instagram", "notion"])
                    access_token = st.text_input("Access Token *", type="password")
                    external_id = st.text_input("External ID (Page ID / Account ID)", placeholder="e.g., 1201839566347724")
                    
                    submitted = st.form_submit_button("💾 Save Token", use_container_width=True)
                    
                    if submitted:
                        if not access_token:
                            st.error("Access token is required!")
                        else:
                            try:
                                db.save_token(page_id, platform, access_token, external_id)
                                st.success(f"✅ {platform.title()} token saved!")
                                st.balloons()
                            except Exception as e:
                                st.error(f"Error saving token: {e}")
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
    
    # Check database
    try:
        pages = db.get_all_pages()
        st.success(f"✅ Neon Database: Connected ({len(pages)} pages)")
    except Exception as e:
        st.error(f"❌ Neon Database: {e}")
    
    # Check environment variables
    st.markdown(styles.create_section_header("Environment Variables", "🔐"), unsafe_allow_html=True)
    env_vars = ["NOTION_API_KEY", "NOTION_DATABASE_ID", "MISTRAL_API_KEY", 
                "FACEBOOK_PAGE_ID", "FACEBOOK_ACCESS_TOKEN", "INSTAGRAM_ACCOUNT_ID",
                "STRATEGY_DB_ID", "MEMORY_DB_ID", "DATABASE_URL"]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            masked = value[:5] + "..." + value[-5:] if len(value) > 10 else "***"
            st.success(f"✅ {var}: `{masked}`")
        else:
            st.warning(f"⚠️ {var}: Not set")
    
    st.markdown("---")
    st.info("💡 This dashboard is in Phase 1. Phase 2 will add Facebook OAuth auto-connect. Phase 3 will add workflow triggering.")
