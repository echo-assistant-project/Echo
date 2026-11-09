---
name: machine-learning-basics
description: Understand and apply machine learning and AI — when ML fits, framing a problem, splitting data, choosing a simple model, measuring it honestly, and using LLMs well. Use for "teach me machine learning", "can AI predict…", "build a model", "what is overfitting", "how do LLMs work".
audience: developers
field: Technology
courses: Machine Learning Specialization (Andrew Ng, DeepLearning.AI / Stanford, Coursera) | https://www.coursera.org/specializations/machine-learning-introduction ; Google Machine Learning Crash Course | https://developers.google.com/machine-learning/crash-course ; Practical Deep Learning for Coders (fast.ai) | https://course.fast.ai/ ; Elements of AI (University of Helsinki) | https://www.elementsofai.com/
source: Echo (written for Echo from these courses' syllabi)
license: same as Echo
---

# Machine learning basics

## 1. Does this need ML at all?
Use ML when there are many examples, a pattern too fuzzy for hand-written rules, and a tolerable cost for mistakes. If a few `if` rules or a spreadsheet formula work, use those.

## 2. Frame the problem
- **Classification** (spam or not, which category), **regression** (a number: price, demand), **clustering** (group similar customers), **ranking/recommendation**.
- Define the label you predict, the features you know at prediction time (no "future" information — that's leakage), and the metric that matters to the business.

## 3. Data and splits
Split into train / validation / test (e.g. 70/15/15), or by time for anything that changes over time. Never tune on the test set. Check class balance; look at examples by hand.

## 4. Start simple
Baseline first (predict the average or the most common class). Then linear/logistic regression, decision trees, random forests, gradient boosting (XGBoost/LightGBM) for tables; pretrained deep models for images, audio and text (fine-tune instead of training from scratch).

## 5. Measure honestly
- Classification: accuracy can mislead on imbalanced data — use precision, recall, F1, a confusion matrix.
- Regression: MAE (easy to explain), RMSE.
- **Overfitting**: great on train, poor on validation → more data, simpler model, regularisation, early stopping.
- Check errors by group (region, gender, age) for unfairness.

## 6. Using large language models (LLMs)
LLMs predict the next words from huge text training. They're strong at drafting, summarising and explaining, weak at exact facts and arithmetic. Give clear instructions, examples and source text (retrieval); ask for structured output; verify facts; never paste secrets.

## 7. Shipping a model
Save the pipeline (preprocessing + model), monitor live accuracy and data drift, keep a fallback rule, and retrain on a schedule.
