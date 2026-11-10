# BloodBeacon — Emergency Blood-Donor Activation System

A college project for an emergency blood-donor activation system that finds eligible donors nearby, predicts who is most likely to show up, and alerts them on WhatsApp in waves.

## Quick Start

1. Clone the repo and create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up Supabase credentials (see SUPABASE_SETUP.md for details):
   ```bash
   cp .env.example .env
   # Edit .env with your Supabase URL and service key
   ```

4. Run the app locally:
   ```bash
   PORT=5001 python app.py
   ```

Visit `http://localhost:5001` to access the app.

## Project Structure

- `app.py` — Main Flask application
- `db.py` — Single database access module for Supabase
- `schema.sql` — Database schema (run in Supabase SQL editor)
- `seed.py` — Seed script for test data
- `templates/` — Jinja2 HTML templates
- `tests/` — Test suite

## Stages

This project is built in 6 stages. See `BLOODBEACON_STATUS.md` for the current stage and progress.

## License

College project.
