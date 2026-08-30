# Assignment Snapshot Validation

These are **test/validation benchmarks derived from the supplied workbooks only**. They are not embedded into the production application.

| Question | Expected snapshot result |
|---|---:|
| How many deals are there? | 346 records |
| How many active deals? | 51 (49 Open + 2 On Hold) |
| Total deal value | ₹230.55 Cr |
| Active pipeline value | ₹68.82 Cr |
| Weighted active pipeline | ₹27.16 Cr |
| Won deals | 165 |
| Lost/dead deals | 127 |
| Work orders | 176 |
| Completed work orders | 117 |
| Non-completed/open work orders | 59 |
| Billed value, excl. GST | ₹10.74 Cr |
| Billed value, incl. GST | ₹12.67 Cr |
| Collected value, incl. GST | ₹9.04 Cr |
| Receivables | ₹3.63 Cr |

The Deals workbook also contains 2 header-like status records and 1 record with a missing status. The application retains these items for total record counts and surfaces data-quality warnings instead of silently deleting them.

The Work Orders workbook has a blank first spreadsheet row; the actual header row is the second spreadsheet row, yielding 176 work-order records.
