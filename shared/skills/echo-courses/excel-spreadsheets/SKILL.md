---
name: excel-spreadsheets
description: Get things done in Excel or Google Sheets — formulas, XLOOKUP, SUMIFS, pivot tables, charts, cleaning data, budgets and trackers. Use for "teach me Excel", "write an Excel formula", "make a pivot table", "VLOOKUP not working", "make a budget sheet", "remove duplicates".
audience: work
field: Office
courses: Excel Skills for Business Specialization (Macquarie University, Coursera) | https://www.coursera.org/specializations/excel ; Microsoft Excel video training | https://support.microsoft.com/excel ; GCFGlobal Excel tutorials (free) | https://edu.gcfglobal.org/en/excel/ ; Google Sheets training (Google Workspace Learning Center) | https://support.google.com/a/users/answer/9282959
source: Echo (written for Echo from these courses' syllabi)
license: same as Echo
---

# Excel and spreadsheets

## 1. Set the sheet up right
One table per sheet, headers in row 1, one kind of data per column, no blank rows inside. Turn it into a Table (Ctrl+T): formulas fill down, filters appear, ranges grow by themselves. Freeze the header row (View → Freeze Panes).

## 2. The formulas that do 90% of the work
- `=SUM(B2:B100)`, `=AVERAGE()`, `=COUNT()` / `=COUNTA()`, `=ROUND(x, 2)`.
- Conditional totals: `=SUMIFS(Amount, Category, "Food", Month, "Nov")`, `=COUNTIFS(...)`, `=AVERAGEIFS(...)`.
- Look up: `=XLOOKUP(A2, Products[Code], Products[Price], "Not found")` (older Excel: `=INDEX(col, MATCH(A2, codes, 0))`; VLOOKUP needs `FALSE` as the last argument and breaks when columns move).
- Logic: `=IF(C2>=40, "Pass", "Fail")`, `=IFS(...)`, `=IFERROR(x, 0)`.
- Text: `=TRIM()`, `=PROPER()`, `=TEXTSPLIT()` / Text to Columns, `=CONCAT()` or `&`.
- Dates: `=TODAY()`, `=EDATE(date, 1)`, `=DATEDIF(start, end, "m")`, `=NETWORKDAYS()`.
- Dynamic: `=UNIQUE()`, `=FILTER(table, condition)`, `=SORT()`.
- `$` locks a reference: `$B$1` stays fixed when copying (F4 toggles).

## 3. Pivot tables (summaries in seconds)
Click in the table → Insert → PivotTable → drag a category to Rows, a number to Values (Sum), dates to Columns (group by Month). Refresh after data changes. Slicers make it clickable for others.

## 4. Cleaning data
Remove Duplicates (Data tab), Trim spaces, Text to Columns, Find & Replace, Flash Fill (Ctrl+E), conditional formatting to spot blanks and outliers. Power Query for repeatable cleaning of monthly exports.

## 5. Charts
Select the data → Insert → Recommended Charts. Line for time, bar for categories; title says the message; remove clutter (gridlines, 3-D).

## 6. Useful templates to build
Monthly budget (income, categories, actual vs planned with SUMIFS), EMI tracker, attendance sheet, inventory with low-stock highlighting, simple invoice with GST.

## 7. Speed keys
Ctrl+Arrow (jump), Ctrl+Shift+Arrow (select), Ctrl+D (fill down), Ctrl+; (today's date), Alt+= (AutoSum), F2 (edit cell), Ctrl+1 (format).

## 8. When a formula fails
`#N/A` not found (check spaces/types), `#VALUE!` wrong type, `#REF!` deleted cells, `#DIV/0!` divide by zero, `#NAME?` misspelled function. Use Formulas → Evaluate Formula to step through.
