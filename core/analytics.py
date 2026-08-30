from typing import Any, Dict, List
import pandas as pd

PROB = {"low": 0.25, "medium": 0.50, "high": 0.75}
ACTIVE_DEAL_STATUSES = {"open", "on hold"}
WON_DEAL_STATUSES = {"won", "closed won"}
LOST_DEAL_STATUSES = {"dead", "lost", "closed lost"}
COMPLETED_WO_STATUSES = {"completed"}
OPEN_WO_STATUSES = {"ongoing", "executed until current month", "not started", "pause / struck", "partial completed", "details pending from client", "open", "in progress", "started"}
SECTOR_ALIASES = {
    "energy": ["renewables", "powerline"],
    "renewable energy": ["renewables"],
    "renewables": ["renewables"],
    "power": ["powerline"],
    "powerline": ["powerline"],
}


def _num(df, col):
    if col not in df.columns:
        return pd.Series(float("nan"), index=df.index)
    return pd.to_numeric(df[col], errors="coerce")


def _sum(df, col):
    return float(_num(df, col).fillna(0).sum())


def _money_quality(df, col):
    if col not in df.columns or not len(df):
        return {"missing": len(df), "usable": 0}
    s = _num(df, col)
    return {"missing": int(s.isna().sum()), "usable": int(s.notna().sum())}


def _display_sector(s):
    return s.astype("string").fillna("Unclassified / Missing").replace("", "Unclassified / Missing")


def _norm(s):
    return s.fillna("").astype(str).str.strip().str.lower()


def _period_anchor(df: pd.DataFrame, date_col: str) -> pd.Timestamp:
    if date_col not in df.columns:
        return pd.Timestamp.today().normalize()
    dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
    return pd.Timestamp(dates.max()).normalize() if not dates.empty else pd.Timestamp.today().normalize()


def date_mask(df, date_range, date_col):
    if not date_range or date_col not in df.columns:
        return pd.Series(True, index=df.index)
    d = _period_anchor(df, date_col)
    if date_range == "this_month":
        start, end = d.replace(day=1), d.replace(day=1) + pd.offsets.MonthBegin(1)
    elif date_range == "last_month":
        end = d.replace(day=1); start = end - pd.offsets.MonthBegin(1)
    elif date_range == "this_quarter":
        p = d.to_period("Q"); start, end = p.start_time.normalize(), (p + 1).start_time.normalize()
    elif date_range == "last_quarter":
        p = d.to_period("Q"); end, start = p.start_time.normalize(), (p - 1).start_time.normalize()
    elif date_range == "this_year":
        start, end = pd.Timestamp(d.year, 1, 1), pd.Timestamp(d.year + 1, 1, 1)
    elif date_range == "last_year":
        start, end = pd.Timestamp(d.year - 1, 1, 1), pd.Timestamp(d.year, 1, 1)
    else:
        return pd.Series(True, index=df.index)
    return pd.to_datetime(df[date_col], errors="coerce").ge(start) & pd.to_datetime(df[date_col], errors="coerce").lt(end)


def apply_filters(df: pd.DataFrame, filters: Dict[str, Any], source: str) -> pd.DataFrame:
    out = df.copy()
    sector = filters.get("sector")
    if sector and "sector" in out.columns:
        requested = str(sector).strip().lower()
        aliases = SECTOR_ALIASES.get(requested, [requested])
        normalized = _norm(out["sector"])
        out = out[normalized.isin(aliases)]
    if filters.get("active_pipeline") and source == "deals" and "deal_status" in out.columns:
        out = out[_norm(out["deal_status"]).isin(ACTIVE_DEAL_STATUSES)]
    if filters.get("won_only") and source == "deals" and "deal_status" in out.columns:
        out = out[_norm(out["deal_status"]).isin(WON_DEAL_STATUSES)]
    if filters.get("lost_only") and source == "deals" and "deal_status" in out.columns:
        out = out[_norm(out["deal_status"]).isin(LOST_DEAL_STATUSES)]
    if filters.get("deal_status") and "deal_status" in out.columns:
        out = out[_norm(out["deal_status"]) == str(filters["deal_status"]).lower()]
    if filters.get("execution_status") and "execution_status" in out.columns:
        out = out[_norm(out["execution_status"]) == str(filters["execution_status"]).lower()]
    if filters.get("owner_code") and "owner_code" in out.columns:
        out = out[_norm(out["owner_code"]) == str(filters["owner_code"]).lower()]
    if filters.get("date_range"):
        date_col = "tentative_close_date" if source == "deals" else "probable_start_date"
        out = out[date_mask(out, filters["date_range"], date_col)]
    return out


