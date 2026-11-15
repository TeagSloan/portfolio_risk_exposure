#!/usr/bin/env bash
# Starts the Monad Blitz demo dashboard (demo_app.py) with its dark theme.
# The theme is passed here instead of in .streamlit/config.toml so app.py keeps its own look.
cd "$(dirname "$0")"
exec streamlit run demo_app.py \
  --theme.base dark \
  --theme.primaryColor "#6E5CE6" \
  --theme.backgroundColor "#0E0F14" \
  --theme.secondaryBackgroundColor "#171922" \
  --theme.textColor "#F2F3F7" \
  "$@"
