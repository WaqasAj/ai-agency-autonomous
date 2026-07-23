def load_css():
    """Load custom CSS styles for the Streamlit app."""
    return """
    <style>
    /* ============ GLOBAL STYLES ============ */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
        text-align: center;
    }
    
    /* ============ METRIC CARDS ============ */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        transition: transform 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0.5rem 0;
    }
    
    .metric-label {
        font-size: 0.9rem;
        opacity: 0.9;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* ============ PAGE CARDS ============ */
    .page-card {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        border-left: 5px solid #667eea;
        margin-bottom: 1rem;
        box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    
    .page-card:hover {
        box-shadow: 0 10px 40px rgba(0,0,0,0.15);
        transform: translateY(-2px);
    }
    
    /* ============ BUTTONS ============ */
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.5rem 1.5rem;
        border-radius: 25px;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
    }
    
    /* ============ SIDEBAR ============ */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    }
    
    [data-testid="stSidebar"] .stMarkdown {
        color: white;
    }
    
    /* ============ TABS ============ */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: white;
        padding: 10px 20px;
        border-radius: 10px 10px 0 0;
        font-weight: 600;
    }
    
    /* ============ STATUS BADGES ============ */
    .status-badge {
        display: inline-block;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    
    .status-active {
        background: #10b981;
        color: white;
    }
    
    .status-paused {
        background: #f59e0b;
        color: white;
    }
    
    .status-inactive {
        background: #ef4444;
        color: white;
    }
    
    /* ============ EXPANDERS ============ */
    .streamlit-expanderHeader {
        background: white;
        border-radius: 10px;
        padding: 1rem;
        font-weight: 600;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    
    /* ============ FORMS ============ */
    .stTextInput>div>div>input,
    .stTextArea>div>div>textarea {
        border-radius: 10px;
        border: 2px solid #e5e7eb;
        transition: all 0.3s ease;
    }
    
    .stTextInput>div>div>input:focus,
    .stTextArea>div>div>textarea:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    
    /* ============ ALERTS ============ */
    .stAlert {
        border-radius: 10px;
        border-left: 5px solid;
    }
    
    /* ============ ICONS ============ */
    .icon-emoji {
        font-size: 1.5rem;
        margin-right: 0.5rem;
    }
    
    /* ============ ANIMATIONS ============ */
    @keyframes fadeIn {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .fade-in {
        animation: fadeIn 0.5s ease-out;
    }
    
    /* ============ RESPONSIVE ============ */
    @media (max-width: 768px) {
        .main-header {
            font-size: 2rem;
        }
        
        .metric-value {
            font-size: 2rem;
        }
    }
    </style>
    """

def create_metric_card(value, label, icon="📊"):
    """Create a styled metric card."""
    return f"""
    <div class="metric-card fade-in">
        <div style="font-size: 2rem;">{icon}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-label">{label}</div>
    </div>
    """

def create_page_card(name, niche, status, created_date):
    """Create a styled page card."""
    status_class = "status-active" if status == "active" else "status-paused"
    return f"""
    <div class="page-card fade-in">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h3 style="margin: 0; color: #1a1a2e;">{name}</h3>
                <p style="margin: 0.3rem 0; color: #6b7280;">{niche}</p>
                <span class="status-badge {status_class}">{status.upper()}</span>
            </div>
            <div style="text-align: right; color: #9ca3af; font-size: 0.9rem;">
                Created: {created_date}
            </div>
        </div>
    </div>
    """
