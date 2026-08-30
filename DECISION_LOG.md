# Decision Log — Skylark Drones BI Agent

## Assumptions

1. monday.com is the production source of truth; the supplied Excel files are used to create the two monday boards and are not embedded in the deployed app.
2. All monday items count as records for total-record questions. Malformed/header-like records are not silently deleted; status-based metrics naturally exclude them because they do not match real business statuses.
3. Active pipeline means Open + On Hold.
4. Weighted pipeline uses High 75%, Medium 50%, Low 25%. Missing probability/value is surfaced as a coverage caveat.
5. The source contains Renewables and Powerline rather than a literal Energy label, so Energy is interpreted as both.
6. Historical date phrases are anchored to the latest available source date when the dataset is a snapshot rather than the current calendar date.

## Architecture

Python + Streamlit + monday GraphQL + deterministic analytics + optional OpenAI query planning.

The model is deliberately not the calculator. It can translate a founder question into an allow-listed plan, while Python applies filters and performs every aggregation. This prevents an LLM from hallucinating a KPI or returning a plausible but incorrect number.

## Data resilience

Column aliases, number parsing, date parsing, whitespace/status normalization, null handling, missing-column detection, malformed-record warnings, and API error handling are implemented in the ingestion/analytics layers.

## Leadership updates

A leadership update combines active sales pipeline, weighted pipeline, won/lost counts, work-order completion, billing, collections and receivables, with data-quality caveats. The UI also provides drill-down tables.

## What I would improve with more time

- persistent cache with freshness timestamps,
- richer date/period comparison semantics,
- one-click PDF/Markdown leadership brief,
- configurable board-schema mapping UI,
- conversation memory for follow-up questions,
- observability for API latency and query errors,
- automated evaluator regression tests against a frozen anonymized snapshot.