def _status_breakdown(df, col, name):
    if col not in df.columns:
        return []
    return df.assign(_status=_norm(df[col]).replace("", "missing")).groupby("_status").size().reset_index(name="records").sort_values("records", ascending=False).rename(columns={"_status": name}).to_dict("records")


def _quality_warnings(deals, selected, result):
    if "deal_value" in deals.columns and len(deals):
        miss = int(_num(deals, "deal_value").isna().sum())
        if miss:
            selected_missing = int(_num(selected, "deal_value").isna().sum())
            result["warnings"].append(f"Data quality: {miss:,} of {len(deals):,} deal records ({miss/len(deals):.0%}) lack a usable deal value. The requested value metric excludes {selected_missing:,} selected records with missing values.")
    if "closure_probability" in deals.columns:
        unknown = int((~_norm(selected.get("closure_probability", pd.Series(index=selected.index))).isin(PROB)).sum()) if len(selected) else 0
        if unknown:
            result["warnings"].append(f"Data quality: {unknown:,} selected active deal(s) have no recognized closure probability, so their weighted contribution is treated as zero and is excluded from weighted-value coverage.")


def _period_note(df, date_range, source, result):
    if date_range:
        col = "tentative_close_date" if source == "deals" else "probable_start_date"
        if col in df.columns:
            anchor = _period_anchor(df, col)
            result["warnings"].append(f"Period interpretation: '{date_range.replace('_',' ')}' is anchored to the latest available {source.replace('_',' ')} date ({anchor.date()}) because the monday.com data is a historical snapshot.")


