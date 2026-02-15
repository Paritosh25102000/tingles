"""Quick test to verify Supabase connection and credential loading."""

import sys
from pathlib import Path
import toml

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Read secrets
secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
with open(secrets_path, 'r') as f:
    secrets = toml.load(f)

# Initialize Supabase
from supabase import create_client

url = secrets["supabase"]["url"]
key = secrets["supabase"]["key"]
client = create_client(url, key)

print("🔄 Testing Supabase connection...")
print(f"URL: {url}")

# Test credentials table
try:
    response = client.table('credentials').select('*').execute()
    print(f"\n✅ Credentials table accessible")
    print(f"Found {len(response.data)} credentials:")
    for cred in response.data:
        print(f"  - {cred['email']} (role: {cred['role']})")
except Exception as e:
    print(f"\n❌ Error loading credentials: {e}")

# Test profiles table
try:
    response = client.table('profiles').select('*').execute()
    print(f"\n✅ Profiles table accessible")
    print(f"Found {len(response.data)} profiles")
except Exception as e:
    print(f"\n❌ Error loading profiles: {e}")

# Test suggestions table
try:
    response = client.table('suggestions').select('*').execute()
    print(f"\n✅ Suggestions table accessible")
    print(f"Found {len(response.data)} suggestions")
except Exception as e:
    print(f"\n❌ Error loading suggestions: {e}")
