import pandas as pd
from core.analytics import execute_plan
from core.intent import heuristic_plan


def deals():
    return pd.DataFrame([
        {"monday_item_id":str(i),"deal_value":v,"deal_status":s,"closure_probability":p,"sector":sec}
        for i,(v,s,p,sec) in enumerate([(100,"Open","High","Renewables"),(200,"On Hold","Medium","Powerline"),(300,"Won",None,"Mining"),(400,"Dead",None,"Mining"),(500,"Deal Status",None,"Sector/service"),(None,None,None,None)],1)
    ])

def wo():
    return pd.DataFrame([
        {"monday_item_id":"w1","execution_status":"Completed","billed_value_incl_gst":100,"collected_amount":80,"amount_receivable":20,"sector":"Mining"},
        {"monday_item_id":"w2","execution_status":"Ongoing","billed_value_incl_gst":200,"collected_amount":100,"amount_receivable":100,"sector":"Powerline"},
    ])

def test_total_count_keeps_all_records():
    r=execute_plan(heuristic_plan("How many deals are there?"),deals(),wo())
    assert r["summary"]["value"]==6

def test_active_pipeline_is_open_plus_hold():
    r=execute_plan(heuristic_plan("How many deals are currently in the pipeline?"),deals(),wo())
    assert r["summary"]["value"]==2

def test_pipeline_values():
    assert execute_plan(heuristic_plan("What is our total pipeline value?"),deals(),wo())["summary"]["value"]==1500
    assert execute_plan(heuristic_plan("What is our active pipeline value?"),deals(),wo())["summary"]["value"]==300

def test_weighted_active_pipeline():
    r=execute_plan(heuristic_plan("What is our weighted pipeline?"),deals(),wo())
    assert r["summary"]["value"]==175

def test_won_lost():
    assert execute_plan(heuristic_plan("How many won deals?"),deals(),wo())["summary"]["value"]==1
    assert execute_plan(heuristic_plan("How many lost deals?"),deals(),wo())["summary"]["value"]==1

def test_energy_alias():
    p=heuristic_plan("How is our pipeline looking for the energy sector?")
    assert p["filters"]["sector"]=="energy"
    r=execute_plan(p,deals(),wo())
    assert r["summary"]["value"]==300

def test_work_order_metrics():
    assert execute_plan(heuristic_plan("How many work orders do we have?"),deals(),wo())["summary"]["value"]==2
    assert execute_plan(heuristic_plan("How many work orders are completed?"),deals(),wo())["summary"]["value"]==1
    assert execute_plan(heuristic_plan("How much have we billed?"),deals(),wo())["summary"]["value"]==300
    assert execute_plan(heuristic_plan("What are our receivables?"),deals(),wo())["summary"]["value"]==120

def test_operational_health():
    r=execute_plan(heuristic_plan("How are our work orders performing?"),deals(),wo())
    assert r["summary"]["total_orders"]==2
    assert r["summary"]["completed"]==1
    assert r["summary"]["completion_rate"]==50
