# FoodWise AI

**An intelligent food ordering, meal planning, demand insight, inventory, and surplus rescue platform.** Built with Python, Flask, Flask-SQLAlchemy, SQLite, Pandas, scikit-learn, Bootstrap, JavaScript, and Chart.js.

## Current implementation

- Registration/login with Werkzeug password hashing, session-based CSRF checks for state-changing requests, and customer, restaurant, and community organization roles.
- SQLite models for users, restaurants, food items, meal preferences, orders, order lines, inventory, demand history, surplus listings, donation requests, and reviews.
- Menu search/filtering, menu administration, local browser cart, server-side price/availability checks, COD and explicitly simulated payment, order history/details, and restaurant order status updates.
- Explainable recommendation rules using diet, cuisine, meal type, budget, disliked ingredients, and declared allergens. Allergen exclusion depends on complete and accurate menu records; users should verify directly with restaurants.
- Server-calculated smart budget planner using available menu items and a deterministic, price-first combination.
- Restaurant inventory records with low-stock and upcoming-expiry warnings based on entered data.
- Demand dashboard: item-level recent-mean baselines; daily Random Forest model only when enough dated observations exist. It does not claim validated accuracy. Seeded history is synthetic and labelled as demo data.
- Surplus listings and organization donation requests, with restaurant acceptance/decline/collection status and deadlines. Food safety is not automatically verified.
- Rules-based text assistant with vegetarian, budget, recorded peanut-allergen, cuisine, meal-type, and popular-item handling. No paid AI API required.
- Food scanner upload interface. **Classification is not implemented** because no pretrained model/weights are bundled or verified; it explicitly reports that limitation instead of fabricating predictions.
- Responsive dark navy/green/orange UI with Bootstrap and Chart.js.

## Requirements and setup

Python 3.10+ recommended.

```bash
cd foodwise-ai
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env`, set a long random `SECRET_KEY`, and optionally set `DATABASE_URL`. Then:

```bash
python app.py
```

Open http://127.0.0.1:5000. The SQLite database is created automatically and clearly labelled demo records are seeded on first launch. To reset demo data, stop the app and delete the SQLite database in the instance directory, then restart.

### Demo accounts

All seeded demo accounts use `Foodwise123!` (change before any public deployment):

- Customer: `customer@foodwise.demo`
- Restaurant administrator: `restaurant@foodwise.demo`
- Community organization: `community@foodwise.demo`

The organization account is pre-verified for the hackathon demo. Newly registered organization accounts are unverified and cannot request donations until an administrator-verification workflow is implemented; only the seeded demo community account is pre-verified.

## Tests

```bash
pytest -q
```

Tests cover rendering, password hashing, recommendation allergen filtering, server-side checkout totals, payment labelling, role boundaries, and assistant budget constraints.

## Demo sequence for judges (4–6 minutes)

1. **Customer:** sign in and open the menu; search/filter; inspect ingredients/allergen fields.
2. **Personalization:** set vegetarian, peanuts, budget, cuisine, and meal type; explain why recommendations appear.
3. **Budget planner:** build a dinner under ₹200 and show the backend-enforced total and remaining amount.
4. **Ordering:** add two items, modify quantities, choose simulated payment, and show the confirmation/order history.
5. **Restaurant:** sign in as restaurant; add/toggle a menu item; update inventory quantity; show low-stock/expiry signals.
6. **Forecast:** open demand forecasting and explain the synthetic history and unvalidated baseline/ML estimate honestly.
7. **Food rescue:** publish or inspect a surplus listing; sign in as community organization and request a quantity; return as restaurant to accept/decline and mark collection.
8. **Assistant/scanner:** ask “Recommend a vegetarian dinner under ₹200”; show results; open scanner and explain model is not configured rather than claiming computer vision works.

## Hackathon pitch

Food delivery apps optimize discovery and dispatch. FoodWise AI optimizes the **decision and resource loop around a meal**: preference-aware recommendations and budget planning for customers, demand and inventory signals for kitchens, and a surplus-to-community workflow to reduce avoidable waste. The demo prioritizes transparent, reproducible rules over unsupported AI claims.

## Limitations and production hardening

- No pretrained food image classifier is included. To enable this module, choose a licensed food dataset/model, pin the model version, implement preprocessing/inference, evaluate it, and show calibrated uncertainty. Upload currently checks that a file was supplied but does not run classification.
- The chat assistant is deterministic text/rule parsing, not an LLM and not speech recognition.
- The forecast is an operational demo, not a validated forecasting system. Synthetic seeded demand must be replaced with real POS history and evaluated with a chronological holdout before operational use.
- Menu allergen/ingredient records may be incomplete. The platform does not provide medical advice and cannot guarantee allergy safety.
- Inventory expiry dates are reminders, not safety certification. Donation partners must verify handling and local food-safety requirements.
- Payments are not processed; “Simulated Payment” is a demo status only.
- Demo database seeding is enabled by default. Set `SEED_DEMO=False` in deployment config or adapt the factory before production.
- For production: add rate limiting, email verification and organization approval, secure session-cookie settings, audit logs, pagination, migrations, backups, accessibility review, and tests against concurrent inventory/order changes. Serve behind HTTPS, set `COOKIE_SECURE=1`, and set secrets via environment variables.
- External Unsplash imagery, Google Fonts, Bootstrap, icons, and Chart.js use CDNs and require internet access in the browser. Local fallback styling is available, but imagery and chart libraries may not load offline.
