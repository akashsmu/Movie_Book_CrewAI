"""CSS styling for the Media Recommender application."""


def get_app_css() -> str:
    """
    Return CSS styling for the Streamlit app.
    
    Returns:
        CSS string to be injected via st.markdown()
    """
    return """
    <style>
    .main-header {
        font-size: 3rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .recommendation-card {
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #ddd;
        margin: 1rem 0;
        background-color: #f9f9f9;
    }
    .success-message {
        padding: 1rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .compromise-alert {
        padding: 1.2rem;
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        border-radius: 5px;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .compromise-alert-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #856404;
        margin-bottom: 0.5rem;
    }
    .compromise-alert-text {
        color: #856404;
        font-size: 0.95rem;
        line-height: 1.5;
    }
    </style>
    """
