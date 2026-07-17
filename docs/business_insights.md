# Demonstration Business Insights

Every number below comes from deterministic synthetic data generated for software verification.
It demonstrates analytical technique, not the performance of a real retailer.

## Executive baseline

The sample contains 750 order lines, 311 orders, 79 active customers, and 20 products. It produces
597,016.99 in revenue and 170,830.64 in profit, a 28.61% margin. Average order value is 1,919.67 and
average units per order is 10.56.

## Questions the model supports

- Is revenue growth accompanied by profit growth, or driven by discounting?
- Which products lead revenue but rank poorly on profit?
- Which categories, regions, and order lines create loss or weak margin?
- Who are the highest-value, newest, loyal, and at-risk customers under relative RFM scoring?
- Are quality warnings or rejected rows changing the trustworthiness of a refresh?

## Responsible interpretation

Use `sql/analysis_queries.sql`, the API filters, or Power BI pages to calculate current slices.
Do not hard-code a product or region recommendation from the sample into portfolio prose. A useful
review format is:

1. **Observation** — state the measured difference and filter context.
2. **Hypothesis** — give a plausible cause without presenting correlation as causation.
3. **Action** — propose a limited test, owner, and success measure.
4. **Guardrail** — identify margin, customer, or data-quality risk.

For example: a heavily discounted product with negative profit is a candidate for price/promotion
review, but the data does not include cost allocation, inventory, returns, or competitor pricing.
The correct next step is controlled investigation, not automatic delisting.

## Limitations

The synthetic model has no marketing attribution, inventory availability, returns, taxes,
fulfillment cost, currency conversion, product cost history, or causal experiment design. Customer
attributes are current-state, not slowly changing dimensions. RFM scores are relative to this small
dataset and should be recalibrated before real business use.

