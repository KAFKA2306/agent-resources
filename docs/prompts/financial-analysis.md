# Financial analysis prompt

Use this prompt for financial claims, valuation checks, earnings commentary, and market posts.

## Prompt

Before answering any financial question, verify current and historical facts against the latest available primary sources.

1. Separate each claim into:
   - market data: share price, market capitalization, trading date/time;
   - reported financials: revenue, operating income, operating cash flow, free cash flow, cash, debt, shares outstanding;
   - company guidance: only figures explicitly guided by the company;
   - external estimates: analyst consensus, prediction markets, social-media claims, or model outputs;
   - derived calculations: valuation multiples, growth rates, margins, annualized values.
2. For reported financials and guidance, prefer company investor-relations releases and SEC filings. Check the period, units, and whether a figure is GAAP or non-GAAP.
3. Never present an external estimate as company guidance or reported fact. If no primary source publishes the estimate, label it as an external estimate and require its source before treating it as verified.
4. Recalculate every derived metric from the cited inputs. Show the formula when the calculation is material to the conclusion.
5. Market capitalization and share price must include an as-of date/time because they change continuously.
6. When a post says a multiple is "below X", test the literal inequality. Do not soften a false threshold claim into "almost correct" without stating the exact result.
7. Distinguish trailing, year-to-date, annualized, forward, and consensus figures. Do not mix them in one multiple.
8. If only year-to-date cash flow is available, do not call a simple annualization a forecast. Label it explicitly as annualized run rate and state the calculation.
9. Social-media account identity, affiliation, motivation, or emphasis must not be inferred without direct evidence.
10. Remove any factual claim that cannot be supported by an accessible source. State what remains unverified.

## Required output

- Verdict: verified / partly verified / unverified / contradicted.
- Verified facts with exact dates, periods, units, and sources.
- Unverified or externally estimated inputs, clearly separated.
- Recalculated figures with formulas.
- A short conclusion that preserves the distinction between fact, estimate, and interpretation.

## Example: Meta valuation claim, 2026-08-18 market data

A claim such as "Meta has a market capitalization of about $1.41T, 2026 operating cash flow of about $131B, so P/OCF is below 10x" must be handled as follows:

- Current market capitalization is market data and must be timestamped.
- Meta reported operating cash flow of $32.226B for Q1 2026 and $31.86B for Q2 2026. First-half operating cash flow is therefore $64.086B.
- Meta's published 2026 outlook gives revenue, expense, capital-expenditure, operating-income, and tax-rate guidance, but does not provide full-year operating-cash-flow guidance.
- Therefore a $131B full-year 2026 OCF figure is not verified as Meta guidance from primary sources. It must be attributed to the external estimator that produced it.
- If an external $131B OCF estimate is accepted and market capitalization is $1.421T, P/OCF = 1,421.05 / 131 = 10.85x, so the literal statement "below 10x" is false.
- A simple annualization of first-half reported OCF is $64.086B × 2 = $128.172B. This is an annualized run rate, not a forecast; at $1.421T market capitalization it implies about 11.09x.

Primary sources for the reported cash-flow figures:
- Meta Q1 2026 results: https://investor.atmeta.com/investor-news/press-release-details/2026/Meta-Reports-First-Quarter-2026-Results/
- Meta Q1 2026 Form 10-Q: https://www.sec.gov/Archives/edgar/data/1326801/000162828026028526/meta-20260331.htm
- Meta Q2 2026 results filed with the SEC: https://www.sec.gov/Archives/edgar/data/1326801/000162828026050596/meta-06302026xexhibit991.htm
