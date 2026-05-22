# Recruiter Brief

**ChargeNet Europe is a decision-support tool for analysts screening where EV charging expansion deserves deeper diligence.**

- Turns public OpenStreetMap, Eurostat population, and GISCO regional-boundary data into ranked candidate-site shortlists across Belgium, Germany, France, and the Netherlands.
- Compares four baseline scoring factors: coverage, data quality, rollout risk, and competition proxy.
- Adds optimization with mixed-integer linear programming to test whether a portfolio of sites covers more unique demand than simply picking the highest-ranked locations.

- Non-obvious finding: in the aggressive-radius scenario, the simple top-10 baseline shortlist covered 8 zones, while the optimization run covered 120 zones under the same 10-site limit. The lesson is that "best individual sites" can overlap heavily; a portfolio method can spread coverage better.

Stack: Python, pandas, PuLP/CBC, Streamlit, OpenStreetMap Overpass, Eurostat, GISCO NUTS3, matplotlib, CSV marts, Power BI-ready exports.

What this is NOT: this is not an investment recommendation or a real site rollout plan. It does not model grid capacity, permits, land control, traffic flows, charger utilization, negotiated capital expenditure, or time-of-day demand. It is a public-data diligence layer built to show how I structure messy data, test assumptions, and communicate limits honestly.

Live demo: [chargenet-europe.streamlit.app](https://chargenet-europe.streamlit.app)

GitHub: [github.com/tasohub/chargenet-europe](https://github.com/tasohub/chargenet-europe)

Time to read: about 60 seconds.
