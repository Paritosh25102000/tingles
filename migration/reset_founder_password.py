"""
Script to reset founder password in Supabase.
This script reads credentials from secrets.toml (NOT hardcoded).
"""

import sys
from pathlib import Path
import toml
import getpass

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    print("\n" + "=" * 60)
    print("RESET FOUNDER PASSWORD IN SUPABASE")
    print("=" * 60)

    # Read secrets
    print("\n🔄 Reading secrets.toml...")
    secrets_path = Path(__file__).parent.parent / ".streamlit" / "secrets.toml"

    try:
        with open(secrets_path, 'r') as f:
            secrets = toml.load(f)
        print("✅ Secrets loaded")
    except Exception as e:
        print(f"❌ Failed to read secrets.toml: {e}")
        return

    # Get founder email from secrets
    founder_email = secrets.get('founder_email', 'suman.lal@tins.com')

    # Prompt for new password (not hardcoded!)
    print(f"\n📧 Founder email: {founder_email}")
    new_password = getpass.getpass("🔑 Enter NEW password for founder account: ")
    confirm_password = getpass.getpass("🔑 Confirm NEW password: ")

    if new_password != confirm_password:
        print("❌ Passwords don't match. Aborting.")
        return

    if len(new_password) < 8:
        print("❌ Password must be at least 8 characters. Aborting.")
        return

    # Initialize Supabase client
    print("\n🔄 Connecting to Supabase...")
    try:
        from supabase import create_client
        url = secrets["supabase"]["url"]
        key = secrets["supabase"]["key"]
        client = create_client(url, key)
        print("✅ Connected to Supabase")
    except Exception as e:
        print(f"❌ Failed to connect to Supabase: {e}")
        return

    # Update password
    print(f"\n🔄 Updating password for {founder_email}...")

    try:
        response = client.table('credentials').update({
            'password': new_password
        }).eq('email', founder_email.lower().strip()).execute()

        if response.data:
            print(f"✅ Password updated successfully!")
            print(f"\n🎉 You can now login with:")
            print(f"   Email: {founder_email}")
            print(f"   Password: <your new password>")
        else:
            print(f"❌ No credential found for {founder_email}")
            print("   You may need to create the founder account first.")
    except Exception as e:
        print(f"❌ Error updating password: {e}")

    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
