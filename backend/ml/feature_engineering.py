"""
Feature Engineering Pipeline
Builds the 28-feature vector for XGBoost Credit Risk Model (PRD Section 4.2).

5 Categories:
- Financial (8): Current Ratio, D/E, DSCR, Interest Coverage, EBITDA%, ROE, Revenue CAGR, PAT%
- GST (6): GST vs Financial ratio, Filing regularity, GSTR mismatch, ITC ratio, Circular trading score, Reversals
- Banking (6): Bounce rate, Bounce amount, Cash withdrawal, EMI burden, Balance volatility, Window dressing
- Collateral & Management (4): Collateral coverage, Promoter character, Management quality, Litigation count
- External (4): Sector risk weight, RBI caution flag, News sentiment, Research flag count
"""

from typing import Any, Dict, List, Optional
from services.supabase_client import get_supabase
import numpy as np


# Feature names in order (must match training data column order)
FEATURE_NAMES = [
    # Financial (8)
    "current_ratio",
    "debt_to_equity",
    "dscr",
    "interest_coverage",
    "ebitda_margin",
    "roe",
    "revenue_cagr",
    "pat_margin",
    # GST (6)
    "gst_vs_financial_ratio",
    "filing_regularity",
    "gstr_mismatch",
    "itc_ratio",
    "circular_trading_score",
    "itc_reversals",
    # Banking (6)
    "bounce_rate",
    "bounce_amount_ratio",
    "cash_withdrawal_ratio",
    "emi_burden",
    "balance_volatility",
    "window_dressing_score",
    # Collateral & Management (4)
    "collateral_coverage",
    "promoter_character_score",
    "management_quality_score",
    "litigation_count",
    # External (4)
    "sector_risk_weight",
    "rbi_caution_flag",
    "news_sentiment_score",
    "research_flag_count",
]