def execute_plan(plan: Dict[str, Any], deals: pd.DataFrame, work_orders: pd.DataFrame) -> Dict[str, Any]:
    sources = plan.get("sources", [])
    metric = plan.get("metric")
    filters = plan.get("filters", {}) or {}
    result = {"plan": plan, "rows": [], "summary": {}, "warnings": []}
    dfs = {}
    if "deals" in sources: dfs["deals"] = apply_filters(deals, filters, "deals")
    if "work_orders" in sources: dfs["work_orders"] = apply_filters(work_orders, filters, "work_orders")

    if filters.get("sector", "").lower() == "energy" and "deals" in sources:
        result["warnings"].append("Data interpretation: the source has no exact 'Energy' sector label. 'Energy' is interpreted as Renewables + Powerline.")

    if metric in {"deal_count", "pipeline_value", "weighted_pipeline_value", "won_value", "won_count", "lost_value", "lost_count", "average_deal_value", "win_rate", "deal_status_breakdown", "deal_list", "sector_pipeline", "owner_pipeline", "stage_pipeline"}:
        df = dfs.get("deals", deals)
        if metric == "deal_count": value = len(df)
        elif metric == "pipeline_value": value = _sum(df, "deal_value")
        elif metric == "weighted_pipeline_value":
            p = _norm(df.get("closure_probability", pd.Series(index=df.index))).map(PROB).fillna(0)
            value = float((_num(df, "deal_value").fillna(0) * p).sum())
        elif metric == "won_value":
            won = df[_norm(df.get("deal_status", pd.Series(index=df.index))).isin(WON_DEAL_STATUSES)]
            value = _sum(won, "deal_value")
        elif metric == "won_count": value = int(_norm(df.get("deal_status", pd.Series(index=df.index))).isin(WON_DEAL_STATUSES).sum())
        elif metric == "lost_value":
            lost = df[_norm(df.get("deal_status", pd.Series(index=df.index))).isin(LOST_DEAL_STATUSES)]
            value = _sum(lost, "deal_value")
        elif metric == "lost_count": value = int(_norm(df.get("deal_status", pd.Series(index=df.index))).isin(LOST_DEAL_STATUSES).sum())
        elif metric == "average_deal_value":
            s = _num(df, "deal_value").dropna(); value = float(s.mean()) if len(s) else 0.0
        elif metric == "win_rate":
            statuses = _norm(df.get("deal_status", pd.Series(index=df.index)))
            decided = statuses.isin(WON_DEAL_STATUSES | LOST_DEAL_STATUSES)
            wins = statuses.isin(WON_DEAL_STATUSES).sum(); value = float(wins / decided.sum() * 100) if decided.sum() else 0.0
            result["summary"] = {"metric": metric, "value": value, "won": int(wins), "decided": int(decided.sum()), "record_count": len(df)}
            result["rows"] = _status_breakdown(df, "deal_status", "status")
            _quality_warnings(deals, df, result)
            return result
        elif metric == "deal_status_breakdown":
            result["rows"] = _status_breakdown(df, "deal_status", "status")
            result["summary"] = {"metric": metric, "record_count": len(df)}
            return result
        elif metric == "deal_list":
            cols = [c for c in ["monday_item_name", "deal_name", "owner_code", "client_code", "deal_status", "deal_value", "closure_probability", "deal_stage", "sector", "tentative_close_date"] if c in df.columns]
            result["rows"] = df[cols].copy().fillna("").to_dict("records")
            result["summary"] = {"metric": metric, "record_count": len(df)}
            _quality_warnings(deals, df, result)
            return result
        if metric not in {"win_rate", "deal_status_breakdown", "deal_list", "sector_pipeline", "owner_pipeline", "stage_pipeline"}:
            result["summary"] = {"metric": metric, "value": value, "record_count": len(df)}
            if metric in {"pipeline_value", "weighted_pipeline_value", "deal_count"} and filters.get("active_pipeline"):
                result["summary"]["pipeline_scope"] = "active"
            if filters.get("date_range"): _period_note(deals, filters["date_range"], "deals", result)
            _quality_warnings(deals, df, result)

        if metric == "sector_pipeline":
            tmp = df.copy(); tmp["sector"] = _display_sector(tmp["sector"]) if "sector" in tmp.columns else "Unclassified / Missing"; tmp["pipeline"] = _num(tmp, "deal_value").fillna(0)
            result["rows"] = tmp.groupby("sector", dropna=False).agg(deals=("monday_item_id", "count"), pipeline=("pipeline", "sum")).reset_index().sort_values("pipeline", ascending=False).to_dict("records")
            result["summary"] = {"metric": metric, "total_pipeline": _sum(df, "deal_value"), "record_count": len(df), "pipeline_scope": "active" if filters.get("active_pipeline") else "all"}
            _quality_warnings(deals, df, result)
        elif metric in {"owner_pipeline", "stage_pipeline"}:
            g = "owner_code" if metric == "owner_pipeline" else "deal_stage"
            if g in df.columns:
                tmp = df.copy(); tmp["value"] = _num(tmp, "deal_value").fillna(0)
                result["rows"] = tmp.groupby(g, dropna=False).agg(records=("monday_item_id", "count"), pipeline=("value", "sum")).reset_index().sort_values("pipeline", ascending=False).fillna({g:"Unclassified / Missing"}).to_dict("records")
        return result

    if metric in {"order_count", "order_value", "billed_value", "collected_value", "receivable_value", "completed_count", "open_count", "execution_breakdown", "order_list", "sector_financials", "collection_rate", "billing_gap", "financial_snapshot"}:
        df = dfs.get("work_orders", work_orders)
        status = _norm(df.get("execution_status", pd.Series(index=df.index))).replace("", "missing")
        if metric == "order_count": value = len(df)
        elif metric == "order_value": value = _sum(df, "invoice_amount_incl_gst") or _sum(df, "invoice_amount_excl_gst")
        elif metric == "billed_value": value = _sum(df, "billed_value_incl_gst") or _sum(df, "billed_value_excl_gst")
        elif metric == "collected_value": value = _sum(df, "collected_amount")
        elif metric == "receivable_value": value = _sum(df, "amount_receivable")
        elif metric == "completed_count": value = int(status.isin(COMPLETED_WO_STATUSES).sum())
        elif metric == "open_count": value = int((~status.isin(COMPLETED_WO_STATUSES)).sum())
        elif metric == "execution_breakdown":
            result["rows"] = _status_breakdown(df, "execution_status", "execution_status"); result["summary"] = {"metric": metric, "record_count": len(df)}; return result
        elif metric == "order_list":
            cols = [c for c in ["monday_item_name", "deal_name", "client_code", "execution_status", "sector", "invoice_amount_incl_gst", "billed_value_incl_gst", "collected_amount", "amount_receivable", "probable_start_date", "probable_end_date"] if c in df.columns]
            result["rows"] = df[cols].copy().fillna("").to_dict("records"); result["summary"] = {"metric": metric, "record_count": len(df)}; return result
        elif metric == "sector_financials":
            tmp=df.copy(); tmp["sector"]=_display_sector(tmp["sector"]); result["rows"]=tmp.groupby("sector").agg(work_orders=("monday_item_id","count"), billed=("billed_value_incl_gst","sum"), collected=("collected_amount","sum"), receivables=("amount_receivable","sum")).reset_index().sort_values("billed",ascending=False).to_dict("records"); result["summary"]={"metric":metric,"record_count":len(df)}; return result
        elif metric == "collection_rate":
            billed = _sum(df, "billed_value_incl_gst")
            collected = _sum(df, "collected_amount")
            value = collected / billed * 100 if billed else 0.0
            result["summary"]={"metric":metric,"value":value,"billed":billed,"collected":collected,"record_count":len(df)}
            return result
        elif metric == "billing_gap":
            to_bill = _sum(df, "amount_to_be_billed_incl_gst") or _sum(df, "amount_to_be_billed_excl_gst")
            result["summary"]={"metric":metric,"value":to_bill,"record_count":len(df)}
            return result
        elif metric == "financial_snapshot":
            result["summary"]={"metric":metric,"billed_excl_gst":_sum(df,"billed_value_excl_gst"),"billed_incl_gst":_sum(df,"billed_value_incl_gst"),"collected":_sum(df,"collected_amount"),"receivables":_sum(df,"amount_receivable"),"record_count":len(df)}
            return result
        if metric not in {"execution_breakdown", "order_list", "sector_financials", "collection_rate", "billing_gap", "financial_snapshot"}:
            result["summary"] = {"metric": metric, "value": value, "record_count": len(df)}
        return result

    if metric == "operational_health":
        df = dfs.get("work_orders", work_orders)
        status = _norm(df.get("execution_status", pd.Series(index=df.index))).replace("", "missing")
        completed = int(status.isin(COMPLETED_WO_STATUSES).sum())
        result["summary"] = {
            "metric": metric, "total_orders": len(df), "completed": completed,
            "open_orders": len(df)-completed, "completion_rate": completed/len(df)*100 if len(df) else 0.0,
            "not_started": int(status.eq("not started").sum()), "in_progress": int(status.isin({"ongoing","in progress","started"}).sum()),
            "missing_status": int(status.eq("missing").sum()), "billed": _sum(df,"billed_value_incl_gst") or _sum(df,"billed_value_excl_gst"),
            "collected": _sum(df,"collected_amount"), "receivables": _sum(df,"amount_receivable"),
        }
        result["rows"] = _status_breakdown(df,"execution_status","execution_status")
        if result["summary"]["missing_status"]: result["warnings"].append(f"Data quality: {result['summary']['missing_status']:,} of {len(df):,} work orders have no execution status.")
        return result

    if metric == "leadership_update":
        d_active = apply_filters(deals, {"active_pipeline": True}, "deals")
        w = work_orders
        probs = _norm(d_active.get("closure_probability", pd.Series(index=d_active.index))).map(PROB).fillna(0)
        result["summary"] = {
            "metric": metric, "all_deals": len(deals), "active_deals": len(d_active), "pipeline": _sum(d_active,"deal_value"),
            "weighted_pipeline": float((_num(d_active,"deal_value").fillna(0)*probs).sum()), "won_deals": int(_norm(deals.get("deal_status",pd.Series(index=deals.index))).isin(WON_DEAL_STATUSES).sum()),
            "lost_deals": int(_norm(deals.get("deal_status",pd.Series(index=deals.index))).isin(LOST_DEAL_STATUSES).sum()),
            "work_orders": len(w), "completed_orders": int(_norm(w.get("execution_status",pd.Series(index=w.index))).isin(COMPLETED_WO_STATUSES).sum()),
            "billed": _sum(w,"billed_value_incl_gst") or _sum(w,"billed_value_excl_gst"), "collected": _sum(w,"collected_amount"), "receivables": _sum(w,"amount_receivable"),
        }
        _quality_warnings(deals,d_active,result)
        result["warnings"].append("Leadership snapshot combines the live monday.com deals and work-order boards. Monetary figures remain source-system/masked values.")
        return result

    if metric == "data_quality":
        result["summary"] = {
            "metric": metric, "deal_records": len(deals), "deal_value_missing": int(_num(deals,"deal_value").isna().sum()),
            "deal_status_missing": int(_norm(deals.get("deal_status",pd.Series(index=deals.index))).isin({"","missing"}).sum()),
            "work_order_records": len(work_orders), "wo_execution_status_missing": int(_norm(work_orders.get("execution_status",pd.Series(index=work_orders.index))).eq("").sum()),
            "wo_billed_missing": int(_num(work_orders,"billed_value_incl_gst").isna().sum()) if "billed_value_incl_gst" in work_orders else int(_num(work_orders,"billed_value_excl_gst").isna().sum()),
        }
        return result

    result["warnings"].append(f"I could not safely map this question to a supported business metric. Try a pipeline, deal, work-order, billing, collection, receivables, sector, or leadership question.")
    return result
