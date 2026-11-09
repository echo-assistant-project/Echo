---
name: data-analysis
description: Turn raw data (CSV, Excel, exports) into answers — cleaning, summarising, charts and honest conclusions, in Excel, Google Sheets or Python pandas. Use for "analyse this data", "what does this spreadsheet show", "make a chart of sales", "find trends", "clean this CSV".
audience: developers
field: Technology
courses: Google Data Analytics Professional Certificate (Coursera) | https://www.coursera.org/professional-certificates/google-data-analytics ; Kaggle Learn: Pandas, Data Cleaning, Data Visualization | https://www.kaggle.com/learn ; Khan Academy Statistics and Probability | https://www.khanacademy.org/math/statistics-probability
source: Echo (written for Echo from these courses' syllabi)
license: same as Echo
---

# Data analysis

## 1. Ask the question first
Write the decision the data should inform ("which product to restock", "did the ad campaign work"). Name the metric, the time period and the comparison (last month, last year, other region).

## 2. Look before you trust
- Rows and columns, data types, date range, units (₹ vs lakh), duplicates, blanks, obvious typos ("Vizag" vs "Visakhapatnam").
- In pandas: `df.shape`, `df.info()`, `df.describe()`, `df.isna().sum()`, `df.duplicated().sum()`.

## 3. Clean (and record every step)
Trim spaces, standardise names and dates, fix types, remove exact duplicates, decide what to do with blanks (drop, fill, or flag). Keep the raw file untouched; clean a copy.

## 4. Summarise
- Totals and averages by group (pivot table / `groupby`), shares (% of total), change over time (month-over-month %), top and bottom 10.
- Prefer the **median** when a few huge values skew the average (house prices, salaries).

## 5. Charts that tell the truth
Line for trends over time; bar for comparing categories; scatter for relationships; avoid pie charts with more than 4 slices and 3-D charts. Start bar axes at zero; label units; one message per chart, written as its title ("Sales fell 12% in October").

## 6. Conclusions without fooling yourself
- Correlation is not causation; check for seasonality, small samples and one-off events.
- Say how sure you are and what data is missing. Give 1–3 recommendations tied to the original question.

## 7. Hand-off
A one-page summary: question, answer, key chart, caveats, next steps. Share the cleaned file and the steps so someone can repeat it.
