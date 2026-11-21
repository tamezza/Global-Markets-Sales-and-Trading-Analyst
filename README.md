# Global Markets Sales & Trading Analyst — Job Simulation

My work on the **Bank of America Global Markets Sales and Trading Analyst** virtual job simulation: market analysis, trading decisions, client recommendations and process automation.

**Source:** [Forage — Bank of America, Sales and Trading Analyst](https://www.theforage.com/simulations/bank-of-america/sales-and-trading-analyst-i5jo)

## Progress

| Part | Topic | Status | Folder |
|------|-------|--------|--------|
| 0 | Intro & scenario | ✅ Done | [00_Intro_Scenario](00_Intro_Scenario/) |
| 1 | Market overview and insight generation | ✅ Done | [01_Market_Overview_Insight_Generation](01_Market_Overview_Insight_Generation/) |
| 2 | Navigating live market dynamics | ⏳ To do | [02_Navigating_Live_Market_Dynamics](02_Navigating_Live_Market_Dynamics/) |
| 3 | Client-centric product recommendations | ⏳ To do | [03_Client_Centric_Product_Recommendations](03_Client_Centric_Product_Recommendations/) |
| 4 | Innovating through automation or process analysis | ⏳ To do | [04_Automation_Process_Analysis](04_Automation_Process_Analysis/) |

Status: ✅ Done · 🔄 In progress · ⏳ To do

## Skills & tools

- LaTeX (reports)
- Python: pandas, NumPy, matplotlib, Jupyter (data analysis and charts)
- _Add as the project goes: Excel, Python, market data analysis, risk management…_

## Repository structure

```
.
├── README.md
├── style/forage.sty      # shared LaTeX style used by every part
├── 00_Intro_Scenario/
├── 01_Market_Overview_Insight_Generation/
├── 02_Navigating_Live_Market_Dynamics/
├── 03_Client_Centric_Product_Recommendations/
└── 04_Automation_Process_Analysis/
```

## Reproduce the analysis

```bash
pip install -r requirements.txt
cd 01_Market_Overview_Insight_Generation
jupyter notebook analysis.ipynb   # writes figures/ used by the report
```

The Forage datasets are not included (simulation use only): download them into each part's `resources/` folder first.

## Build the PDFs

Each part has its own `.tex` file. Compile from inside its folder:

```bash
cd 00_Intro_Scenario
pdflatex Intro.tex
```

New documents load the shared style with:

```latex
\documentclass[11pt]{article}
\usepackage{../style/forage}
```

## Disclaimer

This is a personal learning project. The simulation and its scenario belong to Forage and Bank of America; the analysis and solutions in this repository are my own.
