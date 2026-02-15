"""Test which backend is being selected."""

import streamlit as st
import toml
from pathlib import Path

# Manually load secrets to debug
secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
with open(secrets_path, 'r') as f:
    secrets = toml.load(f)

print(f"db_backend in secrets.toml: '{secrets.get('db_backend', 'NOT FOUND')}'")

# Now test with Streamlit secrets (requires running in Streamlit context)
# This won't work outside Streamlit, just showing the code
