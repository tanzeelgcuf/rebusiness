import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import time

st.set_page_config(page_title="ReBusiness Automation Dashboard", layout="wide")

st.title("🤖 ReBusiness Automation Commander")

# --- Database Connection ---
@st.cache_data(ttl=5) # Cache data for 5 seconds
def get_data():
    conn = sqlite3.connect("rebusiness_automation.db")
    
    # 1. Solicitations Overview
    solicitations = pd.read_sql_query("SELECT id, title, created_at FROM solicitations ORDER BY id DESC LIMIT 100", conn)
    
    # 2. Products Stats
    products_count = pd.read_sql_query("SELECT count(*) as count FROM products", conn).iloc[0]['count']
    detailed_products = pd.read_sql_query("SELECT count(*) as count FROM products WHERE quantity IS NOT NULL", conn).iloc[0]['count']
    
    # 3. Outreach Stats
    requests = pd.read_sql_query("SELECT status, count(*) as count FROM manufacturer_requests GROUP BY status", conn)
    
    # 4. Recent Activity
    recent_reqs = pd.read_sql_query("""
        SELECT m.name, p.product_name, r.status, r.request_date, r.response_date 
        FROM manufacturer_requests r
        JOIN manufacturers m ON r.manufacturer_id = m.id
        JOIN products p ON r.product_id = p.product_id
        ORDER BY r.request_date DESC LIMIT 10
    """, conn) if "manufacturer_requests" in pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table'", conn)['name'].values else pd.DataFrame()
    
    conn.close()
    return solicitations, products_count, detailed_products, requests, recent_reqs

# --- Layout ---

# Top Metrics
col1, col2, col3, col4 = st.columns(4)

try:
    solicitations, prod_total, prod_detailed, requests_df, recent_activity = get_data()
    
    with col1:
        st.metric("Total Solicitations", len(solicitations))
        
    with col2:
        st.metric("Products Found", prod_total)
        
    with col3:
        st.metric("Detailed Specs Extracted", prod_detailed)
        
    with col4:
        total_outreach = requests_df['count'].sum() if not requests_df.empty else 0
        st.metric("Outreach Sent", total_outreach)

    st.markdown("---")

    # Tabs
    tab1, tab2 = st.tabs(["🚀 Mission Control", "🚩 Review Queue"])

    with tab1:
        # Main Content
        c1, c2 = st.columns([2, 1])

        with c1:
            st.subheader("📢 Recent Outreach Activity")
            if not recent_activity.empty:
                st.dataframe(recent_activity, use_container_width=True)
            else:
                st.info("No outreach requests sent yet.")

        with c2:
            st.subheader("📊 Outreach Status")
            if not requests_df.empty:
                fig = px.pie(requests_df, values='count', names='status', title='Request Status Distribution')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No data to display.")

        st.markdown("---")
        st.subheader("📄 Latest Solicitations")
        st.dataframe(solicitations, use_container_width=True)

    with tab2:
        st.subheader("🚩 Flagged for Review")
        st.markdown("These solicitations have low confidence scores (< 80%) and may need manual verification.")
        
        # Fetch Flagged Items
        conn = sqlite3.connect("rebusiness_automation.db")
        flagged_df = pd.read_sql_query("SELECT id, contract_id, title, extraction_confidence, analysis_summary FROM solicitations WHERE review_status='flagged'", conn)
        conn.close()
        
        if not flagged_df.empty:
            st.dataframe(flagged_df, use_container_width=True)
            
            # Simple Review Action (Mock)
            # In a real app, this would use st.form to update the DB
            st.info(f"Found {len(flagged_df)} items needing review.")
        else:
            st.success("No items flagged for review! All systems nominal.")

except Exception as e:
    st.error(f"Error loading dashboard: {e}")
    st.info("Please ensure 'rebusiness_automation.db' exists and is populated.")

# Auto-refresh logic (optional button)
if st.button('Refresh Data'):
    st.rerun()
