"""
Streamlit components for the RFQ Review Queue — human-in-the-loop approval gate.

Integrates with the existing Streamlit dashboard. Adds three new views:
- Review Queue: pending RFQs with approve/reject actions
- Pipeline Metrics: conversion funnel and audit summary
- Audit Trail: submission log with vendor responses
"""

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from typing import List, Dict, Any, Optional
import json
from datetime import datetime

DB_PATH = "rebusiness_automation.db"


def get_db_connection():
    """Get a database connection."""
    return sqlite3.connect(DB_PATH)


def get_pending_review_rfqs() -> List[Dict]:
    """Fetch all RFQs with review_status='pending_review'."""
    conn = get_db_connection()
    try:
        query = """
            SELECT
                r.id, r.contract_id, r.rfq_type, r.rfq_content,
                r.review_status, r.validation_issues, r.created_at,
                s.title as solicitation_title
            FROM rfq_outputs r
            LEFT JOIN solicitations s ON r.contract_id = s.contract_id
            WHERE r.review_status = 'pending_review'
            ORDER BY r.created_at ASC
        """
        df = pd.read_sql_query(query, conn)
        return df.to_dict('records')
    finally:
        conn.close()


def get_rfq_counts() -> Dict[str, int]:
    """Get counts of RFQs by review status."""
    conn = get_db_connection()
    try:
        query = """
            SELECT review_status, COUNT(*) as count
            FROM rfq_outputs
            GROUP BY review_status
        """
        df = pd.read_sql_query(query, conn)
        counts = df.set_index('review_status')['count'].to_dict()
        return {
            'pending_review': counts.get('pending_review', 0),
            'approved': counts.get('approved', 0),
            'rejected': counts.get('rejected', 0),
            'auto_rejected': counts.get('auto_rejected', 0),
            'total': sum(counts.values()),
        }
    finally:
        conn.close()


def get_pipeline_metrics() -> Dict[str, Any]:
    """Get aggregated pipeline metrics."""
    conn = get_db_connection()
    try:
        # RFQ counts
        rfq_counts = get_rfq_counts()

        # Submission stats
        sub_query = """
            SELECT
                submission_status,
                response_status,
                COUNT(*) as count
            FROM submission_log
            GROUP BY submission_status, response_status
        """
        sub_df = pd.read_sql_query(sub_query, conn)

        total_submissions = sub_df['count'].sum() if not sub_df.empty else 0
        sent_count = sub_df[sub_df['submission_status'] == 'sent']['count'].sum() if not sub_df.empty else 0
        failed_count = sub_df[sub_df['submission_status'] == 'failed']['count'].sum() if not sub_df.empty else 0
        quoted_count = sub_df[sub_df['response_status'] == 'quoted']['count'].sum() if not sub_df.empty else 0
        declined_count = sub_df[sub_df['response_status'] == 'declined']['count'].sum() if not sub_df.empty else 0
        no_response_count = sub_df[sub_df['response_status'] == 'no_response']['count'].sum() if not sub_df.empty else 0

        # Recent submissions
        recent_query = """
            SELECT
                sl.id, sl.solicitation_id, sl.rfq_id, sl.vendor_name,
                sl.submitted_at, sl.submission_method, sl.submission_status,
                sl.response_received_at, sl.response_status, sl.notes
            FROM submission_log sl
            ORDER BY sl.submitted_at DESC
            LIMIT 50
        """
        recent_df = pd.read_sql_query(recent_query, conn)

        return {
            'rfq_counts': rfq_counts,
            'total_submissions': total_submissions,
            'sent_count': sent_count,
            'failed_count': failed_count,
            'quoted_count': quoted_count,
            'declined_count': declined_count,
            'no_response_count': no_response_count,
            'response_rate': (quoted_count + declined_count) / sent_count * 100 if sent_count > 0 else 0,
            'conversion_rate': quoted_count / sent_count * 100 if sent_count > 0 else 0,
            'recent_submissions': recent_df.to_dict('records'),
        }
    finally:
        conn.close()


def update_rfq_review(rfq_id: int, status: str, reviewed_by: str = "admin") -> bool:
    """Update RFQ review status in database."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE rfq_outputs
            SET review_status = ?, reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (status, reviewed_by, rfq_id))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        st.error(f"Failed to update RFQ review: {e}")
        return False
    finally:
        conn.close()


def bulk_approve_rfqs(rfq_ids: List[int], reviewed_by: str = "admin") -> int:
    """Bulk approve multiple RFQs."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        placeholders = ','.join(['?'] * len(rfq_ids))
        cursor.execute(f"""
            UPDATE rfq_outputs
            SET review_status = 'approved', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders}) AND review_status = 'pending_review'
        """, [reviewed_by] + rfq_ids)
        conn.commit()
        return cursor.rowcount
    except Exception as e:
        st.error(f"Bulk approve failed: {e}")
        return 0
    finally:
        conn.close()


