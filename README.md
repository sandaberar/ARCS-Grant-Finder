# ARCS Grant Finder v6 — live opportunity search and IRS foundation history

## What's different from v5

- **Official-site deadline extraction:** identifies a deadline only when a specific date appears in the same paragraph/list item as explicit application-deadline language. Multiple conflicting dates => blank, marked for review. The original sentence is displayed. A past extracted date is labelled closed (date passed), not automatically verified closed by the funder.
- **Eligibility evidence:** extracts exact paragraphs with stated eligibility or applicant rules. **It does not certify ARCS's eligibility.** The source website is linked for confirmation.
- **Live foundation grant history:** scans the publicly accessible, IRS-derived NCCS 990-PF grants-paid table and looks for historical grants to arts and cultural recipients, weighted toward Washington. Maps recipient/amount/purpose to grantmaking foundation from the filing header. Entries are marked **Historical funding lead — application unverified**, never as open grant applications.
- **Federal live API:** uses your existing Simpler.Grants.gov key stored under `SIMPLER_GRANTS_API_KEY` in Streamlit secrets.
- **No imported grant CSV is required.**

## Updating the existing GitHub deployment

Upload/replace these files in the *root* of `sandaberar/ARCS-Grant-Finder`: `app.py`, `discovery.py`, `federal.py`, `foundations.py`, `verification.py`, and `requirements.txt`. You can also replace `README.md` and upload `tests/` if you like. Do NOT upload `__pycache__` or the API key. Commit changes. Streamlit should redeploy automatically.

Your existing secrets setting should still be:

```toml
SIMPLER_GRANTS_API_KEY = "your-real-key"
```

## Local run

```powershell
py -3.13 -m pip install -r requirements.txt
py -3.13 -m streamlit run app.py
```

## Important limits and evidence rules

1. **A webpage check is live, but it is not a guaranteed complete search of the web.** It follows configured official-source sites and a bounded set of links. Some sites block requests, require JavaScript, or publish PDF-only application details. Diagnostics report failures.
2. **Deadlines and eligibility remain provisional.** Multiple dated programs on one page, partial HTML, amendments and organization-specific rules require funder confirmation. No tool can prove ARCS eligibility using only website text without ARCS's legal/address/program details.
3. **IRS foundation history is not a current grant application.** A foundation that previously awarded money may be invitation-only, have changed priorities, or no longer fund. This version finds *historical prospects with evidence* and separately checks configured current foundation sites.
4. **NCCS public data can be large.** Each live scan downloads an annual CSV (2025, 2024 or 2023). It streams data rather than materializing the entire table. The app limits transfers to 240 MB per grants-paid file and 90 MB for the header file, and caps displayed matches. Scans can fail on hosting/network restrictions and this will be shown in diagnostics. A single tax year is not all IRS history.
5. **Shared storage** is not yet implemented. Each user sees a session-level result set. This is not a shared multi-user application tracker.
6. **No runtime external integration test completed in the build environment** (network access blocked). Python syntax and four deterministic parser/data tests passed. Verify external websites and NCCS table access in your deployed Streamlit app.

## Data references

- Federal API: https://simpler.grants.gov/developers
- Official public IRS e-file returns: https://www.irs.gov/charities-non-profits/form-990-series-downloads
- NCCS IRS-derived 990-PF tables, published October 2026: https://nccs.urban.org/nccs/catalogs/catalog-efilepf-v3_1.html
- Data dictionary: https://nonprofit-open-data-collective.github.io/concordance990/articles/data-dictionary-990pf.html

This is a research assistant, not an eligibility or application approval system.
