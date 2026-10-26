# SmartBrew AI

SmartBrew AI is a local web prototype for personalized beverage ordering. It includes menu browsing, customization, ingredient checks, order placement, simulated payments, downloadable digital receipts, saved recipes, recommendations, natural-language drink parsing, and an admin inventory/event view.

## Scope and safety

This is a software prototype using local demo data. Payments are simulated and no real card or wallet is charged. NFC, physical machine controls, weather APIs, email delivery, and facial mood analysis are not implemented. Facial images are not captured by this prototype. Do not use the demo credentials or this setup for a production deployment.

## Prerequisites

- Python 3.11.4
- pip
- Git (optional, for repository management)

## Install

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

Streamlit prints the local URL to open in your browser. SQLite creates `smartbrew.db` automatically on first run and seeds demonstration data.

## Demo accounts

- Customer: `customer` / `BrewDemo123!`
- Administrator: `admin` / `AdminDemo123!`

These are public demo credentials and are only suitable for local evaluation. Change them before any non-demo use.

## Demonstrate the 10 selected feature groups

1. **Browse menu:** Sign in as customer; open “Menu & customize” and inspect categories, descriptions, prices, calories, and ingredient status.
2. **Customize drink:** Choose size, milk, strength, temperature, sugar, and syrup shots.
3. **Ingredient availability:** Sign in as admin in another session, set milk stock to zero, then try ordering a Latte as customer. Restore stock afterward.
4. **Place order:** Choose a drink with available ingredients and select “Validate and create order”.
5. **Payment workflow:** Open “Checkout & receipt” and select simulated success or failure. Payment is not real.
6. **Digital receipt:** Complete a successful simulated payment and download the receipt JSON.
7. **Favorites:** Save a custom drink by entering a favorite name in the customization form; inspect “Favorites”.
8. **Recommendations:** Save preferences and inspect ranked drinks.
9. **Natural-language order:** Try “Large hot latte with oat milk and an extra shot”; review the interpreted options before confirming.
10. **Admin inventory and events:** Sign in as admin, update ingredient quantities and thresholds, and inspect recent event logs.

## Tests

```bash
pytest -v
```

Tests use isolated temporary SQLite databases and do not modify the default demo database.

## Architecture

- `app.py`: Streamlit interface.
- `src/database.py`: schema and demo data.
- `src/security.py`: password hashing and verification.
- `src/services.py`: application business logic.
- `tests/`: automated service tests.

## LLM assistance and assignment documentation

The assignment uses ChatGPT — GPT-6 for requirements elicitation and implementation assistance. Include the actual prompts and relevant code-generation/debugging conversation in `docs/llm-transcript.md` or as an appendix in the submitted report. Compare the AI-generated artifacts with the human Assignment 2 submission and document accepted/rejected suggestions.

## Known limitations

- Payment success/failure is simulated.
- Natural-language interpretation is a limited rule-based parser, not a locally hosted LLM.
- Recommendations use simple preference/history scoring.
- Favorites can be saved and loaded; full editing/deletion UI is not implemented.
- Email/QR delivery, real NFC/EMV/digital wallets, weather API, camera-based mood inference, waste-bin sensors, and physical maintenance are not implemented.
- For an academic prototype, admin and customer login are local and use demo accounts; additional production hardening would be required.