async def build_xgboost_features(application_id: str) -> Dict[str, float]:
    """
    Build the 28-feature vector for a given application.
    Pulls data from extracted_financials, gst_monthly_data, bank_statement_data,
    field_visit_notes, research_findings, and config tables.
    """
    supabase = get_supabase()
    features = {name: 0.0 for name in FEATURE_NAMES}

    try:
        # --- Financial Features (8) ---
        financials = supabase.table("extracted_financials").select("*").eq(
            "application_id", application_id
        ).order("financial_year", desc=True).limit(3).execute()

        if financials.data:
            latest = financials.data[0]
            features["current_ratio"] = float(latest.get("current_ratio", 0) or 0)
            features["debt_to_equity"] = float(latest.get("debt_to_equity", 0) or 0)
            features["dscr"] = float(latest.get("dscr", 0) or 0)
            features["interest_coverage"] = float(latest.get("interest_coverage", 0) or 0)
            features["ebitda_margin"] = float(latest.get("ebitda_margin", 0) or 0)
            features["roe"] = float(latest.get("roe", 0) or 0)
            features["pat_margin"] = float(latest.get("pat_margin", 0) or 0)

            # Revenue CAGR (needs multiple years)
            if len(financials.data) >= 2:
                rev_latest = float(financials.data[0].get("total_revenue", 0) or 1)
                rev_oldest = float(financials.data[-1].get("total_revenue", 0) or 1)
                n_years = len(financials.data) - 1
                if rev_oldest > 0 and n_years > 0:
                    features["revenue_cagr"] = ((rev_latest / rev_oldest) ** (1 / n_years)) - 1

        # --- GST Features (6) ---
        gst_data = supabase.table("gst_monthly_data").select("*").eq(
            "application_id", application_id
        ).execute()

        if gst_data.data:
            months = gst_data.data
            total_gst_turnover = sum(float(m.get("gstr3b_turnover", 0) or 0) for m in months)
            total_gstr1 = sum(float(m.get("gstr1_turnover", 0) or 0) for m in months)
            total_itc_claimed = sum(float(m.get("itc_claimed", 0) or 0) for m in months)
            total_itc_available = sum(float(m.get("itc_available", 0) or 0) for m in months)
            filed_count = sum(1 for m in months if m.get("filing_status") == "filed")

            if financials.data:
                fin_revenue = float(financials.data[0].get("total_revenue", 0) or 1)
                features["gst_vs_financial_ratio"] = total_gst_turnover / max(fin_revenue, 1)

            features["filing_regularity"] = filed_count / max(len(months), 1)
            features["gstr_mismatch"] = abs(total_gst_turnover - total_gstr1) / max(total_gst_turnover, 1)
            features["itc_ratio"] = total_itc_claimed / max(total_itc_available, 1)
            features["itc_reversals"] = sum(float(m.get("itc_reversal", 0) or 0) for m in months)

        # Get circular trading score from ML
        risk = supabase.table("risk_scores").select("circular_trading_score").eq(
            "application_id", application_id
        ).execute()
        if risk.data:
            features["circular_trading_score"] = float(risk.data[0].get("circular_trading_score", 0) or 0)

        # --- Banking Features (6) ---
        banking = supabase.table("bank_statement_data").select("*").eq(
            "application_id", application_id
        ).execute()

        if banking.data:
            months = banking.data
            total_bounces = sum(int(m.get("bounce_count", 0) or 0) for m in months)
            total_transactions = len(months) * 30  # rough estimate
            total_bounce_amt = sum(float(m.get("bounce_amount", 0) or 0) for m in months)
            total_credits = sum(float(m.get("total_credits", 0) or 0) for m in months)
            total_cash = sum(float(m.get("cash_withdrawals", 0) or 0) for m in months)
            total_emi = sum(float(m.get("emi_outflows", 0) or 0) for m in months)
            balances = [float(m.get("closing_balance", 0) or 0) for m in months]

            features["bounce_rate"] = total_bounces / max(total_transactions, 1)
            features["bounce_amount_ratio"] = total_bounce_amt / max(total_credits, 1)
            features["cash_withdrawal_ratio"] = total_cash / max(total_credits, 1)
            features["emi_burden"] = total_emi / max(total_credits, 1)
            features["balance_volatility"] = float(np.std(balances)) / max(float(np.mean(balances)), 1) if balances else 0

            # Window dressing: check if month-end balances spike
            avg_balances = [float(m.get("average_balance", 0) or 0) for m in months]
            if avg_balances and balances:
                closing_avg_ratio = np.mean(balances) / max(np.mean(avg_balances), 1)
                features["window_dressing_score"] = max(0, closing_avg_ratio - 1.0) * 100

        # --- Collateral & Management (4) ---
        field_visit = supabase.table("field_visit_notes").select("*").eq(
            "application_id", application_id
        ).order("created_at", desc=True).limit(1).execute()

        if field_visit.data:
            fv = field_visit.data[0]
            mgmt_scores = {"strong": 0.9, "adequate": 0.6, "weak": 0.3}
            features["management_quality_score"] = mgmt_scores.get(fv.get("management_quality", "adequate"), 0.5)
            coop_scores = {"cooperative": 0.9, "evasive": 0.3, "hostile": 0.1}
            features["promoter_character_score"] = coop_scores.get(fv.get("management_cooperation", "cooperative"), 0.5)

        features["collateral_coverage"] = 1.0  # TODO: from application data
        features["litigation_count"] = 0  # Populated from research

        # --- External (4) ---
        app = supabase.table("loan_applications").select("sector").eq("id", application_id).single().execute()
        if app.data:
            bench = supabase.table("sector_benchmarks").select("risk_weight").eq("sector", app.data["sector"]).execute()
            features["sector_risk_weight"] = float(bench.data[0]["risk_weight"]) if bench.data else 1.0

        research = supabase.table("research_findings").select("*").eq("application_id", application_id).execute()
        if research.data:
            features["research_flag_count"] = len(research.data)
            rbi_flags = [r for r in research.data if r.get("source") == "rbi"]
            features["rbi_caution_flag"] = 1.0 if rbi_flags else 0.0
            # Simple sentiment: count negative findings
            high_sev = sum(1 for r in research.data if r.get("severity") in ["high", "critical"])
            features["news_sentiment_score"] = max(0, 1.0 - (high_sev * 0.2))

    except Exception as e:
        print(f"[ML] Feature engineering error: {e}")

    return features


def features_to_array(features: Dict[str, float]) -> list:
    """Convert feature dict to ordered array for model input."""
    return [features.get(name, 0.0) for name in FEATURE_NAMES]
