"""
ingest/load_data.py
Loads, cleans and joins all Vireo support CSVs.
Returns a single merged DataFrame ready for analysis.
"""
import os
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')


def _path(fname):
    return os.path.join(DATA_DIR, fname)


def load_products():
    df = pd.read_csv(_path('products.csv'))
    # drop duplicate header row if present
    df = df[df['sku'] != 'sku'].copy()
    df['unit_cost_inr'] = pd.to_numeric(df['unit_cost_inr'], errors='coerce')
    df['retail_price_inr'] = pd.to_numeric(df['retail_price_inr'], errors='coerce')
    df['warranty_months'] = pd.to_numeric(df['warranty_months'], errors='coerce')
    return df


def load_agents():
    df = pd.read_csv(_path('agents.csv'))
    df['agent_id'] = df['agent_id'].str.strip()
    df['tier'] = pd.to_numeric(df['tier'], errors='coerce')
    # Keep latest assignment per agent (max from_date)
    df['from_date'] = pd.to_datetime(df['from_date'], errors='coerce')
    df = df.sort_values('from_date').drop_duplicates('agent_id', keep='last')
    return df[['agent_id', 'name', 'site', 'team', 'shift', 'tier']].copy()


def load_customers():
    df = pd.read_csv(_path('customers.csv'))
    df['customer_id'] = df['customer_id'].str.strip()
    df['care_plus'] = df['care_plus'].str.strip().str.upper() == 'Y'
    return df[['customer_id', 'name', 'city', 'state', 'care_plus']].copy()


def load_tickets():
    df = pd.read_csv(_path('tickets.csv'), low_memory=False)

    # Strip whitespace from string columns
    str_cols = ['ticket_id', 'status', 'channel', 'customer_id', 'order_id',
                'product_sku', 'category', 'priority', 'assigned_team',
                'agent_id', 'refund_reason_code', 'replacement_issued',
                'source_system']
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].replace('nan', '')

    # Parse timestamps
    for col in ['created_at', 'first_response_at', 'resolved_at']:
        df[col] = pd.to_datetime(df[col], errors='coerce')

    # Fix CSAT: legacy rows use 0 for "no response" (policy §8)
    df['csat_score'] = pd.to_numeric(df['csat_score'], errors='coerce')
    df.loc[df['csat_score'] == 0, 'csat_score'] = pd.NA

    # Refund amount
    df['refund_amount_inr'] = pd.to_numeric(df['refund_amount_inr'], errors='coerce').fillna(0)

    # Transfers
    df['transfers'] = pd.to_numeric(df['transfers'], errors='coerce').fillna(0).astype(int)

    # Replacement flag
    df['replacement_issued'] = df['replacement_issued'].str.upper() == 'Y'

    # ISO week of creation (for digest bucketing)
    df['week'] = df['created_at'].dt.strftime('%G-W%V')  # ISO 8601 week

    # SLA breach flag per policy §3 — vectorised
    SLA_MINUTES = {'chat': 15, 'email': 480, 'voice': 120, 'social': 240}
    df['response_minutes'] = (
        df['first_response_at'] - df['created_at']
    ).dt.total_seconds() / 60
    sla_target = df['channel'].map(SLA_MINUTES)
    df['sla_breached'] = (
        df['response_minutes'].notna()
        & sla_target.notna()
        & (df['response_minutes'] > sla_target)
    )

    # Repeat contact flag: same customer, same category, within 30 days of a prior resolution
    df = df.sort_values('created_at').reset_index(drop=True)
    df['is_repeat_contact'] = False

    # Walk tickets in chronological order; track last resolved_at per (customer, category)
    df_with_idx = df
    repeat_flags = []
    last_resolved: dict = {}  # (customer_id, category) -> last resolved_at

    for _, row in df_with_idx.iterrows():
        key = (row['customer_id'], row['category'])
        created = row['created_at']
        if pd.isna(created):
            repeat_flags.append(False)
            continue
        prior = last_resolved.get(key)
        if prior is not None:
            gap_days = (created - prior).total_seconds() / 86400
            repeat_flags.append(gap_days <= 30)
        else:
            repeat_flags.append(False)
        # Update tracker only for resolved/closed tickets with a valid resolved_at
        if row['status'] in ('resolved', 'closed') and pd.notna(row['resolved_at']):
            if prior is None or row['resolved_at'] > prior:
                last_resolved[key] = row['resolved_at']

    df['is_repeat_contact'] = repeat_flags

    return df


def load_all():
    """Returns merged DataFrame: tickets + agent info + product info."""
    tickets = load_tickets()
    agents = load_agents()
    products = load_products()
    customers = load_customers()

    # Join agent info
    tickets = tickets.merge(
        agents.rename(columns={
            'name': 'agent_name', 'site': 'agent_site',
            'team': 'agent_team', 'shift': 'agent_shift',
            'tier': 'agent_tier'
        }),
        on='agent_id', how='left'
    )

    # Join product info
    tickets = tickets.merge(
        products[['sku', 'product_name', 'family', 'unit_cost_inr', 'retail_price_inr', 'warranty_months']].rename(
            columns={'sku': 'product_sku'}
        ),
        on='product_sku', how='left'
    )

    # Join customer info
    tickets = tickets.merge(
        customers.rename(columns={'name': 'customer_name'}),
        on='customer_id', how='left'
    )

    return tickets


def get_available_weeks(df):
    """Returns sorted list of ISO weeks present in the data."""
    weeks = sorted(df['week'].dropna().unique())
    return weeks


def get_tickets_for_week(df, week_str):
    """Filter tickets created in the given ISO week string e.g. '2026-W25'."""
    return df[df['week'] == week_str].copy()


if __name__ == '__main__':
    df = load_all()
    print(f"Loaded {len(df)} tickets")
    print(f"Columns: {list(df.columns)}")
    print(f"Date range: {df['created_at'].min()} → {df['created_at'].max()}")
    print(f"Repeat contacts: {df['is_repeat_contact'].sum()} ({100*df['is_repeat_contact'].mean():.1f}%)")
    print(f"SLA breaches: {df['sla_breached'].sum()} ({100*df['sla_breached'].mean():.1f}%)")
    weeks = get_available_weeks(df)
    print(f"Weeks: {weeks[0]} → {weeks[-1]} ({len(weeks)} total)")
