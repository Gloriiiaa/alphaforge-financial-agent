# AlphaForge Financial Agent

Mateo is a company research demo built for the AlphaForge AI Simulation. It combines historical market performance, ESG evidence, and market risk checks to explain how a company screens under the simulation’s investment rules.

**[Open the live demo](https://gloriiiaa.github.io/alphaforge-financial-agent/)**

## Try the demo

1. Enter a supported company name or ticker, or select one of the examples.
2. Choose a lookback period of 90 days, 1 year, 3 years, or 5 years.
3. Select a moderate or stricter risk threshold and click **Analyze Company**.

Try **CNQ.TO** for a tailings enforcement case, **ENB.TO** for Line 5, **MSFT** for emissions disclosure, or **NVDA** for a market risk example.

## What the report shows

| Section | What you can review |
| --- | --- |
| Screening decision | The simulation’s verdict, its rationale, and follow-up research |
| Historical performance | Price change, dividend-adjusted return in CAD, and a chart comparing the stock with its benchmark |
| ESG evidence | Dated evidence with source links and gaps in environmental, social, or governance coverage |
| Market risk | Annualized volatility, maximum drawdown, threshold comparisons, and hypothetical stress scenarios |

## How it works

The GitHub Pages demo is a self-contained HTML page with precomputed reports for 20 companies. It renders reports and charts in the browser from an embedded historical snapshot, with no backend or API key required. The report shows the date range and data sources used for each analysis.

| File | Purpose |
| --- | --- |
| `index.html` | Interactive demo and GitHub Pages entry point |
| `analyze.py` | Company analysis logic |
| `build_demo.py` | Demo generation script |
| `evidence.json` | Sample ESG evidence and source references |

To run the demo locally, download `index.html` and open it in a browser.

## Data scope

The demo uses historical market data and a curated sample of public ESG evidence. Coverage varies by company. Screening decisions are outputs of the datathon simulation and are intended for research and demonstration.
