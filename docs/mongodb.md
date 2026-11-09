## Report pipelines

All pipelines live in `mongodb/pipelines/` as `{ "collection", "description", "pipeline" }`.
Run one with `uv run python mongodb/run_pipeline.py <n> --limit 3`.
Money is stored in cents (integers) and converted to euros only in the last stage.
Dates and hours use the Europe/Lisbon time zone.

### Report 2: revenue per organiser per month
Collection: `report_orders`. Revenue counts only `paid` orders (refunded orders gave the money back).
Sample result:
```json
<cola o output de run_pipeline.py 2>
```

(repetir para 3, 4, 5, 6)

### Report 6 limitation
The hold-attempt log records the outcome of the hold, not whether the customer paid
afterwards, so "did not end in a sale" is approximated by refused attempts.