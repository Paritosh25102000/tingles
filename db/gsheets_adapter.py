"""
Google Sheets database adapter.
Implements the DatabaseAdapter interface using Google Sheets as the backend.
"""

import streamlit as st
import pandas as pd
from typing import Optional, Dict, Tuple
from pathlib import Path
import math
from .base import DatabaseAdapter


class GoogleSheetsAdapter(DatabaseAdapter):
    """Google Sheets implementation of the database adapter."""

    def __init__(self):
        """Initialize Google Sheets connection."""
        self.conn = None
        self.gspread_client = None
        self.gspread_sh = None
        self.gspread_ws = None
        self.credentials_ws = None
        self.suggestions_ws = None

        # Try to use Streamlit's connection API
        try:
            self.conn = st.connection("gsheets", type="gsheets")
        except Exception:
            self.conn = None

        # Initialize gspread as fallback
        self._init_gspread()

    def _init_gspread(self):
        """Initialize gspread client from secrets (st.secrets on Cloud, or .streamlit/secrets.toml locally)."""
        # Return early if already initialized
        if self.gspread_ws is not None:
            return True, "ok"

        try:
            import gspread
        except Exception:
            return False, "gspread package not installed"

        # Try to get secrets - multiple formats supported
        spreadsheet = None
        creds = None

        # Method 1: Try st.secrets directly (Streamlit Cloud format)
        try:
            # Check for connections.gsheets format (used by st.connection)
            if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
                gsheets_secrets = st.secrets["connections"]["gsheets"]
                spreadsheet = gsheets_secrets.get("spreadsheet")
                # Service account creds are usually at root level alongside connections
                creds = {k: v for k, v in st.secrets.items() if k not in ("connections", "spreadsheet", "db_backend")}
                # Or they might be nested
                if not creds or "type" not in creds:
                    if "service_account" in gsheets_secrets:
                        creds = dict(gsheets_secrets["service_account"])
            # Check for flat format (spreadsheet + service account at root)
            elif "spreadsheet" in st.secrets:
                spreadsheet = st.secrets["spreadsheet"]
                creds = {k: v for k, v in st.secrets.items() if k not in ("spreadsheet", "db_backend", "supabase")}
            # Check for type key (service account JSON directly at root)
            elif "type" in st.secrets:
                creds = {k: v for k, v in st.secrets.items() if k not in ("db_backend", "supabase")}
                # spreadsheet might be in a different key
                spreadsheet = st.secrets.get("spreadsheet") or st.secrets.get("sheet_url")
        except Exception:
            pass

        # Method 2: Fallback to local secrets.toml file
        if not spreadsheet or not creds:
            try:
                import toml
                p = Path(".streamlit/secrets.toml")
                if p.exists():
                    data = toml.loads(p.read_text())
                    if "connections" in data and "gsheets" in data["connections"]:
                        gsheets_data = data["connections"]["gsheets"]
                        spreadsheet = spreadsheet or gsheets_data.get("spreadsheet")
                        creds = creds or {k: v for k, v in data.items() if k not in ("connections", "spreadsheet", "db_backend")}
                    else:
                        spreadsheet = spreadsheet or data.get("spreadsheet")
                        creds = creds or {k: v for k, v in data.items() if k not in ("spreadsheet", "db_backend", "supabase")}
            except Exception:
                pass

        if not spreadsheet:
            return False, "no spreadsheet URL found"

        if not creds or "type" not in creds:
            return False, f"no service account credentials found"

        try:
            self.gspread_client = gspread.service_account_from_dict(creds)
            self.gspread_sh = self.gspread_client.open_by_url(spreadsheet)
            # Try to get "profiles" sheet (renamed from Sheet1)
            try:
                self.gspread_ws = self.gspread_sh.worksheet("profiles")
            except Exception:
                # Fallback to Sheet1 if profiles doesn't exist
                try:
                    self.gspread_ws = self.gspread_sh.worksheet("Sheet1")
                except Exception:
                    self.gspread_ws = self.gspread_sh.sheet1
        except Exception as e:
            return False, f"gspread init failed: {e}"

        # Try to get credentials sheet
        try:
            self.credentials_ws = self.gspread_sh.worksheet("credentials")
        except Exception:
            try:
                self.credentials_ws = self.gspread_sh.worksheet("Credentials")
            except Exception:
                # Try to create it
                try:
                    self.credentials_ws = self.gspread_sh.add_worksheet(title="credentials", rows=100, cols=3)
                    self.credentials_ws.append_row(["email", "password", "role"])
                except Exception:
                    pass

        # Initialize Suggestions sheet
        try:
            self.suggestions_ws = self.gspread_sh.worksheet("Suggestions")
        except Exception:
            try:
                self.suggestions_ws = self.gspread_sh.worksheet("suggestions")
            except Exception:
                try:
                    self.suggestions_ws = self.gspread_sh.add_worksheet(title="Suggestions", rows=1000, cols=5)
                    self.suggestions_ws.append_row(["Suggested_To_Email", "Profile_Of_Email", "Status"])
                except Exception:
                    # Non-fatal: suggestions sheet is optional for backward compat
                    self.suggestions_ws = None

        return True, "ok"

    # ============ PROFILE OPERATIONS ============

    def load_profiles(self, force_refresh: bool = False) -> Optional[pd.DataFrame]:
        """Load all profiles from Google Sheets."""
        if self.conn is not None:
            try:
                # Use ttl=0 to bypass cache if force_refresh requested
                if force_refresh:
                    df = self.conn.read(ttl=0)
                else:
                    df = self.conn.read()
                if isinstance(df, pd.DataFrame):
                    return df
                return pd.DataFrame(df)
            except Exception as e:
                st.error(f"Failed to read sheet via st.connection: {e}")
                return None

        # Fallback to gspread
        ok, why = self._init_gspread()
        if not ok:
            st.error(f"Could not initialize gspread: {why}")
            return None
        try:
            records = self.gspread_ws.get_all_records()
            return pd.DataFrame(records)
        except Exception as e:
            st.error(f"gspread read failed: {e}")
            return None

    def get_profile_by_email(self, email: str, force_refresh: bool = False) -> Optional[Dict]:
        """Get a single profile by email."""
        profiles_df = self.load_profiles(force_refresh=force_refresh)
        if profiles_df is None or profiles_df.empty:
            return None

        # Find email column - check for common variations
        email_col = None
        email_aliases = ['email', 'email_address', 'emailaddress', 'e-mail', 'user_email', 'useremail']
        for col in profiles_df.columns:
            if col.lower().strip() in email_aliases or 'email' in col.lower():
                email_col = col
                break

        if email_col is None:
            return None

        email_lower = str(email).lower().strip()
        profiles_df['_email_lower'] = profiles_df[email_col].fillna('').astype(str).str.lower().str.strip()
        match = profiles_df[profiles_df['_email_lower'] == email_lower]

        if match.empty:
            return None

        # Convert to dict and handle NaN values
        profile_dict = match.iloc[0].to_dict()
        # Replace NaN/None with empty strings for cleaner display
        cleaned_profile = {}
        for key, value in profile_dict.items():
            if value is None or (isinstance(value, float) and math.isnan(value)):
                cleaned_profile[key] = ''
            else:
                cleaned_profile[key] = str(value).strip() if value else ''

        # Normalize keys to match expected format (handle both lowercase and Pascal case)
        key_mapping = {
            'id': 'ID',
            'email': 'Email',
            'name': 'Name',
            'gender': 'Gender',
            'age': 'Age',
            'height': 'Height',
            'profession': 'Profession',
            'industry': 'Industry',
            'education': 'Education',
            'religion': 'Religion',
            'residency_status': 'Residency_Status',
            'location': 'Location',
            'linkedin_url': 'LinkedIn',
            'linkedin': 'LinkedIn',
            'photo_url': 'PhotoURL',
            'photourl': 'PhotoURL',
            'imageurl': 'ImageURL',
            'bio': 'Bio',
            'status': 'Status',
            'match_stage': 'MatchStage',
            'whatsapp': 'WhatsApp'
        }

        normalized_profile = {}
        for key, value in cleaned_profile.items():
            # Skip computed columns
            if key.startswith('_'):
                continue
            # Normalize the key
            normalized_key = key_mapping.get(key.lower(), key)
            normalized_profile[normalized_key] = value

        return normalized_profile

    def add_profile(self, profile_data: Dict) -> bool:
        """Add a new profile to Google Sheets."""
        if self.conn is not None:
            try:
                # Normalize column names to match sheet headers
                current_df = self.load_profiles()
                if current_df is not None and not current_df.empty:
                    # Map profile_data keys to actual column names (case-insensitive)
                    actual_cols = {col.lower().strip(): col for col in current_df.columns}
                    normalized_dict = {}
                    for key, value in profile_data.items():
                        key_lower = key.lower().strip()
                        if key_lower in actual_cols:
                            # Use the actual column name from the sheet
                            normalized_dict[actual_cols[key_lower]] = value
                        else:
                            # Keep original key if no match found
                            normalized_dict[key] = value
                    self.conn.write(normalized_dict, mode="append")
                else:
                    self.conn.write(profile_data, mode="append")
                return True
            except Exception as e:
                st.error(f"Failed to append via st.connection: {e}")
                return False

        # Fallback: use gspread
        ok, why = self._init_gspread()
        if not ok:
            st.error(f"gspread not initialized: {why}")
            return False
        try:
            # Ensure order matches header if present
            header = self.gspread_ws.row_values(1)
            # Build a small alias map to match common header variants
            alias_map_local = {
                "name": "Name",
                "full_name": "Name",
                "email": "Email",
                "email_address": "Email",
                "photo_url": "PhotoURL",
                "photourl": "PhotoURL",
                "imageurl": "PhotoURL",
                "image_url": "PhotoURL",
                "height": "Height",
                "profession": "Profession",
                "industry": "Industry",
                "education": "Education",
                "religion": "Religion",
                "residency_status": "Residency_Status",
                "residency": "Residency_Status",
                "location": "Location",
                "bio": "Bio",
                "gender": "Gender",
                "age": "Age",
                "linkedin_url": "LinkedIn",
                "linkedin": "LinkedIn",
                "whatsapp": "WhatsApp",
                "status": "Status",
                "match_stage": "MatchStage",
                "matchstage": "MatchStage",
                "phone": "Phone",
                "id": "ID",
            }

            def _get_for_header(h):
                if h in profile_data and profile_data.get(h) not in (None, ""):
                    return profile_data.get(h)
                hl = str(h).strip().lower()
                # Try direct lower-key
                if hl in profile_data and profile_data.get(hl) not in (None, ""):
                    return profile_data.get(hl)
                # Try canonical alias mapping
                canon = alias_map_local.get(hl)
                if canon and canon in profile_data and profile_data.get(canon) not in (None, ""):
                    return profile_data.get(canon)
                # Try common keys
                for k in (hl, canon, h, h.title()):
                    if k and k in profile_data and profile_data.get(k) not in (None, ""):
                        return profile_data.get(k)
                return ""

            values = [_get_for_header(h) for h in header]
            self.gspread_ws.append_row(values)
            return True
        except Exception as e:
            st.error(f"gspread append failed: {e}")
            return False

    def update_profile_by_email(self, email: str, updates: Dict) -> bool:
        """Update specific fields for a profile identified by email."""
        ok, why = self._init_gspread()
        if not ok:
            return False
        try:
            header = self.gspread_ws.row_values(1)
            email_col = None
            for i, h in enumerate(header):
                if h.lower().strip() == 'email':
                    email_col = i + 1
                    break

            if not email_col:
                return False

            # Find row by email
            col_vals = self.gspread_ws.col_values(email_col)
            row_number = None
            for r_idx, v in enumerate(col_vals, start=1):
                if str(v).strip().lower() == str(email).strip().lower():
                    row_number = r_idx
                    break

            if not row_number:
                return False

            # Build case-insensitive column mapping
            col_map = {}
            for col_idx, col_name in enumerate(header, start=1):
                col_map[col_name.lower().strip()] = (col_idx, col_name)

            # Update cells - match both exact case and lowercase
            updates_made = 0
            for update_key, update_value in updates.items():
                # Try exact match first
                if update_key in header:
                    col_idx = header.index(update_key) + 1
                    self.gspread_ws.update_cell(row_number, col_idx, update_value)
                    updates_made += 1
                # Try case-insensitive match
                elif update_key.lower().strip() in col_map:
                    col_idx, actual_name = col_map[update_key.lower().strip()]
                    self.gspread_ws.update_cell(row_number, col_idx, update_value)
                    updates_made += 1

            return updates_made > 0
        except Exception as e:
            st.error(f"Profile update failed: {e}")
            return False

    # ============ CREDENTIAL OPERATIONS ============

    def load_credentials(self) -> Optional[pd.DataFrame]:
        """Load all credentials from Google Sheets."""
        ok, why = self._init_gspread()
        if not ok:
            return None

        if self.credentials_ws is None:
            return None

        try:
            records = self.credentials_ws.get_all_records()
            df = pd.DataFrame(records)
            # Normalize column names - support both 'email' and 'username' columns
            col_lower = {c.lower().strip(): c for c in df.columns}
            if 'email' in col_lower:
                df = df.rename(columns={col_lower['email']: 'email'})
            elif 'username' in col_lower:
                # Treat username as email for backwards compatibility
                df = df.rename(columns={col_lower['username']: 'email'})
            if 'password' in col_lower:
                df = df.rename(columns={col_lower['password']: 'password'})
            if 'role' in col_lower:
                df = df.rename(columns={col_lower['role']: 'role'})
            return df
        except Exception as e:
            return None

    def add_credential(self, email: str, password: str, role: str = "user") -> Tuple[bool, Optional[str]]:
        """Add a new credential to Google Sheets."""
        ok, why = self._init_gspread()
        if not ok or self.credentials_ws is None:
            return False, f"Could not initialize credentials: {why}"

        try:
            # Check if email already exists
            creds_df = self.load_credentials()
            if creds_df is not None and 'email' in creds_df.columns:
                if email.lower().strip() in creds_df['email'].fillna('').astype(str).str.lower().str.strip().values:
                    return False, "Email already registered. Please sign in."

            # Get header to determine column order
            header = self.credentials_ws.row_values(1)
            header_lower = [h.lower().strip() for h in header]

            # Build row values in correct order
            row_values = []
            for h in header_lower:
                if h in ('email', 'username'):
                    row_values.append(email)
                elif h == 'password':
                    row_values.append(password)
                elif h == 'role':
                    row_values.append(role)
                else:
                    row_values.append('')

            self.credentials_ws.append_row(row_values)
            return True, None
        except Exception as e:
            return False, f"Failed to add credential: {e}"

    def authenticate_user(self, email: str, password: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Authenticate a user login attempt."""
        creds_df = self.load_credentials()
        if creds_df is None:
            return False, None, "Could not load credentials"
        if creds_df.empty:
            return False, None, "No users registered. Please sign up first."

        # Normalize email comparison
        email_lower = str(email).strip().lower()

        # Check if email column exists
        if 'email' not in creds_df.columns:
            return False, None, "Credentials sheet missing 'email' column."

        # Create lowercase email column for matching
        creds_df['_email_lower'] = creds_df['email'].fillna('').astype(str).str.lower().str.strip()

        # Find user by email
        user_row = creds_df[creds_df['_email_lower'] == email_lower]

        if user_row.empty:
            return False, None, "Email not found. Please sign up first."

        # Check password
        stored_password = str(user_row.iloc[0].get('password', '')).strip()
        if stored_password != password:
            return False, None, "Incorrect password. Please try again."

        # Get role (default to 'user' if not specified)
        role = str(user_row.iloc[0].get('role', 'user')).strip().lower()
        if not role or role == 'nan':
            role = 'user'

        # Check if founder
        try:
            founder_email = st.secrets.get("founder_email", "founder@tingles.com")
            if email_lower == founder_email.lower().strip():
                role = 'founder'
        except Exception:
            pass

        return True, role, None

    # ============ SUGGESTION OPERATIONS ============

    def load_suggestions(self) -> Optional[pd.DataFrame]:
        """Load all suggestions from Google Sheets."""
        ok, why = self._init_gspread()
        if not ok or self.suggestions_ws is None:
            return None
        try:
            records = self.suggestions_ws.get_all_records()
            return pd.DataFrame(records)
        except Exception:
            return None

    def get_suggestions_for_user(self, user_email: str) -> pd.DataFrame:
        """Get all profiles suggested to a specific user."""
        suggestions_df = self.load_suggestions()
        if suggestions_df is None or suggestions_df.empty:
            return pd.DataFrame()

        # Filter by Suggested_To_Email (case-insensitive)
        user_email_lower = str(user_email).lower().strip()
        user_suggestions = suggestions_df[
            suggestions_df['Suggested_To_Email'].fillna('').astype(str).str.lower().str.strip() == user_email_lower
        ]

        if user_suggestions.empty:
            return pd.DataFrame()

        # Get profile data for each Profile_Of_Email
        profiles_df = self.load_profiles()
        if profiles_df is None or profiles_df.empty:
            return pd.DataFrame()

        # Ensure Email column exists
        if 'Email' not in profiles_df.columns:
            return pd.DataFrame()

        # Create lowercase email column for matching
        profiles_df['_email_lower'] = profiles_df['Email'].fillna('').astype(str).str.lower().str.strip()

        # Get suggested profile emails
        suggested_emails = [str(e).lower().strip() for e in user_suggestions['Profile_Of_Email'].tolist()]

        # Filter profiles to only those suggested
        curated_profiles = profiles_df[profiles_df['_email_lower'].isin(suggested_emails)].copy()

        # Merge suggestion status
        user_suggestions['_profile_lower'] = user_suggestions['Profile_Of_Email'].fillna('').astype(str).str.lower().str.strip()
        curated_profiles = curated_profiles.merge(
            user_suggestions[['_profile_lower', 'Status']].rename(columns={'Status': 'SuggestionStatus'}),
            left_on='_email_lower',
            right_on='_profile_lower',
            how='left'
        )

        # Clean up temp columns
        curated_profiles = curated_profiles.drop(columns=['_email_lower', '_profile_lower'], errors='ignore')

        return curated_profiles

    def add_suggestion(self, suggested_to_email: str, profile_of_email: str, status: str = "Pending") -> bool:
        """Add a new suggestion to Google Sheets."""
        ok, why = self._init_gspread()
        if not ok or self.suggestions_ws is None:
            return False
        try:
            self.suggestions_ws.append_row([suggested_to_email, profile_of_email, status])
            return True
        except Exception as e:
            st.error(f"Failed to add suggestion: {e}")
            return False

    def update_suggestion_status(self, suggested_to_email: str, profile_of_email: str, new_status: str) -> bool:
        """Update the status of a specific suggestion."""
        ok, why = self._init_gspread()
        if not ok or self.suggestions_ws is None:
            return False
        try:
            records = self.suggestions_ws.get_all_records()
            for i, rec in enumerate(records, start=2):  # Start at row 2 (after header)
                if (str(rec.get('Suggested_To_Email', '')).lower().strip() == str(suggested_to_email).lower().strip() and
                    str(rec.get('Profile_Of_Email', '')).lower().strip() == str(profile_of_email).lower().strip()):
                    # Update Status column (column 3)
                    self.suggestions_ws.update_cell(i, 3, new_status)
                    return True
            return False
        except Exception as e:
            st.error(f"Failed to update suggestion: {e}")
            return False

    def suggestion_exists(self, suggested_to_email: str, profile_of_email: str) -> bool:
        """Check if a suggestion already exists."""
        suggestions_df = self.load_suggestions()
        if suggestions_df is None or suggestions_df.empty:
            return False

        existing = suggestions_df[
            (suggestions_df['Suggested_To_Email'].fillna('').astype(str).str.lower().str.strip() == str(suggested_to_email).lower().strip()) &
            (suggestions_df['Profile_Of_Email'].fillna('').astype(str).str.lower().str.strip() == str(profile_of_email).lower().strip())
        ]
        return not existing.empty
