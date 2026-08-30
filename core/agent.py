import os
from typing import Any, Dict
import pandas as pd
from .intent import plan_query
from .analytics import execute_plan

class LLMWrapper:
    def __init__(self, client, model): self.client, self.model = client, model
    @property
    def responses(self): return self.client.responses

class BI_Agent:
    def __init__(self, deals: pd.DataFrame, work_orders: pd.DataFrame):
        self.deals, self.work_orders = deals, work_orders
        self.llm = None
        key = os.getenv("OPENAI_API_KEY")
        if key:
            try:
                from openai import OpenAI
                self.llm = LLMWrapper(OpenAI(api_key=key), os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
            except Exception:
                self.llm = None

    def schema(self): return {"deals": list(self.deals.columns), "work_orders": list(self.work_orders.columns)}
    def ask(self, question: str) -> Dict[str, Any]:
        plan = plan_query(question, self.llm, self.schema())
        result = execute_plan(plan, self.deals, self.work_orders)
        result["answer"] = self.compose(question, result)
        return result

    @staticmethod
    def money(v):
        v = float(v or 0); a = abs(v)
        if a >= 10_000_000: return f"₹{v/10_000_000:.2f} Cr"
        if a >= 1_000_000: return f"₹{v/1_000_000:.2f}M"
        if a >= 1000: return f"₹{v/1000:.1f}K"
        return f"₹{v:,.0f}"

    def compose(self, question, r):
        s=r.get("summary",{}); m=s.get("metric") or r.get("plan",{}).get("metric"); v=s.get("value",0)
        if m=="deal_count": return f"There are **{int(v):,} deal records** in the monday.com Deals board." + (f" **{int(s.get('record_count',0)):,}** match the requested filters." if s.get('record_count')!=len(self.deals) else "")
        if m=="pipeline_value": return (f"Active pipeline value is **{self.money(v)}** across **{s.get('record_count',0):,} active deals** (Open + On Hold)." if s.get('pipeline_scope')=='active' else f"Total deal value is **{self.money(v)}** across **{s.get('record_count',0):,} deal records**.")
        if m=="weighted_pipeline_value": return f"Weighted active pipeline is **{self.money(v)}** across **{s.get('record_count',0):,} active deals**, using High=75%, Medium=50%, Low=25%."
        if m=="won_count": return f"There are **{int(v):,} won deals** (Won / Closed Won) in the selected scope."
        if m=="won_value": return f"Won deal value is **{self.money(v)}** in the selected scope."
        if m=="lost_count": return f"There are **{int(v):,} lost deals** (Dead / Lost / Closed Lost) in the selected scope."
        if m=="lost_value": return f"Lost deal value is **{self.money(v)}** in the selected scope."
        if m=="average_deal_value": return f"Average deal value is **{self.money(v)}** across **{s.get('record_count',0):,} records** with usable values."
        if m=="win_rate": return f"Win rate is **{v:.1f}%**, based on **{s.get('won',0):,} wins** out of **{s.get('decided',0):,} decided deals** (Won + Lost)."
        if m=="sector_pipeline": return f"Active pipeline totals **{self.money(s.get('total_pipeline',0))}**. The breakdown below is ranked by pipeline value."
        if m=="order_count": return f"There are **{int(v):,} work-order records** in the monday.com Work Orders board."
        if m=="completed_count": return f"**{int(v):,} work orders** are marked Completed."
        if m=="open_count": return f"**{int(v):,} work orders** are not marked Completed and are therefore treated as open/incomplete."
        if m=="order_value": return f"Total work-order value is **{self.money(v)}** using the inclusive-of-GST order value where available."
        if m=="billed_value": return f"Total billed value is **{self.money(s.get('billed_value_incl_gst',v))} incl. GST** and **{self.money(s.get('billed_value_excl_gst',0))} excl. GST**."
        if m=="collected_value": return f"Total collected value is **{self.money(v)}** (incl. GST basis)."
        if m=="receivable_value": return f"Total receivables are **{self.money(v)}**."
        if m=="collection_rate": return f"Collection rate is **{v:.1f}%** of billed value (inclusive-of-GST basis where available)."
        if m=="billing_gap": return f"Amount still to be billed is **{self.money(v)}**."
        if m=="financial_snapshot": return f"Financial snapshot: **{self.money(s.get('billed_excl_gst',0))} billed excl. GST**, **{self.money(s.get('billed_incl_gst',0))} billed incl. GST**, **{self.money(s.get('collected',0))} collected**, and **{self.money(s.get('receivables',0))} receivables**."
        if m=="operational_health": return f"Operationally, there are **{s.get('total_orders',0):,} work orders**: **{s.get('completed',0):,} completed ({s.get('completion_rate',0):.1f}%)** and **{s.get('open_orders',0):,} not completed**. Financial exposure is **{self.money(s.get('billed',0))} billed**, **{self.money(s.get('collected',0))} collected**, and **{self.money(s.get('receivables',0))} receivables**."
        if m=="execution_breakdown": return "Here is the work-order execution-status breakdown."
        if m=="sector_financials": return "Here is the work-order financial breakdown by sector, ranked by billed value."
        if m=="deal_status_breakdown": return "Here is the deal-status breakdown across all selected records."
        if m=="deal_list": return f"Here are all **{s.get('record_count',0):,} deal records** returned by monday.com."
        if m=="order_list": return f"Here are all **{s.get('record_count',0):,} work-order records** returned by monday.com."
        if m=="owner_pipeline": return "Here is active pipeline ranked by owner."
        if m=="stage_pipeline": return "Here is active pipeline ranked by deal stage."
        if m=="data_quality": return "Here is the current data-quality snapshot for both monday.com boards."
        if m=="leadership_update": return f"**Leadership snapshot:** {s.get('all_deals',0):,} total deals, **{s.get('active_deals',0):,} active**, with **{self.money(s.get('pipeline',0))} active pipeline** and **{self.money(s.get('weighted_pipeline',0))} weighted pipeline**. Operations include **{s.get('work_orders',0):,} work orders**, with **{s.get('completed_orders',0):,} completed**. Financially, **{self.money(s.get('billed',0))} billed**, **{self.money(s.get('collected',0))} collected**, and **{self.money(s.get('receivables',0))} receivables** are reported."
        return "I could not safely map that question to the available business data."
