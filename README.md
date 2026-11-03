# ARCS Grant Finder v4

A local Streamlit research application covering **City Grants, King County & 4Culture, Washington State, Private Foundations, Federal Grants**. Includes the 21 historical v3 leads, live federal API search (requires personal API key), flexible CSV imports, manual state/county/city/foundation collection, unified relevance scoring, exact duplicate merges, fuzzy duplicate warnings, application tracker and CSV export.

## Run locally

Install Python 3.10+. Unzip this folder and open a terminal inside `ARCS_Grant_Finder_v4`:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Streamlit displays a browser URL, normally `http://localhost:8501`. Stop by pressing Ctrl+C in the terminal.

## Federal

Get a Simpler.Grants.gov API key from https://simpler.grants.gov/developers . Enter it in the **Federal live search** tab (or set `SIMPLER_GRANTS_API_KEY` environment variable). Click Search, inspect results, then Add federal results to unified list. The live request cannot be validated without your API key. API docs: https://wiki.simpler.grants.gov/product/api/search-opportunities .

## Washington state and other sources

Use **Import state & local**. Download the template and fill in details from the official agency sites. Import by category. The importer accepts columns like `Title`, `Agency`, `Close Date`, `Award Range`, `URL`, `Eligibility`, `Description` as well as the native ARCS master format. Imported records are marked *unverified*. State agency sites do not provide a verified general-public API integrated here. **FundHubWA is primarily focused on climate / clean energy, not general arts funding.**

## Persistence

This is a local prototype. Session changes are NOT persisted between server restarts or shared between browsers. Export **arcs_grants_master.csv** and the application-tracker CSV, then restore them next time. For real shared online use, add a proper persistent database (e.g. hosted Postgres with authentication), secret management, and scheduled refresh jobs before deployment.

## Safety and provenance

Do not treat scores as eligibility or success predictions. The v3 research snapshot dates to November 2, 2026; old deadlines are flagged automatically, but a listed rolling or open status must be confirmed on the source website. Never commit API keys to GitHub. Federal searches and imports need a network connection where applicable. No application is submitted by this tool.

## Run tests

```bash
python -m unittest discover -s tests -v
```
