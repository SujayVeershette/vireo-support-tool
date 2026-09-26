"""
app.py — Vireo Audio Support Intelligence Tool
Streamlit app with two views:
  1. Weekly Digest (AI-generated, Groq gpt-oss-120b)
  2. Agent Leaderboard (Tier 1, per-team)

Run: streamlit run app.py
"""
import os
import sys
import json
import streamlit as st
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))
from ingest.load_data import load_all, get_available_weeks, get_tickets_for_week
from digest.weekly_digest import generate_digest
from leaderboard.agent_leaderboard import build_leaderboard, get_weekly_trend

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Vireo Audio · Support Intelligence",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: #1e1e2e;
        border: 1px solid #313244;
        border-radius: 10px;
        padding: 16px 20px;
        text-align: center;
    }
    .metric-value { font-size: 2rem; font-weight: 700; color: #cdd6f4; }
    .metric-label { font-size: 0.8rem; color: #9399b2; text-transform: uppercase; letter-spacing: 0.05em; }
    .theme-badge-high { background: #f38ba8; color: #1e1e2e; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
    .theme-badge-medium { background: #fab387; color: #1e1e2e; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
    .theme-badge-low { background: #a6e3a1; color: #1e1e2e; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
    .alert-box { background: #45475a; border-left: 4px solid #f38ba8; padding: 12px 16px; border-radius: 4px; margin: 8px 0; }
    .info-box { background: #313244; border-left: 4px solid #89b4fa; padding: 12px 16px; border-radius: 4px; margin: 8px 0; }
    .rank-1 { color: #f9e2af; font-weight: 700; }
    .rank-2 { color: #cdd6f4; font-weight: 600; }
    .rank-3 { color: #fab387; font-weight: 600; }
    h1, h2, h3 { color: #cdd6f4; }
</style>
""", unsafe_allow_html=True)

# ── Data loading (cached) ─────────────────────────────────────────────────────
@st.cache_data(show_spinner="Loading Vireo support data…")
def get_data():
    df = load_all()
    weeks = get_available_weeks(df)
    return df, weeks


@st.cache_data(show_spinner=False)
def get_leaderboard(_df, week_str):
    """Cached wrapper — underscore prefix tells Streamlit not to hash the df."""
    return build_leaderboard(_df, week_str)


@st.cache_data(show_spinner=False)
def get_trend(_df, n_weeks=8):
    return get_weekly_trend(_df, last_n_weeks=n_weeks)


df, weeks = get_data()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://via.placeholder.com/200x50/1e1e2e/cdd6f4?text=🎧+Vireo+Audio", width='stretch')
    st.markdown("## Support Intelligence")
    st.markdown("---")

    view = st.radio("View", ["📋 Weekly Digest", "🏆 Agent Leaderboard"], label_visibility="collapsed")

    st.markdown("### Select Week")
    # Default to last full week in dataset (weeks[-2] avoids partial last week)
    default_idx = max(0, len(weeks) - 2)
    selected_week = st.selectbox(
        "ISO Week",
        options=weeks,
        index=default_idx,
        format_func=lambda w: w,
        label_visibility="collapsed",
    )

    week_df = get_tickets_for_week(df, selected_week)
    st.markdown(f"**{len(week_df)} tickets** in `{selected_week}`")

    st.markdown("---")
    st.markdown("### Dataset")
    st.markdown(f"- **{len(df):,}** total tickets")
    st.markdown(f"- **{len(weeks)}** weeks: {weeks[0]} → {weeks[-1]}")
    st.markdown(f"- **{df['agent_id'].nunique()}** agents")

    if not os.getenv("GROQ_API_KEY"):
        st.error("⚠️ GROQ_API_KEY not set. Digest generation disabled.")

# ── Helper: metric card ───────────────────────────────────────────────────────
def metric_card(label, value, delta=None, delta_label=""):
    delta_html = f'<div style="font-size:0.75rem;color:{"#f38ba8" if (delta and delta > 0) else "#a6e3a1"}">{delta_label}</div>' if delta is not None else ''
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{value}</div>
        <div class="metric-label">{label}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# VIEW 1: WEEKLY DIGEST
# ════════════════════════════════════════════════════════════════════════════
if "Digest" in view:
    st.title(f"🎧 Weekly Support Digest — {selected_week}")

    # ── Week-level stats (computed, no AI needed) ─────────────────────────
    closed_df = week_df[week_df['status'].isin(['resolved', 'closed'])]
    total = len(week_df)
    closed = len(closed_df)
    repeat = int(closed_df['is_repeat_contact'].sum())
    breaches = int(closed_df['sla_breached'].sum())
    csat_vals = closed_df['csat_score'].dropna()
    avg_csat = round(float(csat_vals.mean()), 2) if len(csat_vals) > 0 else None
    refunds = float(closed_df['refund_amount_inr'].sum())

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        metric_card("Total Tickets", total)
    with c2:
        metric_card("Resolved/Closed", closed)
    with c3:
        repeat_pct = f"{100*repeat/max(closed,1):.1f}%"
        metric_card("Repeat Contacts", f"{repeat} ({repeat_pct})", delta=repeat if repeat > 0 else None, delta_label="⬆ needs FCR focus")
    with c4:
        metric_card("SLA Breaches", breaches)
    with c5:
        metric_card("Avg CSAT", f"{avg_csat:.2f}" if avg_csat else "—")

    st.markdown("---")

    # ── Category breakdown ────────────────────────────────────────────────
    col_left, col_right = st.columns([1.2, 1])

    with col_left:
        st.subheader("Ticket Volume by Category")
        cat_counts = week_df['category'].value_counts().reset_index()
        cat_counts.columns = ['Category', 'Count']
        fig = px.bar(
            cat_counts, x='Count', y='Category', orientation='h',
            color='Count', color_continuous_scale='Blues',
            template='plotly_dark', height=350,
        )
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig, width='stretch')

    with col_right:
        st.subheader("Channel Mix")
        ch_counts = week_df['channel'].value_counts().reset_index()
        ch_counts.columns = ['Channel', 'Count']
        fig2 = px.pie(
            ch_counts, values='Count', names='Channel',
            template='plotly_dark', hole=0.5, height=350,
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        fig2.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig2, width='stretch')

    # ── Repeat contacts by category ──────────────────────────────────────
    repeat_by_cat = closed_df[closed_df['is_repeat_contact']]['category'].value_counts()
    if len(repeat_by_cat) > 0:
        st.subheader("🔁 Repeat Contacts by Category")
        st.caption("Same customer, same category, ≤30 days after prior resolution.")
        repeat_df = repeat_by_cat.reset_index()
        repeat_df.columns = ['Category', 'Repeat Contacts']
        fig3 = px.bar(
            repeat_df, x='Category', y='Repeat Contacts',
            color='Repeat Contacts', color_continuous_scale='Oranges',
            template='plotly_dark', height=280,
        )
        fig3.update_layout(margin=dict(l=0, r=0, t=10, b=0), coloraxis_showscale=False)
        st.plotly_chart(fig3, width='stretch')

    st.markdown("---")

    # ── AI Digest Generation ─────────────────────────────────────────────
    st.subheader("🤖 AI-Generated Digest")

    if not os.getenv("GROQ_API_KEY"):
        st.warning("Set GROQ_API_KEY in .env to enable AI digest generation.")
    else:
        digest_key = f"digest_{selected_week}"
        stats_key = f"stats_{selected_week}"

        col_btn, col_cost = st.columns([1, 3])
        with col_btn:
            run_digest = st.button("▶ Generate Digest", type="primary", width='stretch')

        if run_digest:
            with st.spinner(f"Analysing {len(week_df)} tickets with gpt-oss-120b…"):
                try:
                    digest, usage_stats = generate_digest(week_df, selected_week)
                    st.session_state[digest_key] = digest
                    st.session_state[stats_key] = usage_stats
                except Exception as e:
                    st.error(f"Digest generation failed: {e}")
                    digest = None

        digest = st.session_state.get(digest_key)
        usage_stats = st.session_state.get(stats_key, {})

        if usage_stats:
            with col_cost:
                cost_usd = usage_stats.get('cost_usd', 0)
                cost_inr = usage_stats.get('cost_inr', 0)
                st.caption(
                    f"Run cost: **${cost_usd:.4f}** (~₹{cost_inr:.2f}) · "
                    f"{usage_stats.get('input_tokens',0):,} in + {usage_stats.get('output_tokens',0):,} out tokens"
                )

        if digest:
            if 'error' in digest:
                st.error(f"Digest error: {digest['error']}")
                if 'raw_response' in digest:
                    with st.expander("Raw LLM response"):
                        st.code(digest['raw_response'])
            else:
                # Week summary
                st.markdown(f"### Summary\n{digest.get('week_summary', '')}")

                # Alerts row
                alert_cols = st.columns(2)
                with alert_cols[0]:
                    rc = digest.get('repeat_contact_alert', {})
                    if rc.get('flagged'):
                        st.markdown(f'<div class="alert-box">🔁 <strong>Repeat Contact Alert</strong><br>{rc.get("summary","")}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="info-box">✅ <strong>Repeat Contacts</strong>: No unusual spike detected.</div>', unsafe_allow_html=True)

                with alert_cols[1]:
                    sla = digest.get('sla_breach_alert', {})
                    if sla.get('flagged'):
                        channels = ', '.join(sla.get('channels_affected', []))
                        st.markdown(f'<div class="alert-box">🔴 <strong>SLA Breach Alert</strong> ({channels})<br>{sla.get("summary","")}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="info-box">✅ <strong>SLA</strong>: Within normal range.</div>', unsafe_allow_html=True)

                # Top themes
                st.markdown("### Top Complaint Themes")
                themes = digest.get('top_themes', [])
                for i, theme in enumerate(themes):
                    severity = theme.get('severity', 'medium')
                    badge_class = f"theme-badge-{severity}"
                    with st.expander(
                        f"**{i+1}. {theme.get('theme', 'Unknown')}** — ~{theme.get('ticket_count', '?')} tickets",
                        expanded=(i < 3),
                    ):
                        st.markdown(
                            f'<span class="{badge_class}">{severity.upper()}</span>',
                            unsafe_allow_html=True
                        )
                        st.markdown(f"**What's happening:** {theme.get('description', '')}")
                        example = theme.get('example_verbatim', '')
                        if example:
                            st.markdown(f"> *\"{example}\"*")

                # Product signals
                signals = digest.get('product_signals', [])
                if signals:
                    st.markdown("### 📦 Product Signals")
                    for sig in signals:
                        st.markdown(f"- **{sig.get('sku','')}**: {sig.get('signal','')}")

                # Recommended action
                rec = digest.get('recommended_action', '')
                if rec:
                    st.markdown("### ⚡ Recommended Action This Week")
                    st.info(rec)

                # Raw JSON expander
                with st.expander("Raw JSON response"):
                    st.json(digest)


# ════════════════════════════════════════════════════════════════════════════
# VIEW 2: AGENT LEADERBOARD
# ════════════════════════════════════════════════════════════════════════════
else:
    st.title(f"🏆 Agent Leaderboard — {selected_week}")
    st.caption(
        "Tier 1 agents only, ranked by tickets resolved/closed. "
        "Tier 2 (Escalations & Warranty) shown separately with resolution-day metric. "
        "Policy: §6 of Vireo Support Operating Policy."
    )

    result = get_leaderboard(df, selected_week)
    summary = result['summary']
    tier1 = result['tier1']
    tier2 = result['tier2']

    # ── Week summary metrics ───────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        metric_card("Tickets Closed", summary['tickets_closed'])
    with c2:
        metric_card("Open/Pending", summary['tickets_open'])
    with c3:
        metric_card("Repeat Rate", f"{summary['repeat_contact_rate_pct']}%",
                    delta=1 if summary['repeat_contact_rate_pct'] > 15 else None,
                    delta_label="above 15% threshold")
    with c4:
        metric_card("SLA Breach Rate", f"{summary['sla_breach_rate_pct']}%")
    with c5:
        metric_card("Avg CSAT", f"{summary['avg_csat']:.2f}" if summary['avg_csat'] else "—")

    st.markdown("---")

    # ── Tier 1 Leaderboard ────────────────────────────────────────────────
    st.subheader("Tier 1 Agents")

    if tier1 is not None and len(tier1) > 0:
        # Team filter
        teams_available = ['All Teams'] + sorted(tier1['team'].unique().tolist())
        team_filter = st.selectbox("Filter by Team", teams_available)

        display_t1 = tier1.copy()
        if team_filter != 'All Teams':
            display_t1 = display_t1[display_t1['team'] == team_filter]

        # Format for display
        display_cols = {
            'overall_rank': 'Rank',
            'agent_name': 'Agent',
            'team': 'Team',
            'site': 'Site',
            'tickets_closed': 'Tickets Closed',
            'avg_csat': 'Avg CSAT',
            'csat_responses': 'CSAT Responses',
            'sla_breach_rate': 'Breach Rate %',
            'repeat_contacts': 'Repeat Contacts',
            'total_transfers': 'Transfers',
        }

        show_df = display_t1[list(display_cols.keys())].rename(columns=display_cols)

        # Colour tickets_closed column
        def highlight_top(row):
            rank = row.get('Rank', 99)
            if rank == 1:
                return ['background-color: #2a2a3e; font-weight: bold'] * len(row)
            elif rank <= 3:
                return ['background-color: #1e2030'] * len(row)
            return [''] * len(row)

        styled = show_df.style.apply(highlight_top, axis=1).format({
            'Avg CSAT': lambda x: f"{x:.2f}" if pd.notna(x) else "—",
            'Breach Rate %': lambda x: f"{x:.1f}%",
        })

        st.dataframe(styled, width='stretch', height=500)

        # ── Bar chart: tickets closed per agent ───────────────────────────
        st.subheader("Tickets Closed — Visual")
        top_n = display_t1.head(20)
        fig = px.bar(
            top_n.sort_values('tickets_closed'),
            x='tickets_closed', y='agent_name',
            color='team', orientation='h',
            template='plotly_dark', height=max(400, len(top_n) * 25),
            labels={'tickets_closed': 'Tickets Closed', 'agent_name': 'Agent', 'team': 'Team'},
        )
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, width='stretch')

    else:
        st.info("No Tier 1 agent data for this week.")

    # ── Tier 2 (separate, no volume rank) ────────────────────────────────
    st.markdown("---")
    st.subheader("Escalations & Warranty Team (Tier 2)")
    st.caption("Measured by median resolution days, not ticket count. Not ranked against Tier 1.")

    if tier2 is not None and len(tier2) > 0:
        show_t2 = tier2[['agent_name', 'site', 'tickets_closed', 'median_resolution_days', 'avg_csat']].copy()
        show_t2 = show_t2.rename(columns={
            'agent_name': 'Agent', 'site': 'Site',
            'tickets_closed': 'Cases Closed',
            'median_resolution_days': 'Median Resolution (days)',
            'avg_csat': 'Avg CSAT',
        })
        st.dataframe(show_t2.style.format({
            'Avg CSAT': lambda x: f"{x:.2f}" if pd.notna(x) else "—",
            'Median Resolution (days)': lambda x: f"{x:.1f}d",
        }), width='stretch')
    else:
        st.info("No Tier 2 data for this week.")

    # ── 8-week trend ──────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📈 8-Week Trend")
    trend_df = get_trend(df, n_weeks=8)

    if len(trend_df) > 0:
        tc1, tc2 = st.columns(2)
        with tc1:
            fig_t = px.line(
                trend_df, x='week', y='tickets_closed',
                template='plotly_dark', markers=True,
                title='Tickets Closed per Week',
                labels={'tickets_closed': 'Tickets', 'week': 'Week'},
            )
            fig_t.update_layout(margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_t, width='stretch')

        with tc2:
            fig_r = px.line(
                trend_df, x='week', y=['repeat_rate_pct', 'breach_rate_pct'],
                template='plotly_dark', markers=True,
                title='Repeat Contact & SLA Breach Rate (%)',
                labels={'value': '%', 'week': 'Week', 'variable': 'Metric'},
            )
            fig_r.update_layout(margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_r, width='stretch')

    # ── Cost summary box ──────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("💰 Week Cost Estimate")
    cost_cols = st.columns(4)
    with cost_cols[0]:
        metric_card("Contact Cost", f"₹{summary['contact_cost_inr']:,.0f}")
    with cost_cols[1]:
        metric_card("Transfer Cost", f"₹{summary['transfer_cost_inr']:,.0f}")
    with cost_cols[2]:
        metric_card("Breach Credits", f"₹{summary['breach_credits_inr']:,.0f}")
    with cost_cols[3]:
        metric_card("Total Est. Cost", f"₹{summary['total_estimated_cost_inr']:,.0f}")

    st.caption(
        "Contact cost: Rs 210 chat / Rs 260 email / Rs 520 voice / Rs 240 social (policy §4). "
        "Transfer cost: Rs 305 per transfer event. Breach credits: Rs 350 per SLA miss. "
        "Excludes refunds and replacement logistics."
    )
