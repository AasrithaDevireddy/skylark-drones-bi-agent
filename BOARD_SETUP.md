# Monday.com Setup

Create two separate boards from the assignment workbooks:

1. **Deals** — use the first row as column headers.
2. **Work Orders** — the workbook has a blank first row; promote the second spreadsheet row to headers when importing.

Keep monetary columns as Numbers and status/date columns as Status/Date where practical. Exact imported titles may vary; the normalizer maps common variants.

Required environment variables:

- `MONDAY_API_TOKEN`
- `MONDAY_DEALS_BOARD_ID`
- `MONDAY_WORK_ORDERS_BOARD_ID`

The app only issues read queries.
