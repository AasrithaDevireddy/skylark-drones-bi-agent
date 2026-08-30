# Skylark Drones — Monday.com Business Intelligence Agent

A production-oriented, read-only founder BI agent for the Skylark Drones technical assignment.

## What is important about this version

The analytics engine is **deterministic**. An LLM may help understand a natural-language question, but it cannot invent or calculate business numbers. The approved plan is executed against the live monday.com snapshot by Python.

### Correct business semantics

- **All deals** = every item returned from the Deals board. Malformed/header-like records are retained in total counts and surfaced as data-quality warnings.
- **Active pipeline** = `Open` + `On Hold`.
- **Won** = `Won` + `Closed Won`.
- **Lost** = `Dead` + `Lost` + `Closed Lost`.
- **Weighted pipeline** = active deal value × probability (`High 75%`, `Medium 50%`, `Low 25%`). Unknown/missing probability contributes zero and is called out.
- **Energy** = `Renewables + Powerline`, because the supplied dataset has no exact `Energy` label.
- **Work-order open/incomplete** = anything not marked `Completed`; this avoids falsely treating statuses such as `Ongoing`, `Not Started`, `Pause / struck`, and `Executed until current month` as completed.
- Counts never drop records merely because a monetary/status field is missing.

## Configuration

Set these as Streamlit Secrets or environment variables:

```toml
MONDAY_API_TOKEN = "..."
MONDAY_DEALS_BOARD_ID = "..."
MONDAY_WORK_ORDERS_BOARD_ID = "..."
OPENAI_API_KEY = "optional"
OPENAI_MODEL = "gpt-4o-mini"
```

The app is read-only and uses monday.com's GraphQL API with cursor pagination. It does not embed the assignment's Excel/CSV data.

## Local run

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Tests:

```bash
pytest -q
```

## Deployment

Streamlit Community Cloud can run `app.py`. Docker support is also included.

## Example evaluator questions

### Deals
- How many deals are there?
- How many deals are currently in the pipeline?
- What is our total pipeline value?
- What is our active pipeline value?
- What is our weighted pipeline?
- How many won deals?
- How many lost deals?
- What is our win rate?
- Which sectors have the largest pipeline?
- Show me all sales/deals.
- Show pipeline by owner.
- Show pipeline by stage.

### Work orders
- How many work orders do we have?
- How many are completed?
- How many are open?
- How are our work orders performing?
- How much have we billed?
- How much have we collected?
- What are our receivables?
- What is our collection rate?
- What is still to be billed?
- Show work-order financials by sector.
- Show execution status breakdown.
- Show me all work orders.

### Cross-source
- Give me a leadership update.
- Give me an executive summary of sales and operations.
- What is our data quality like?

## Assignment alignment

The original assignment requires a hosted prototype, dynamic monday.com reads, resilience to missing/inconsistent data, conversational founder-level queries, business intelligence across work orders/deals, error handling, source code, README, and a short decision log. This project is structured around those requirements.

## Supplied-workbook benchmark

For a correctly imported copy of the supplied snapshot, the production engine should reproduce the benchmarks in `VALIDATION.md`. This file is documentation/test guidance only; the deployed app still reads monday.com dynamically.
