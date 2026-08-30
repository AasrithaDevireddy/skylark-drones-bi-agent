import json
import re
from typing import Any, Dict, Optional

ALLOWED = {
    "deal_count","pipeline_value","weighted_pipeline_value","won_value","won_count","lost_value","lost_count","average_deal_value","win_rate","deal_status_breakdown","deal_list","sector_pipeline","owner_pipeline","stage_pipeline",
    "order_count","order_value","billed_value","collected_value","receivable_value","completed_count","open_count","execution_breakdown","order_list","sector_financials","collection_rate","billing_gap","financial_snapshot","operational_health",
    "leadership_update","data_quality",
}

SYSTEM = """You are the query planner for a founder-facing BI agent over two monday.com boards.
Never calculate numbers yourself and never invent fields. Return JSON only.
Allowed metrics: """ + ", ".join(sorted(ALLOWED)) + """.
Allowed sources are deals, work_orders, or both.
Allowed filters: sector, active_pipeline, won_only, lost_only, deal_status, execution_status, owner_code, date_range.
Allowed date_range values: this_month, last_month, this_quarter, last_quarter, this_year, last_year.
Business rules:
- total deal count means every deal record returned by monday.com, including malformed/header-like records; do not silently drop records.
- active pipeline means Deal Status Open or On Hold.
- won means Won or Closed Won. lost means Dead, Lost, or Closed Lost.
- weighted pipeline applies High=75%, Medium=50%, Low=25% to active deals unless the user explicitly asks otherwise.
- Energy means Renewables + Powerline because the supplied source has no exact Energy label.
- operational health is a work-order summary, not merely a count.
- "show me all deals/sales" maps to deal_list; "show me all work orders" maps to order_list.
"""


def base(sources, metric, filters=None, group_by=None):
    return {"sources": sources, "metric": metric, "dimension": (group_by or [None])[0], "filters": filters or {}, "group_by": group_by or [], "needs_clarification": False, "clarifying_question": None}


def extract_filters(q):
    filters = {}
    sector_terms = ["renewable energy", "renewables", "powerline", "mining", "railways", "construction", "manufacturing", "aviation", "tender", "others", "dsp", "security and surveillance", "energy"]
    for x in sector_terms:
        if re.search(r"\b" + re.escape(x) + r"\b", q): filters["sector"] = x; break
    for x in ["this quarter","this month","this year","last quarter","last month","last year"]:
        if x in q: filters["date_range"] = x.replace(" ","_"); break
    return filters


