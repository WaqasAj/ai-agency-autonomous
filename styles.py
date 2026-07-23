"""
Kahani AI Agency Dashboard - Clean Professional Styles
Modern, minimal design with excellent readability
"""

def load_css():
    """Load custom CSS styles for the Streamlit app."""
    return """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* ============ GLOBAL ============ */
    .stApp {
        background: #f8fafc;
        font-family: 'Inter', sans-serif;
    }
    
    .main .block-container {
        padding: 2rem 3rem;
        max-width: 1400px;
    }
    
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 2rem;
        letter-spacing: -0.5px;
    }
    
    .sub-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #334155;
        margin: 2rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e2e8f0;
    }
    
    /* ============ METRIC CARDS ============ */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border: 1px solid #e2e8f0;
        transition: all 0.2s ease;
    }
    
    .metric-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
    
    .metric-icon {
        font-size: 2rem;
        margin-bottom: 0.5rem;
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        color: #3b82f6;
        margin: 0.5rem 0;
    }
    
    .metric-label {
        font-size: 0.875rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 600;
    }
    
    /* ============ PAGE CARDS ============ */
    .page-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        transition: all 0.2s ease;
    }
    
    .page-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        border-color: #3b82f6;
    }
    
    .page-card h3 {
        margin: 0 0 0.5rem 0;
        color: #1e293b;
        font-size: 1.25rem;
        font-weight: 600;
    }
    
    .page-card p {
        margin: 0.25rem 0;
        color: #64748b;
        font-size: 0.95rem;
    }
    
    /* ============ BUTTONS ============ */
    .stButton>button {
        background: #3b82f6;
        color: white !important;
        border: none;
        padding: 0.5rem 1.5rem;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    .stButton>button:hover {
        background: #2563eb;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    }
    
    /* ============ SIDEBAR ============ */
    [data-testid="stSidebar"] {
        background: #1e293b;
    }
    
    [data-testid="stSidebar"] .stMarkdown {
        color: #f1f5f9;
    }
    
    [data-testid="stSidebar"] h1 {
        color: #f1f5f9;
        font-weight: 700;
    }
    
    [data-testid="stSidebar"] .stRadio label {
        color: #cbd5e1 !important;
        font-size: 1rem;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        transition: all 0.2s ease;
    }
    
    [data-testid="stSidebar"] .stRadio label:hover {
        background: rgba(59, 130, 246, 0.1);
        color: #f1f5f9 !important;
    }
    
    /* ============ TABS ============ */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: white;
        padding: 10px 20px;
        border-radius: 8px;
        font-weight: 600;
        border: 1px solid #e2e8f0;
    }
    
    .stTabs [aria-selected="true"] {
        background: #3b82f6;
        color: white;
        border-color: #3b82f6;
    }
    
    /* ============ STATUS BADGES ============ */
    .status-badge {
        display: inline-block;
        padding: 0.375rem 0.875rem;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .status-active {
        background: #dcfce7;
        color: #166534;
    }
    
    .status-paused {
        background: #fef3c7;
        color: #92400e;
    }
    
    .status-inactive {
        background: #fee2e2;
        color: #991b1b;
    }
    
    /* ============ FORMS ============ */
    .stTextInput>div>div>input,
    .stTextArea>div>div>textarea {
        border-radius: 8px;
        border: 1px solid #cbd5e1;
        transition: all 0.2s ease;
    }
    
    .stTextInput>div>div>input:focus,
    .stTextArea>div>div>textarea:focus {
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
    }
    
    /* ============ ALERTS ============ */
    .stAlert {
        border-radius: 8px;
        border-left: 4px solid;
    }
    
    /* ============ DIVIDERS ============ */
    hr {
        border: none;
        height: 1px;
        background: #e2e8f0;
        margin: 2rem 0;
    }
    
    /* ============ RESPONSIVE ============ */
    @media (max-width: 768px) {
        .main-header {
            font-size: 2rem;
        }
        
        .metric-value {
            font-size: 2rem;
        }
        
        .main .block-container {
            padding: 1rem;
        }
    }
    </style>
    """

def create_metric_card(value, label, icon="📊"):
    """Create a clean metric card."""
    return f"""
    <div class="metric-card">
        <div class="metric-icon">{icon}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-label">{label}</div>
    </div>
    """

def create_page_card(name, niche, status, created_date, description=""):
    """Create a clean page card."""
    status_class = "status-active" if status == "active" else "status-paused" if status == "paused" else "status-inactive"
    
    desc_html = f'<p style="margin: 0.25rem 0; color: #64748b; font-size: 0.9rem;">{description}</p>' if description else ""
    
    return f"""
    <div class="page-card">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div style="flex: 1;">
                <h3>{name}</h3>
                <p style="margin: 0.25rem 0; color: #3b82f6; font-weight: 500;">{niche}</p>
                {desc_html}
                <span class="status-badge {status_class}">{status.upper()}</span>
            </div>
            <div style="text-align: right; color: #94a3b8; font-size: 0.875rem; margin-left: 2rem;">
                <div style="margin-bottom: 0.25rem;">Created</div>
                <div style="font-weight: 600; color: #475569;">{created_date}</div>
            </div>
        </div>
    </div>
    """

def create_section_header(title, icon="📋"):
    """Create a clean section header."""
    return f"""
    <div class="sub-header">
        <span style="margin-right: 0.5rem;">{icon}</span>{title}
    </div>
    """
