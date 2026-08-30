import json
import re
from typing import Any, Dict, Iterable, List, Tuple
import pandas as pd

ALIASES = {
    "deal_name": ["deal name", "deal name masked", "dealname", "name", "deal name masked"],
    "owner_code": ["owner code", "bd/kam personnel code", "owner", "bd kam personnel code"],
    "client_code": ["client code", "customer name code", "customer code"],
    "deal_status": ["deal status", "status"],
    "actual_close_date": ["close date (a)", "close date", "closure date", "actual close date"],
    "closure_probability": ["closure probability", "probability", "closure probability (%)"],
    "deal_value": ["masked deal value", "deal value", "deal amount", "amount"],
    "tentative_close_date": ["tentative close date", "expected close date", "probable close date"],
    "deal_stage": ["deal stage", "stage"],
    "product_deal": ["product deal", "product"],
    "sector": ["sector/service", "sector", "industry", "sector service"],
    "created_date": ["created date", "created at"],
    "execution_status": ["execution status"],
    "data_delivery_date": ["data delivery date"],
    "po_date": ["date of po/loi", "po date", "loi date"],
    "document_type": ["document type"],
    "probable_start_date": ["probable start date", "start date"],
    "probable_end_date": ["probable end date", "end date"],
    "nature_of_work": ["nature of work", "type of work"],
    "invoice_amount_excl_gst": ["amount in rupees (excl of gst) (masked)", "amount in rupees (excl of gst)", "order value excl gst"],
    "invoice_amount_incl_gst": ["amount in rupees (incl of gst) (masked)", "amount in rupees (incl of gst)", "order value incl gst"],
    "billed_value_excl_gst": ["billed value in rupees (excl of gst.) (masked)", "billed value in rupees (excl of gst) (masked)", "billed value"],
    "billed_value_incl_gst": ["billed value in rupees (incl of gst.) (masked)", "billed value in rupees (incl of gst) (masked)"],
    "collected_amount": ["collected amount in rupees (incl of gst.) (masked)", "collected amount in rupees (incl of gst) (masked)", "collected amount"],
    "amount_to_be_billed_excl_gst": ["amount to be billed in rs. (exl. of gst) (masked)", "amount to be billed in rs. (excl. of gst) (masked)", "amount to be billed"],
    "amount_to_be_billed_incl_gst": ["amount to be billed in rs. (incl. of gst) (masked)", "amount to be billed in rs. (incl of gst) (masked)"],
    "amount_receivable": ["amount receivable (masked)", "amount receivable", "ar"],
    "quantity_ops": ["quantity by ops"],
    "quantity_po": ["quantities as per po"],
    "quantity_billed": ["quantity billed (till date)"],
    "balance_quantity": ["balance in quantity"],
    "invoice_status": ["invoice status"],
    "expected_billing_month": ["expected billing month"],
    "actual_billing_month": ["actual billing month"],
    "actual_collection_month": ["actual collection month"],
    "wo_status_billed": ["wo status (billed)"],
    "collection_status": ["collection status"],
    "collection_date": ["collection date"],
    "billing_status": ["billing status"],
}

DATE_COLS = [
    "actual_close_date", "tentative_close_date", "created_date", "data_delivery_date",
    "po_date", "probable_start_date", "probable_end_date", "last_invoice_date",
    "collection_date", "expected_billing_month", "actual_billing_month", "actual_collection_month",
]
NUMERIC_COLS = [
    "deal_value", "invoice_amount_excl_gst", "invoice_amount_incl_gst", "billed_value_excl_gst",
    "billed_value_incl_gst", "collected_amount", "amount_to_be_billed_excl_gst",
    "amount_to_be_billed_incl_gst", "amount_receivable", "quantity_ops", "quantity_po",
    "quantity_billed", "balance_quantity",
]


def clean_key(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def parse_number(v: Any):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)) and not pd.isna(v):
        return float(v)
    s = str(v).replace(",", "").replace("₹", "").strip()
    if not s or s.lower() in {"nan", "none", "null", "na", "n/a", "-"}:
        return None
    # Preserve negatives and decimals; tolerate units such as HA.
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def parse_date(v: Any):
    if v is None or (isinstance(v, float) and pd.isna(v)) or v == "":
        return pd.NaT
    if isinstance(v, dict):
        v = v.get("date") or v.get("datetime") or v.get("value")
    return pd.to_datetime(v, errors="coerce", dayfirst=False)