def heuristic_plan(question: str) -> Dict[str, Any]:
    q = re.sub(r"\s+", " ", question.lower()).strip()
    f = extract_filters(q)
    if not q:
        return base(["deals","work_orders"], "leadership_update")
    if any(x in q for x in ["leadership update","leadership summary","executive summary","ceo summary","founder summary","combined summary"]):
        return base(["deals","work_orders"], "leadership_update")
    if "data quality" in q or "data quality issues" in q or "missing data" in q or "data completeness" in q:
        return base(["deals","work_orders"], "data_quality")

    dealish = any(x in q for x in ["deal", "deals", "pipeline", "sales", "opportunit", "win rate", "won deal", "lost deal", "close"])
    workish = any(x in q for x in ["work order", "work orders", "execution", "billing", "billed", "invoice", "collection", "collected", "receivable", "receivables", "outstanding", "operations", "operational"])

    if workish and not dealish or ("work order" in q):
        if "show" in q and "work order" in q: return base(["work_orders"], "order_list", f)
        if "how are" in q or "perform" in q or "operational health" in q or "key operational" in q: return base(["work_orders"], "operational_health", f)
        if "execution" in q and ("breakdown" in q or "status" in q or "by" in q): return base(["work_orders"], "execution_breakdown", f)
        if "how many" in q and "completed" in q: return base(["work_orders"], "completed_count", f)
        if "how many" in q and ("open" in q or "ongoing" in q): return base(["work_orders"], "open_count", f)
        if "how many" in q: return base(["work_orders"], "order_count", f)
        if "billed" in q and "collect" in q: return base(["work_orders"], "financial_snapshot", f)
        if "receiv" in q or "outstanding" in q: return base(["work_orders"], "sector_financials" if "sector" in q else "receivable_value", f, ["sector"] if "sector" in q else [])
        if "collect" in q and "rate" in q: return base(["work_orders"], "collection_rate", f)
        if "collect" in q: return base(["work_orders"], "collected_value", f)
        if "billed" in q and "how much" in q: return base(["work_orders"], "billed_value", f)
        if "billing gap" in q or "to be billed" in q or "unbilled" in q: return base(["work_orders"], "billing_gap", f)
        if "billed" in q and "collect" in q: return base(["work_orders"], "sector_financials" if "sector" in q else "operational_health", f, ["sector"] if "sector" in q else [])
        if "sector" in q or "by sector" in q: return base(["work_orders"], "sector_financials", f, ["sector"])
        if "order value" in q or "contract value" in q: return base(["work_orders"], "order_value", f)
        return base(["work_orders"], "operational_health", f)

    if dealish:
        if "show" in q and any(x in q for x in ["all sales","all deal","all deals","all opportunities"]): return base(["deals"], "deal_list", f)
        if "weighted" in q: return base(["deals"], "weighted_pipeline_value", {**f,"active_pipeline":True})
        if "win rate" in q: return base(["deals"], "win_rate", f)
        if "how many" in q and "won" in q: return base(["deals"], "won_count", {**f,"won_only":True})
        if "won" in q and any(x in q for x in ["value","amount","revenue"]): return base(["deals"], "won_value", {**f,"won_only":True})
        if "how many" in q and "lost" in q: return base(["deals"], "lost_count", {**f,"lost_only":True})
        if "lost" in q and any(x in q for x in ["value","amount"]): return base(["deals"], "lost_value", {**f,"lost_only":True})
        if "average" in q and "deal" in q: return base(["deals"], "average_deal_value", f)
        if "status" in q and ("breakdown" in q or "distribution" in q): return base(["deals"], "deal_status_breakdown", f)
        if "owner" in q and ("pipeline" in q or "value" in q): return base(["deals"], "owner_pipeline", {**f,"active_pipeline":True}, ["owner_code"])
        if "stage" in q and "pipeline" in q: return base(["deals"], "stage_pipeline", {**f,"active_pipeline":True}, ["deal_stage"])
        if any(x in q for x in ["largest pipeline","highest pipeline","strongest pipeline","top sectors","pipeline by sector","by sector","each sector"]): return base(["deals"], "sector_pipeline", {**f,"active_pipeline":True}, ["sector"])
        if "how many" in q or "number of" in q or "count" in q:
            if any(x in q for x in ["currently","active","in the pipeline","open"]): f["active_pipeline"] = True
            return base(["deals"], "deal_count", f)
        if any(x in q for x in ["active pipeline value","active pipeline"]): return base(["deals"], "pipeline_value", {**f,"active_pipeline":True})
        if any(x in q for x in ["total pipeline value","total pipeline","pipeline value","how much pipeline"]): return base(["deals"], "pipeline_value", f)
        return base(["deals"], "pipeline_value", {**f,"active_pipeline":True})

    return base(["deals","work_orders"], "leadership_update")


def normalize_llm_plan(plan, question):
    if not isinstance(plan, dict) or plan.get("metric") not in ALLOWED:
        return heuristic_plan(question)
    p = base(plan.get("sources") or [], plan["metric"], plan.get("filters") or {}, plan.get("group_by") or [])
    p["dimension"] = plan.get("dimension") or p["dimension"]
    q = question.lower()
    if p["metric"] in {"pipeline_value","weighted_pipeline_value","sector_pipeline","owner_pipeline","stage_pipeline"}:
        p["filters"].setdefault("active_pipeline", True)
    if p["metric"] == "deal_count" and any(x in q for x in ["currently","pipeline","open","active"]): p["filters"]["active_pipeline"] = True
    if p["metric"] == "won_count": p["filters"]["won_only"] = True
    if p["metric"] == "lost_count": p["filters"]["lost_only"] = True
    return p


def plan_query(question: str, llm=None, schema: Optional[Dict[str, Any]] = None):
    if llm is None: return heuristic_plan(question)
    prompt = SYSTEM + "\nAvailable schema:\n" + json.dumps(schema or {}, default=str) + "\nQuestion:\n" + question
    try:
        response = llm.responses.create(model=llm.model, input=prompt)
        return normalize_llm_plan(json.loads(response.output_text.strip()), question)
    except Exception:
        return heuristic_plan(question)
