"""One-off: turn the raw Play Store export into data/reviews.csv (PII-redacted, with stable review ids).

Raw columns: rating,title,text,date. Output columns: rid,review_text,rating,date.
rid = "R" + 1-based data-row number in the raw export, so every theme/quote can be traced back to a row.
Usage: python scripts_prepare.py raw_export.csv
"""
import sys, pandas as pd, pii

raw = pd.read_csv(sys.argv[1])
txt = (raw["title"].fillna("").astype(str).str.strip() + " " + raw["text"].fillna("").astype(str)).str.strip()
red, counts = [], {}
for t in txt:
    r, f = pii.redact(t)
    red.append(r)
    for x in f:
        counts[x["type"]] = counts.get(x["type"], 0) + x["count"]
out = pd.DataFrame({"rid": ["R%d" % (i + 1) for i in range(len(raw))], "review_text": red,
                    "rating": raw["rating"], "date": raw["date"]})
out.to_csv("data/reviews.csv", index=False)
print("rows", len(out), "redactions", counts, "window", out["date"].min(), out["date"].max())