def value_from_column(cv: Dict[str, Any]) -> Any:
    text = cv.get("text")
    raw = cv.get("value")
    if text not in (None, ""):
        return text
    if raw in (None, "", "null"):
        return None
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            for k in ("date", "datetime", "text", "value", "label", "amount"):
                if k in obj and obj[k] not in (None, ""):
                    return obj[k]
            if "personsAndTeams" in obj:
                return obj["personsAndTeams"]
        return obj
    except Exception:
        return raw


def canonicalize(columns: Iterable[str]) -> Dict[str, str]:
    result = {}
    normalized = {clean_key(c): c for c in columns}
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            if clean_key(alias) in normalized:
                result[canonical] = normalized[clean_key(alias)]
                break
    return result


def _clean_text(series):
    return series.astype("string").str.strip().str.replace(r"\s+", " ", regex=True)


def items_to_dataframe(board_payload: Dict[str, Any], board_kind: str) -> Tuple[pd.DataFrame, List[str]]:
    """Flatten a live monday board into canonical analytics columns.

    The record count intentionally preserves every monday item. A malformed/header-like
    item is still a record for total-count questions; it is only excluded from status-based
    business metrics when its status cannot match a real business state.
    """
    board = board_payload.get("board", {})
    items = board_payload.get("items", []) or []
    columns = board.get("columns", []) or []
    title_by_id = {str(c.get("id")): c.get("title") for c in columns}

    rows = []
    for item in items:
        row = {
            "monday_item_id": item.get("id"),
            "monday_item_name": item.get("name"),
            "monday_url": item.get("url"),
            "monday_created_at": item.get("created_at"),
            "monday_updated_at": item.get("updated_at"),
        }
        for cv in item.get("column_values", []) or []:
            title = title_by_id.get(str(cv.get("id")), cv.get("id"))
            if title:
                row[title] = value_from_column(cv)
        rows.append(row)

    df = pd.DataFrame(rows)
    warnings: List[str] = []
    if df.empty:
        return df, [f"{board_kind}: board returned no items."]

    mapping = canonicalize(df.columns)
    for canonical, source in mapping.items():
        df[canonical] = df[source]

    if board_kind == "deals" and "deal_name" not in df.columns:
        df["deal_name"] = df.get("monday_item_name")
    if board_kind == "work_orders" and "deal_name" not in df.columns:
        df["deal_name"] = df.get("monday_item_name")

    for c in DATE_COLS:
        if c in df.columns:
            df[c] = df[c].map(parse_date)
    for c in NUMERIC_COLS:
        if c in df.columns:
            df[c] = df[c].map(parse_number)

    for c in ["sector", "deal_status", "execution_status", "closure_probability", "deal_stage", "collection_status", "billing_status", "invoice_status", "wo_status_billed"]:
        if c in df.columns:
            df[c] = _clean_text(df[c])

    if "deal_status" in df.columns:
        df["deal_status"] = df["deal_status"].str.title()
    if "execution_status" in df.columns:
        df["execution_status"] = df["execution_status"].str.title()
    if "closure_probability" in df.columns:
        df["closure_probability"] = df["closure_probability"].str.title()

    required = {
        "deals": ["deal_name", "deal_value", "deal_status", "sector"],
        "work_orders": ["deal_name", "execution_status", "sector"],
    }[board_kind]
    for c in required:
        if c not in df.columns:
            warnings.append(f"{board_kind}: expected field '{c}' was not found on the board.")
        elif df[c].isna().all():
            warnings.append(f"{board_kind}: field '{c}' exists but all values are missing.")

    # Explicitly surface malformed imported rows instead of silently deleting them.
    if board_kind == "deals" and "deal_status" in df.columns:
        malformed = df["deal_status"].fillna("").str.lower().isin({"deal status", "status"}).sum()
        if malformed:
            warnings.append(f"Data quality: {malformed:,} deal record(s) have a header-like status value and are retained in total record counts but excluded from active/won/lost status metrics.")
    if board_kind == "deals" and "deal_value" in df.columns:
        missing = int(df["deal_value"].isna().sum())
        if missing:
            warnings.append(f"Data quality: {missing:,} of {len(df):,} deal records ({missing/len(df):.0%}) lack a usable deal value.")
    return df, warnings
