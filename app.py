import os
import streamlit as st
from dotenv import load_dotenv
from core.monday_client import MondayClient, MondayAPIError
from core.normalizer import items_to_dataframe
from core.agent import BI_Agent

load_dotenv()
st.set_page_config(page_title="Skylark Drones BI Agent", page_icon="🚁", layout="wide")

def cfg(name, default=""):
    try:
        v=st.secrets.get(name,"")
        if v: return str(v)
    except Exception: pass
    return os.getenv(name,default)

def load_live():
    token=cfg("MONDAY_API_TOKEN"); did=cfg("MONDAY_DEALS_BOARD_ID"); wid=cfg("MONDAY_WORK_ORDERS_BOARD_ID")
    if not all([token,did,wid]): raise MondayAPIError("Configure MONDAY_API_TOKEN, MONDAY_DEALS_BOARD_ID and MONDAY_WORK_ORDERS_BOARD_ID.")
    c=MondayClient(token)
    d,dw=items_to_dataframe(c.read_board(did),"deals")
    w,ww=items_to_dataframe(c.read_board(wid),"work_orders")
    st.session_state.update(deals=d,work_orders=w,warnings=dw+ww,loaded=True)

st.title("🚁 Skylark Drones — Business Intelligence Agent")
st.caption("Founder-level answers from live, read-only monday.com data")

with st.sidebar:
    st.header("Connection")
    token, did, wid = cfg("MONDAY_API_TOKEN"), cfg("MONDAY_DEALS_BOARD_ID"), cfg("MONDAY_WORK_ORDERS_BOARD_ID")
    if token and did and wid: st.success("monday.com configured")
    else: st.warning("monday.com configuration incomplete")
    if st.button("↻ Refresh live monday.com data", type="primary", use_container_width=True):
        with st.spinner("Reading all records from both boards…"):
            try: load_live(); st.success(f"Loaded {len(st.session_state.deals):,} deals + {len(st.session_state.work_orders):,} work orders.")
            except Exception as e: st.error(str(e))

if not st.session_state.get("loaded"):
    st.info("Configure the three monday.com secrets, then click **Refresh live monday.com data**.")
    st.markdown("""
### Supported founder questions
**Sales & pipeline**
- How many deals are there?
- How many deals are currently in the pipeline?
- What is our total pipeline value?
- What is our active pipeline value?
- What is our weighted pipeline?
- How many won/lost deals do we have?
- What is our win rate?
- Which sectors have the largest pipeline?
- Show me all sales/deals.

**Operations & finance**
- How many work orders do we have?
- How many are completed/open?
- How are our work orders performing?
- How much have we billed/collected?
- What are our receivables?
- What is our collection rate?
- Show work-order financials by sector.

**Executive**
- Give me a leadership update.
- What are the biggest business risks?
- What is our data quality like?
""")
    st.stop()

deals, work_orders = st.session_state.deals, st.session_state.work_orders
st.sidebar.metric("Deal records", f"{len(deals):,}")
st.sidebar.metric("Work-order records", f"{len(work_orders):,}")
for w in st.session_state.get("warnings",[]): st.warning(w)

agent=BI_Agent(deals,work_orders)
if "history" not in st.session_state: st.session_state.history=[]
for role,msg in st.session_state.history:
    with st.chat_message(role): st.markdown(msg)

q=st.chat_input("Ask a founder-level business question…")
if q:
    st.session_state.history.append(("user",q))
    with st.chat_message("user"): st.markdown(q)
    with st.chat_message("assistant"):
        with st.spinner("Analyzing live monday.com data…"): r=agent.ask(q)
        st.markdown("### Answer")
        st.markdown(r.get("answer",""))
        s=r.get("summary",{})
        if s:
            m=s.get("metric")
            cards=[]
            if m in {"deal_count","won_count","lost_count","order_count","completed_count","open_count"}: cards=[(m.replace("_"," ").title(),s.get("value",0))]
            elif m in {"pipeline_value","weighted_pipeline_value","won_value","lost_value","average_deal_value","order_value","billed_value","collected_value","receivable_value","billing_gap"}: cards=[(m.replace("_"," ").title(),BI_Agent.money(s.get("value",0)))]
            elif m=="operational_health": cards=[("Work Orders",s.get("total_orders",0)),("Completed",s.get("completed",0)),("Completion",f"{s.get('completion_rate',0):.1f}%"),("Receivables",BI_Agent.money(s.get('receivables',0)))]
            elif m=="leadership_update": cards=[("All Deals",s.get("all_deals",0)),("Active Deals",s.get("active_deals",0)),("Active Pipeline",BI_Agent.money(s.get("pipeline",0))), ("Receivables",BI_Agent.money(s.get("receivables",0)))]
            if cards:
                cols=st.columns(len(cards))
                for c,(k,v) in zip(cols,cards): c.metric(k,v)
        if r.get("rows"):
            st.markdown("### Breakdown / records")
            st.dataframe(r["rows"],use_container_width=True,hide_index=True)
        if r.get("warnings"):
            st.markdown("### Data-quality notes")
            for w in r["warnings"]: st.warning(w)
        st.session_state.history.append(("assistant",r.get("answer","")))
