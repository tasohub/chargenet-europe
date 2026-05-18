# Deploying ChargeNet Europe

## 1. Prepare The Public Repo

1. Review `.gitignore` before publishing. Do not commit raw OSM extracts or large generated coverage matrices unless you have reviewed ODbL and repository-size implications.
2. Commit the app, docs, screenshots, summary CSVs under `docs/portfolio/data/`, and `requirements.txt`.
3. Push to a public GitHub repository. Streamlit Cloud's free tier requires the app repository to be public.

## 2. Connect Streamlit Cloud

1. Go to https://share.streamlit.io/.
2. Choose **New app**.
3. Select the public GitHub repository and branch.
4. Set the main file path to `app.py`.
5. Deploy.

## 3. Secrets

No Streamlit secrets are required for the portfolio demo. The app uses existing local CSVs when present and falls back to the lightweight summary CSVs in `docs/portfolio/data/`. It does not refetch OpenStreetMap or call external APIs.

## 4. Verify The Live URL

After deployment:

1. Open the generated Streamlit Cloud URL.
2. Confirm the sidebar disclaimer is visible.
3. Confirm all four tabs render: Top Candidates, Sensitivity Analysis, Methodology, Coverage Map.
4. Confirm the app states that Phase 5 is in progress and that outputs are illustrative.
5. Add the final URL to `README.md` under **Live Demo**.
