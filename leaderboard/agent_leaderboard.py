"""
leaderboard/agent_leaderboard.py
Builds agent leaderboard for a given ISO week.

Rules (from email thread + support-policy.pdf):
- Tier 2 (Escalations & Warranty) EXCLUDED from main leaderboard (policy §6, Neha's email)
  → shown separately with resolution-days metric
- Count: tickets in status resolved OR closed (policy §10 — both count as attendance)
- CSAT: exclude blank/0 scores (policy §8)
- Transfers: higher = penalised (shows in separate column, not in rank)
- Rank is by tickets_closed DESC within each team (Priya wants to see it)
"""

import pandas as pd
from typing import Optional


TIER2_TEAM = 'Escalations & Warranty'
CONTACT_COST = {'chat': 210, 'email': 260, 'voice': 520, 'social': 240}
TRANSFER_COST = 305


def build_leaderboard(df: pd.DataFrame, week_str: Optional[str] = None) -> dict:
    """
    Build leaderboard for a specific week (or all time if week_str is None).
    Returns dict with keys: 'tier1', 'tier2', 'week_str', 'summary_stats'
    """
    if week_str:
        week_df = df[df['week'] == week_str].copy()
    else:
        week_df = df.copy()

    # Only resolved/closed tickets count as attendance
    closed_df = week_df[week_df['status'].isin(['resolved', 'closed'])].copy()

    # --- TIER 1 LEADERBOARD ---
    tier1_closed = closed_df[
        closed_df['agent_team'] != TIER2_TEAM
    ].copy()

    if len(tier1_closed) == 0:
        tier1_table = pd.DataFrame()
    else:
        agg = tier1_closed.groupby('agent_id').agg(
            agent_name=('agent_name', 'first'),
            team=('agent_team', 'first'),
            site=('agent_site', 'first'),
            tickets_closed=('ticket_id', 'count'),
            avg_csat=('csat_score', lambda x: round(x.dropna().mean(), 2) if len(x.dropna()) > 0 else None),
            csat_responses=('csat_score', lambda x: x.dropna().count()),
            sla_breaches=('sla_breached', 'sum'),
            repeat_contacts=('is_repeat_contact', 'sum'),
            total_transfers=('transfers', 'sum'),
        ).reset_index()

        # Rank within team by tickets_closed
        agg['team_rank'] = agg.groupby('team')['tickets_closed'].rank(
            ascending=False, method='min'
        ).astype(int)

        # Overall rank
        agg = agg.sort_values('tickets_closed', ascending=False).reset_index(drop=True)
        agg['overall_rank'] = agg.index + 1

        # SLA breach rate
        agg['sla_breach_rate'] = (
            agg['sla_breaches'] / agg['tickets_closed'] * 100
        ).round(1)

        tier1_table = agg

    # --- TIER 2 SEPARATE VIEW ---
    tier2_closed = closed_df[
        closed_df['agent_team'] == TIER2_TEAM
    ].copy()

    if len(tier2_closed) == 0:
        tier2_table = pd.DataFrame()
    else:
        # Tier 2 metric: median resolution time in days (per policy §6)
        tier2_closed['resolution_days'] = (
            tier2_closed['resolved_at'] - tier2_closed['created_at']
        ).dt.total_seconds() / 86400

        tier2_agg = tier2_closed.groupby('agent_id').agg(
            agent_name=('agent_name', 'first'),
            site=('agent_site', 'first'),
            tickets_closed=('ticket_id', 'count'),
            median_resolution_days=('resolution_days', 'median'),
            avg_csat=('csat_score', lambda x: round(x.dropna().mean(), 2) if len(x.dropna()) > 0 else None),
        ).reset_index()

        tier2_agg['median_resolution_days'] = tier2_agg['median_resolution_days'].round(1)
        tier2_table = tier2_agg.sort_values('tickets_closed', ascending=False).reset_index(drop=True)

    # --- SUMMARY STATS ---
    total_closed = len(closed_df)
    total_open = len(week_df[week_df['status'].isin(['open', 'pending'])])
    repeat_rate = (
        closed_df['is_repeat_contact'].sum() / max(total_closed, 1) * 100
    )
    breach_rate = (
        closed_df['sla_breached'].sum() / max(total_closed, 1) * 100
    )
    avg_csat_all = closed_df['csat_score'].dropna()
    avg_csat = round(float(avg_csat_all.mean()), 2) if len(avg_csat_all) > 0 else None
    refund_total = float(closed_df['refund_amount_inr'].sum())
    replacements = int(closed_df['replacement_issued'].sum())
    transfer_cost = int(closed_df['transfers'].sum()) * TRANSFER_COST
    breach_credits = int(closed_df['sla_breached'].sum()) * 350

    # Channel cost
    channel_cost = 0
    for ch, cnt in closed_df['channel'].value_counts().items():
        channel_cost += cnt * CONTACT_COST.get(ch, 290)

    summary = {
        'week_str': week_str or 'All time',
        'total_tickets': len(week_df),
        'tickets_closed': total_closed,
        'tickets_open': total_open,
        'repeat_contacts': int(closed_df['is_repeat_contact'].sum()),
        'repeat_contact_rate_pct': round(repeat_rate, 1),
        'sla_breaches': int(closed_df['sla_breached'].sum()),
        'sla_breach_rate_pct': round(breach_rate, 1),
        'avg_csat': avg_csat,
        'refund_total_inr': refund_total,
        'replacements_issued': replacements,
        'transfer_cost_inr': transfer_cost,
        'breach_credits_inr': breach_credits,
        'contact_cost_inr': channel_cost,
        'total_estimated_cost_inr': channel_cost + transfer_cost + breach_credits,
        'channel_mix': closed_df['channel'].value_counts().to_dict(),
        'category_mix': closed_df['category'].value_counts().to_dict(),
    }

    return {
        'tier1': tier1_table,
        'tier2': tier2_table,
        'week_str': week_str,
        'summary': summary,
    }


def get_weekly_trend(df: pd.DataFrame, last_n_weeks: int = 8) -> pd.DataFrame:
    """Returns week-by-week summary for sparkline/trend charts."""
    closed = df[df['status'].isin(['resolved', 'closed'])].copy()
    weeks = sorted(closed['week'].dropna().unique())[-last_n_weeks:]

    rows = []
    for w in weeks:
        w_df = closed[closed['week'] == w]
        csat = w_df['csat_score'].dropna()
        rows.append({
            'week': w,
            'tickets_closed': len(w_df),
            'repeat_rate_pct': round(w_df['is_repeat_contact'].mean() * 100, 1),
            'breach_rate_pct': round(w_df['sla_breached'].mean() * 100, 1),
            'avg_csat': round(float(csat.mean()), 2) if len(csat) > 0 else None,
        })

    return pd.DataFrame(rows)


if __name__ == '__main__':
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from ingest.load_data import load_all, get_available_weeks

    df = load_all()
    weeks = get_available_weeks(df)
    target = weeks[-2] if len(weeks) >= 2 else weeks[-1]
    print(f"Building leaderboard for {target}")

    result = build_leaderboard(df, target)
    print("\n=== TIER 1 LEADERBOARD ===")
    print(result['tier1'][['overall_rank', 'agent_name', 'team', 'tickets_closed', 'avg_csat', 'sla_breach_rate']].to_string(index=False))
    print("\n=== TIER 2 ===")
    print(result['tier2'].to_string(index=False))
    print("\n=== SUMMARY ===")
    for k, v in result['summary'].items():
        print(f"  {k}: {v}")
