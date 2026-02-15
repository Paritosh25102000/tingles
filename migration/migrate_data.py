"""
One-time migration script to copy data from Google Sheets to Supabase.

Usage:
    python migration/migrate_data.py

Prerequisites:
    1. Supabase project created with tables (profiles, credentials, suggestions)
    2. .streamlit/secrets.toml configured with both Google Sheets and Supabase credentials
    3. db_backend set to "gsheets" temporarily to read from Google Sheets

This script will:
    1. Read all data from Google Sheets (profiles, credentials, suggestions)
    2. Write all data to Supabase
    3. Report success/failure for each record
"""

import sys
from pathlib import Path

# Add parent directory to path to import from db module
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from db.gsheets_adapter import GoogleSheetsAdapter
from db.supabase_adapter import SupabaseAdapter


def migrate_profiles(gsheets: GoogleSheetsAdapter, supabase: SupabaseAdapter) -> tuple[int, int]:
    """Migrate all profiles from Google Sheets to Supabase."""
    print("\n" + "=" * 60)
    print("MIGRATING PROFILES")
    print("=" * 60)

    profiles_df = gsheets.load_profiles()
    if profiles_df is None or profiles_df.empty:
        print("⚠️  No profiles found in Google Sheets")
        return 0, 0

    total = len(profiles_df)
    success_count = 0
    error_count = 0

    for idx, row in profiles_df.iterrows():
        profile_dict = row.to_dict()
        email = profile_dict.get('Email', 'Unknown')

        try:
            if supabase.add_profile(profile_dict):
                success_count += 1
                print(f"✅ [{success_count}/{total}] Migrated profile: {email}")
            else:
                error_count += 1
                print(f"❌ [{success_count + error_count}/{total}] Failed to migrate profile: {email}")
        except Exception as e:
            error_count += 1
            print(f"❌ [{success_count + error_count}/{total}] Error migrating {email}: {e}")

    print(f"\n📊 Profiles Summary: {success_count} succeeded, {error_count} failed out of {total} total")
    return success_count, error_count


def migrate_credentials(gsheets: GoogleSheetsAdapter, supabase: SupabaseAdapter) -> tuple[int, int]:
    """Migrate all credentials from Google Sheets to Supabase."""
    print("\n" + "=" * 60)
    print("MIGRATING CREDENTIALS")
    print("=" * 60)

    creds_df = gsheets.load_credentials()
    if creds_df is None or creds_df.empty:
        print("⚠️  No credentials found in Google Sheets")
        return 0, 0

    total = len(creds_df)
    success_count = 0
    error_count = 0

    for idx, row in creds_df.iterrows():
        email = row.get('email', 'Unknown')
        password = row.get('password', '')
        role = row.get('role', 'user')

        try:
            success, error_msg = supabase.add_credential(email, password, role)
            if success:
                success_count += 1
                print(f"✅ [{success_count}/{total}] Migrated credential: {email}")
            else:
                error_count += 1
                print(f"❌ [{success_count + error_count}/{total}] Failed to migrate credential: {email} - {error_msg}")
        except Exception as e:
            error_count += 1
            print(f"❌ [{success_count + error_count}/{total}] Error migrating {email}: {e}")

    print(f"\n📊 Credentials Summary: {success_count} succeeded, {error_count} failed out of {total} total")
    return success_count, error_count


def migrate_suggestions(gsheets: GoogleSheetsAdapter, supabase: SupabaseAdapter) -> tuple[int, int]:
    """Migrate all suggestions from Google Sheets to Supabase."""
    print("\n" + "=" * 60)
    print("MIGRATING SUGGESTIONS")
    print("=" * 60)

    suggestions_df = gsheets.load_suggestions()
    if suggestions_df is None or suggestions_df.empty:
        print("⚠️  No suggestions found in Google Sheets")
        return 0, 0

    total = len(suggestions_df)
    success_count = 0
    error_count = 0

    for idx, row in suggestions_df.iterrows():
        suggested_to = row.get('Suggested_To_Email', 'Unknown')
        profile_of = row.get('Profile_Of_Email', 'Unknown')
        status = row.get('Status', 'Pending')

        try:
            if supabase.add_suggestion(suggested_to, profile_of, status):
                success_count += 1
                print(f"✅ [{success_count}/{total}] Migrated suggestion: {suggested_to} → {profile_of}")
            else:
                error_count += 1
                print(f"❌ [{success_count + error_count}/{total}] Failed to migrate suggestion: {suggested_to} → {profile_of}")
        except Exception as e:
            error_count += 1
            print(f"❌ [{success_count + error_count}/{total}] Error migrating {suggested_to} → {profile_of}: {e}")

    print(f"\n📊 Suggestions Summary: {success_count} succeeded, {error_count} failed out of {total} total")
    return success_count, error_count


def main():
    """Run the complete migration from Google Sheets to Supabase."""
    print("\n" + "=" * 60)
    print("TINGLES DATABASE MIGRATION: Google Sheets → Supabase")
    print("=" * 60)

    # Initialize adapters
    print("\n🔄 Initializing database connections...")
    try:
        gsheets = GoogleSheetsAdapter()
        print("✅ Google Sheets adapter initialized")
    except Exception as e:
        print(f"❌ Failed to initialize Google Sheets adapter: {e}")
        print("\n💡 Make sure .streamlit/secrets.toml has Google Sheets credentials")
        return

    try:
        supabase = SupabaseAdapter()
        print("✅ Supabase adapter initialized")
    except Exception as e:
        print(f"❌ Failed to initialize Supabase adapter: {e}")
        print("\n💡 Make sure .streamlit/secrets.toml has Supabase credentials:")
        print("   [supabase]")
        print("   url = \"https://your-project.supabase.co\"")
        print("   key = \"your-anon-key\"")
        return

    # Track overall stats
    total_success = 0
    total_errors = 0

    # Migrate profiles
    success, errors = migrate_profiles(gsheets, supabase)
    total_success += success
    total_errors += errors

    # Migrate credentials
    success, errors = migrate_credentials(gsheets, supabase)
    total_success += success
    total_errors += errors

    # Migrate suggestions
    success, errors = migrate_suggestions(gsheets, supabase)
    total_success += success
    total_errors += errors

    # Final summary
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE!")
    print("=" * 60)
    print(f"✅ Total records migrated successfully: {total_success}")
    print(f"❌ Total records failed: {total_errors}")

    if total_errors == 0:
        print("\n🎉 All records migrated successfully!")
    else:
        print(f"\n⚠️  {total_errors} records failed to migrate. Please review errors above.")

    print("\n" + "=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    print("1. ✅ Verify data in Supabase dashboard (https://app.supabase.com)")
    print("2. ✅ Update .streamlit/secrets.toml: db_backend = \"supabase\"")
    print("3. ✅ Test the app locally with: streamlit run app.py")
    print("4. ✅ If everything works, deploy to Streamlit Cloud")
    print("5. ✅ Update Streamlit Cloud secrets: db_backend = \"supabase\"")
    print("\n💡 To rollback: change db_backend back to \"gsheets\" in secrets")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