def get_submission_log(limit: int = 50) -> List[Dict]:
    """Get recent submission log entries."""
    conn = get_db_connection()
    try:
        query = """
            SELECT
                sl.id, sl.solicitation_id, sl.rfq_id, sl.vendor_id, sl.vendor_name,
                sl.submitted_at, sl.submission_method, sl.submission_status,
                sl.response_received_at, sl.response_status, sl.notes
            FROM submission_log sl
            ORDER BY sl.submitted_at DESC
            LIMIT ?
        """
        df = pd.read_sql_query(query, conn, params=(limit,))
        return df.to_dict('records')
    finally:
        conn.close()


def render_review_queue():
    """Main review queue page — pending RFQs with approve/reject actions."""
    st.subheader("📋 RFQ Review Queue")
    st.markdown("Review generated RFQs before they're sent to vendors. **Stubs and low-quality RFQs are auto-rejected.**")

    # Status summary
    counts = get_rfq_counts()
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("📥 Pending Review", counts.get('pending_review', 0))
    with c2:
        st.metric("✅ Approved", counts.get('approved', 0))
    with c3:
        st.metric("❌ Rejected", counts.get('rejected', 0))
    with c4:
        st.metric("🤖 Auto-Rejected", counts.get('auto_rejected', 0))
    with c5:
        st.metric("📊 Total RFQs", counts.get('total', 0))

    st.markdown("---")

    # Fetch pending RFQs
    pending = get_pending_review_rfqs()

    if not pending:
        st.success("No RFQs pending review! All caught up.")
        return

    st.info(f"Found **{len(pending)}** RFQs awaiting review")

    # Bulk approve action
    if st.button("🟢 Bulk Approve All Pending", type="primary", use_container_width=True):
        if st.session_state.get('confirm_bulk_approve'):
            rfq_ids = [r['id'] for r in pending]
            approved = bulk_approve_rfqs(rfq_ids)
            st.success(f"Bulk approved {approved} RFQs")
            st.session_state.confirm_bulk_approve = False
            st.rerun()
        else:
            st.session_state.confirm_bulk_approve = True
            st.warning("⚠️ Click again to confirm bulk approval of ALL pending RFQs")

    st.markdown("---")

    # Render each pending RFQ
    for idx, rfq in enumerate(pending):
        contract_id = rfq.get('contract_id', 'Unknown')
        title = rfq.get('solicitation_title', rfq.get('title', 'No title'))
        rfq_type = rfq.get('rfq_type', 'UNKNOWN')
        created_at = rfq.get('created_at', '')
        validation_issues = rfq.get('validation_issues', '')
        rfq_content = rfq.get('rfq_content', '')
        rfq_id = rfq.get('id')

        # Parse validation issues
        issues = []
        if validation_issues:
            try:
                issues = json.loads(validation_issues)
            except:
                issues = [validation_issues]

        with st.expander(f"**{contract_id}** — {title[:80]}... ({rfq_type}) — *{created_at}*", expanded=idx < 3):
            # Show validation issues if any
            if issues:
                st.warning("**Validation Issues:**")
                for issue in issues:
                    st.write(f"• {issue}")
            else:
                st.success("No validation issues flagged")

            # Show RFQ content preview
            st.markdown("**RFQ Content Preview:**")
            preview = rfq_content[:2000] + ("..." if len(rfq_content) > 2000 else "")
            st.text_area("", value=preview, height=200, disabled=True, key=f"preview_{rfq_id}")

            # Action buttons
            c1, c2, c3 = st.columns([1, 1, 3])
            with c1:
                if st.button("✅ Approve", key=f"approve_{rfq_id}", type="primary", use_container_width=True):
                    if update_rfq_review(rfq_id, 'approved'):
                        st.success(f"Approved {contract_id}")
                        st.rerun()
            with c2:
                if st.button("❌ Reject", key=f"reject_{rfq_id}", use_container_width=True):
                    if update_rfq_review(rfq_id, 'rejected'):
                        st.success(f"Rejected {contract_id}")
                        st.rerun()
            with c3:
                if st.button("👁 View Full", key=f"view_{rfq_id}", use_container_width=True):
                    st.session_state[f'show_full_{rfq_id}'] = True
                    st.rerun()

            # Full content view (modal-like)
            if st.session_state.get(f'show_full_{rfq_id}', False):
                st.markdown("---")
                st.markdown(f"### Full RFQ: {contract_id}")
                st.text_area("", value=rfq_content, height=400, disabled=True, key=f"full_{rfq_id}")
                if st.button("Close", key=f"close_{rfq_id}"):
                    st.session_state[f'show_full_{rfq_id}'] = False
                    st.rerun()


