"""
HOW TO INTEGRATE MF ALERTS INTO YOUR EXISTING main.py
======================================================

You have two options:

OPTION A — Run MF scan as part of your existing stock scan (single script)
---------------------------------------------------------------------------
Add these lines to the bottom of your existing main.py, inside run_scan():

    # --- Mutual Fund Dip Scan (runs at end of each scheduled stock scan) ---
    from mf_main import run_mf_scan
    run_mf_scan()

This makes both stock alerts + MF dip alerts fire in the same GitHub Actions run.


OPTION B — Keep MF scan completely separate (recommended)
----------------------------------------------------------
Keep mf_main.py as its own script with its own GitHub Actions workflow
(.github/workflows/mf_scan.yml). This is cleaner because:

  - MF NAVs are published at 6 PM IST — no point running before that
  - Stock scan runs at 9:20 AM and 3:10 PM IST
  - Different schedules = different workflows = no interference

The mf_scan.yml workflow is already set to run at 7:00 PM IST daily.


FOLDER STRUCTURE AFTER INTEGRATION
-----------------------------------
trading_alert_system/
  main.py                            <- existing stock scanner
  mf_main.py                         <- NEW: MF dip scanner
  requirements.txt                   <- add new packages (see below)
  config/
    .env                             <- same file, no new keys needed
    watchlist.yaml                   <- existing stock watchlist
  data/
    fetcher.py                       <- existing
    technical.py                     <- existing
    sentiment.py                     <- existing
    risk.py                          <- existing
    mf_fetcher.py                    <- NEW
    mf_analyser.py                   <- NEW
  alerts/
    telegram_bot.py                  <- existing
    mf_alerts.py                     <- NEW
  .github/
    workflows/
      trading_scan.yml               <- existing stock workflow
      mf_scan.yml                    <- NEW: MF workflow
  logs/
    trading.log                      <- existing
    mf_alerts.log                    <- NEW (auto-created)


PACKAGES TO ADD TO requirements.txt
-------------------------------------
No new packages are needed beyond what you already have installed:
  - requests     (already installed)
  - pandas       (already installed)
  - yfinance     (already installed)
  - python-telegram-bot (already installed)
  - python-dotenv (already installed)

All MF data comes from mfapi.in which is a free REST API — no extra library.


FINDING SCHEME CODES FOR OTHER FUNDS
--------------------------------------
To find the mfapi.in scheme code for any mutual fund:

  1. Open in browser:
     https://api.mfapi.in/mf/search?q=Parag+Parikh+Flexi+Cap

  2. The response is a JSON list. Find the exact fund name and copy its
     schemeCode number.

  3. Add it to FUND_REGISTRY in data/mf_fetcher.py like this:

     "MY_NEW_FUND": {
         "scheme_code":             123456,
         "name":                    "Fund Name - Direct Plan - Growth",
         "category":                "Mid Cap",
         "benchmark_index":         "NIFTY_MIDCAP150",
         "correction_threshold_pct": 15,
     },


VERIFYING SCHEME CODES (IMPORTANT)
------------------------------------
The scheme codes in mf_fetcher.py are sourced from public registries and
are accurate as of May 2026. However, AMFI occasionally reassigns codes
when fund houses merge or rename schemes.

To verify any code, paste this URL in your browser:
  https://api.mfapi.in/mf/<scheme_code>/latest

You should see the fund name and latest NAV. If not, use the /mf/search
endpoint above to find the correct current code.


TESTING LOCALLY
-----------------
  cd trading_alert_system
  venv\\Scripts\\activate          # Windows
  python mf_main.py

You should see log output and receive a Telegram summary message.
"""

# This file is documentation only — not executable.
# Place it in your project root as INTEGRATION_NOTES.py or README_MF.py.