def render_pipeline_metrics():
    """Pipeline metrics dashboard widget."""
    st.subheader("📈 Pipeline Metrics")

    metrics = get_pipeline_metrics()
    rfq_counts = metrics['rfq_counts']

    # Top row: RFQ funnel
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Total RFQs", rfq_counts.get('total', 0))
    with c2:
        st.metric("Pending Review", rfq_counts.get('pending_review', 0))
    with c3:
        st.metric("Approved", rfq_counts.get('approved', 0))
    with c4:
        st.metric("Rejected", rfq_counts.get('rejected', 0))
    with c5:
        st.metric("Auto-Rejected", rfq_counts.get('auto_rejected', 0))

    # Second row: Submission funnel
    st.markdown("---")
    st.markdown("**Submission Funnel**")
    s1, s2, s3, s4, s5 = st.columns(5)
    with s1:
        st.metric("Submissions Sent", metrics['sent_count'])
    with s2:
        st.metric("Failed", metrics['failed_count'])
    with s3:
        st.metric("Quotes Received", metrics['quoted_count'])
    with s4:
        st.metric("Declined", metrics['declined_count'])
    with s5:
        st.metric("No Response", metrics['no_response_count'])

    # Conversion rates
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Response Rate", f"{metrics['response_rate']:.1f}%")
    with c2:
        st.metric("Quote Conversion", f"{metrics['conversion_rate']:.1f}%")

    # Funnel chart
    if metrics['sent_count'] > 0:
        funnel_df = pd.DataFrame({
            'Stage': ['Sent', 'Responded', 'Quoted'],
            'Count': [
                metrics['sent_count'],
                metrics['quoted_count'] + metrics['declined_count'],
                metrics['quoted_count'],
            ]
        })
        fig = px.funnel(funnel_df, x='Count', y='Stage', title='Submission → Quote Funnel')
        st.plotly_chart(fig, use_container_width=True)


def render_audit_trail():
    """Audit trail view — submission log with vendor responses."""
    st.subheader("📜 Audit Trail")
    st.markdown("Complete history of RFQ submissions to vendors and their responses.")

    submissions = get_submission_log(100)

    if not submissions:
        st.info("No submissions logged yet.")
        return

    df = pd.DataFrame(submissions)
    df['submitted_at'] = pd.to_datetime(df['submitted_at'])
    df['response_received_at'] = pd.to_datetime(df['response_received_at'], errors='coerce')

    # Filters
    c1, c2, c3 = st.columns(3)
    with c1:
        status_filter = st.multiselect(
            "Submission Status",
            options=df['submission_status'].unique(),
            default=df['submission_status'].unique()
        )
    with c2:
        response_filter = st.multiselect(
            "Response Status",
            options=df['response_status'].unique(),
            default=df['response_status'].unique()
        )
    with c3:
        method_filter = st.multiselect(
            "Method",
            options=df['submission_method'].unique(),
            default=df['submission_method'].unique()
        )

    # Apply filters
    filtered = df[
        (df['submission_status'].isin(status_filter)) &
        (df['response_status'].isin(response_filter)) &
        (df['submission_method'].isin(method_filter))
    ]

    st.dataframe(
        filtered[['solicitation_id', 'rfq_id', 'vendor_name', 'submitted_at',
                  'submission_method', 'submission_status', 'response_status', 'notes']],
        use_container_width=True,
        hide_index=True
    )

    # Detail view
    if not filtered.empty:
        st.markdown("---")
        selected_id = st.selectbox("View details for submission ID:", filtered['id'].tolist())
        selected = filtered[filtered['id'] == selected_id].iloc[0]

        st.json({
            "Submission ID": int(selected['id']),
            "Solicitation ID": selected['solicitation_id'],
            "RFQ ID": int(selected['rfq_id']),
            "Vendor": selected['vendor_name'],
            "Submitted At": selected['submitted_at'].isoformat() if pd.notna(selected['submitted_at']) else None,
            "Method": selected['submission_method'],
            "Submission Status": selected['submission_status'],
            "Response Received At": selected['response_received_at'].isoformat() if pd.notna(selected['response_received_at']) else None,
            "Response Status": selected['response_status'],
            "Notes": selected['notes'],
        })


# ─────────────────────────────────────────────────────────────────────────────
# Streamlit Dashboard Integration
# ─────────────────────────────────────────────────────────────────────────────

def render_rfq_tabs():
    """Add RFQ review tabs to existing dashboard. Call from streamlit_dashboard.py"""
    tab1, tab2, tab3 = st.tabs(["📋 RFQ Review Queue", "📈 Pipeline Metrics", "📜 Audit Trail"])

    with tab1:
        render_review_queue()

    with tab2:
        render_pipeline_metrics()

    with tab3:
        render_audit_trail()


if __name__ == "__main__":
    # Standalone test
    st.set_page_config(page_title="RFQ Review Queue", layout="wide")
    st.title("🤖 RFQ Review Queue (Standalone Test)")
    render_rfq_tabs()