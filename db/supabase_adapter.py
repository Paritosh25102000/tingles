"""
Supabase database adapter.
Implements the DatabaseAdapter interface using Supabase PostgreSQL as the backend.
"""

import streamlit as st
import pandas as pd
from typing import Optional, Dict, Tuple
from .base import DatabaseAdapter


class SupabaseAdapter(DatabaseAdapter):
    """Supabase implementation of the database adapter."""

    def __init__(self):
        """Initialize Supabase client from secrets."""
        self.client = self._init_client()

    def _init_client(self):
        """Initialize Supabase client from st.secrets."""
        try:
            from supabase import create_client, Client
        except ImportError:
            st.error("supabase package not installed. Run: pip install supabase")
            return None

        try:
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"]["key"]
            return create_client(url, key)
        except Exception as e:
            st.error(f"Failed to initialize Supabase client: {e}")
            return None

    def _normalize_profile_keys(self, profile: Dict) -> Dict:
        """Convert database column names (snake_case) to app format (PascalCase)."""
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
            'photo_url': 'PhotoURL',
            'bio': 'Bio',
            'whatsapp': 'WhatsApp',
            'status': 'Status',
            'match_stage': 'MatchStage',
            'created_at': 'CreatedAt',
            'updated_at': 'UpdatedAt'
        }

        normalized = {}
        for key, value in profile.items():
            if key in key_mapping:
                # Handle NULL values - convert to empty strings for UI compatibility
                if value is None:
                    normalized[key_mapping[key]] = ''
                else:
                    normalized[key_mapping[key]] = str(value).strip() if value else ''

        return normalized

    def _convert_to_db_format(self, data: Dict) -> Dict:
        """Convert app format (PascalCase) to database format (snake_case)."""
        key_mapping = {
            'ID': 'id',
            'Email': 'email',
            'Name': 'name',
            'Gender': 'gender',
            'Age': 'age',
            'Height': 'height',
            'Profession': 'profession',
            'Industry': 'industry',
            'Education': 'education',
            'Religion': 'religion',
            'Residency_Status': 'residency_status',
            'Location': 'location',
            'LinkedIn': 'linkedin_url',
            'PhotoURL': 'photo_url',
            'Bio': 'bio',
            'WhatsApp': 'whatsapp',
            'Status': 'status',
            'MatchStage': 'match_stage'
        }

        db_data = {}
        for key, value in data.items():
            db_key = key_mapping.get(key, key.lower())
            # Convert age to integer if present
            if db_key == 'age' and value and str(value).strip():
                try:
                    db_data[db_key] = int(value)
                except:
                    db_data[db_key] = None
            else:
                # Convert empty strings to None for database
                db_data[db_key] = value if value else None

        return db_data

    # ============ PROFILE OPERATIONS ============

    @st.cache_data(ttl=60)
    def load_profiles(_self, force_refresh: bool = False) -> Optional[pd.DataFrame]:
        """
        Load all profiles from Supabase.
        Cached for 60 seconds. Use force_refresh=True to bypass cache.
        """
        if _self.client is None:
            return None

        try:
            response = _self.client.table('profiles').select('*').execute()
            if response.data:
                df = pd.DataFrame(response.data)
                # Normalize column names to match Google Sheets format
                df = df.rename(columns={
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
                    'photo_url': 'PhotoURL',
                    'bio': 'Bio',
                    'whatsapp': 'WhatsApp',
                    'status': 'Status',
                    'match_stage': 'MatchStage'
                })
                # Fill NaN with empty strings
                df = df.fillna('')
                return df
            return pd.DataFrame()
        except Exception as e:
            st.error(f"Failed to load profiles from Supabase: {e}")
            return None

    def get_profile_by_email(self, email: str, force_refresh: bool = False) -> Optional[Dict]:
        """Get a single profile by email from Supabase."""
        if self.client is None:
            return None

        try:
            response = self.client.table('profiles').select('*').eq('email', email.lower().strip()).execute()

            if not response.data or len(response.data) == 0:
                return None

            # Normalize keys to match Google Sheets format (PascalCase)
            profile = response.data[0]
            normalized = self._normalize_profile_keys(profile)
            return normalized
        except Exception as e:
            st.error(f"Failed to get profile from Supabase: {e}")
            return None

    def add_profile(self, profile_data: Dict) -> bool:
        """Add a new profile to Supabase."""
        if self.client is None:
            return False

        try:
            # Convert PascalCase keys to snake_case for database
            db_data = self._convert_to_db_format(profile_data)

            # Remove 'id' if present - it's auto-generated
            db_data.pop('id', None)

            response = self.client.table('profiles').insert(db_data).execute()

            # Clear cache after write
            st.cache_data.clear()

            return bool(response.data)
        except Exception as e:
            st.error(f"Failed to add profile to Supabase: {e}")
            return False

    def update_profile_by_email(self, email: str, updates: Dict) -> bool:
        """Update profile fields in Supabase."""
        if self.client is None:
            return False

        try:
            # Convert updates to database format
            db_updates = self._convert_to_db_format(updates)

            response = self.client.table('profiles').update(db_updates).eq('email', email.lower().strip()).execute()

            # Clear cache after write
            st.cache_data.clear()

            return bool(response.data)
        except Exception as e:
            st.error(f"Failed to update profile in Supabase: {e}")
            return False

    # ============ CREDENTIAL OPERATIONS ============

    def load_credentials(self) -> Optional[pd.DataFrame]:
        """Load all credentials from Supabase."""
        if self.client is None:
            return None

        try:
            response = self.client.table('credentials').select('*').execute()
            if response.data:
                df = pd.DataFrame(response.data)
                # Ensure column names match Google Sheets format
                df = df.rename(columns={'email': 'email', 'password': 'password', 'role': 'role'})
                return df
            return pd.DataFrame()
        except Exception as e:
            st.error(f"Failed to load credentials from Supabase: {e}")
            return None

    def add_credential(self, email: str, password: str, role: str = "user") -> Tuple[bool, Optional[str]]:
        """Add a new credential to Supabase."""
        if self.client is None:
            return False, "Supabase client not initialized"

        try:
            # Check if email exists
            existing = self.client.table('credentials').select('email').eq('email', email.lower().strip()).execute()
            if existing.data and len(existing.data) > 0:
                return False, "Email already registered. Please sign in."

            # Insert credential
            data = {
                'email': email.lower().strip(),
                'password': password,
                'role': role
            }
            response = self.client.table('credentials').insert(data).execute()
            return bool(response.data), None
        except Exception as e:
            return False, f"Failed to add credential: {e}"

    def authenticate_user(self, email: str, password: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Authenticate user against Supabase credentials."""
        if self.client is None:
            return False, None, "Database not initialized"

        try:
            email_lower = email.lower().strip()

            # Get credential
            response = self.client.table('credentials').select('*').eq('email', email_lower).execute()

            if not response.data or len(response.data) == 0:
                return False, None, "Email not found. Please sign up first."

            user = response.data[0]

            # Check if this is an OAuth user (no password)
            if user.get('auth_provider') and user.get('auth_provider') != 'email':
                return False, None, f"This account uses {user.get('auth_provider')} login. Please use the {user.get('auth_provider')} button."

            # Check password
            if user['password'] != password:
                return False, None, "Incorrect password. Please try again."

            # Get role
            role = user.get('role', 'user')

            # Check if founder
            try:
                founder_email = st.secrets.get("founder_email", "founder@tingles.com")
                if email_lower == founder_email.lower().strip():
                    role = 'founder'
            except Exception:
                pass

            return True, role, None
        except Exception as e:
            return False, None, f"Authentication failed: {e}"

    def get_or_create_oauth_user(self, email: str, name: str, provider: str, oauth_id: str = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Get or create user from OAuth provider.
        Returns (success, role, error_msg).
        """
        if self.client is None:
            return False, None, "Database not initialized"

        try:
            email_lower = email.lower().strip()

            # Check if user already exists
            response = self.client.table('credentials').select('*').eq('email', email_lower).execute()

            if response.data and len(response.data) > 0:
                # User exists - verify they use the same provider or email
                existing_user = response.data[0]
                existing_provider = existing_user.get('auth_provider', 'email')

                # Allow login if same provider or if converting from email to OAuth
                if existing_provider == provider or existing_provider == 'email':
                    # Update to OAuth if they were email-only
                    if existing_provider == 'email' and provider in ['google', 'linkedin']:
                        self.client.table('credentials').update({
                            'auth_provider': provider,
                            'oauth_id': oauth_id
                        }).eq('email', email_lower).execute()

                    # Get role
                    role = existing_user.get('role', 'user')

                    # Check if founder
                    try:
                        founder_email = st.secrets.get("founder_email", "founder@tingles.com")
                        if email_lower == founder_email.lower().strip():
                            role = 'founder'
                    except Exception:
                        pass

                    return True, role, None
                else:
                    return False, None, f"This email is registered with {existing_provider}. Please use that login method."

            # Create new OAuth user
            data = {
                'email': email_lower,
                'password': None,  # OAuth users don't have passwords
                'role': 'user',
                'auth_provider': provider,
                'oauth_id': oauth_id
            }
            response = self.client.table('credentials').insert(data).execute()

            if not response.data:
                return False, None, "Failed to create user account."

            # Create profile with name from OAuth
            # First check if profile already exists
            profile_response = self.client.table('profiles').select('*').eq('email', email_lower).execute()

            if not profile_response.data or len(profile_response.data) == 0:
                # Get next ID
                all_profiles = self.client.table('profiles').select('id').execute()
                existing_ids = [p.get('id', 0) for p in all_profiles.data] if all_profiles.data else []
                next_id = max(existing_ids) + 1 if existing_ids else 1

                # Create basic profile
                profile_data = {
                    'id': next_id,
                    'email': email_lower,
                    'name': name,
                    'status': 'Single'
                }
                self.client.table('profiles').insert(profile_data).execute()

            return True, 'user', None

        except Exception as e:
            return False, None, f"OAuth authentication failed: {e}"

    # ============ SUGGESTION OPERATIONS ============

    def load_suggestions(self) -> Optional[pd.DataFrame]:
        """Load all suggestions from Supabase."""
        if self.client is None:
            return None

        try:
            response = self.client.table('suggestions').select('*').execute()
            if response.data:
                df = pd.DataFrame(response.data)
                # Rename columns to match Google Sheets format
                column_mapping = {
                    'suggested_to_email': 'Suggested_To_Email',
                    'profile_of_email': 'Profile_Of_Email',
                    'status': 'Status'
                }
                df = df.rename(columns=column_mapping)
                return df
            return pd.DataFrame()
        except Exception as e:
            st.error(f"Failed to load suggestions from Supabase: {e}")
            return None

    def get_suggestions_for_user(self, user_email: str) -> pd.DataFrame:
        """Get suggestions for specific user with profile data from Supabase."""
        if self.client is None:
            return pd.DataFrame()

        try:
            email_lower = user_email.lower().strip()

            # Get suggestions for this user
            suggestions = self.client.table('suggestions').select('*').eq('suggested_to_email', email_lower).execute()

            if not suggestions.data or len(suggestions.data) == 0:
                return pd.DataFrame()

            # Get profile emails
            profile_emails = [s['profile_of_email'] for s in suggestions.data]

            # Get profiles
            profiles = self.client.table('profiles').select('*').in_('email', profile_emails).execute()

            if not profiles.data:
                return pd.DataFrame()

            # Normalize profile keys
            normalized_profiles = []
            for profile in profiles.data:
                normalized = self._normalize_profile_keys(profile)
                normalized_profiles.append(normalized)

            profiles_df = pd.DataFrame(normalized_profiles)
            suggestions_df = pd.DataFrame(suggestions.data)

            # Add suggestion status
            profiles_df['_email_lower'] = profiles_df['Email'].str.lower().str.strip()
            suggestions_df['_profile_lower'] = suggestions_df['profile_of_email'].str.lower().str.strip()

            merged = profiles_df.merge(
                suggestions_df[['_profile_lower', 'status']].rename(columns={'status': 'SuggestionStatus'}),
                left_on='_email_lower',
                right_on='_profile_lower',
                how='left'
            )

            merged = merged.drop(columns=['_email_lower', '_profile_lower'], errors='ignore')

            return merged
        except Exception as e:
            st.error(f"Failed to get user suggestions from Supabase: {e}")
            return pd.DataFrame()

    def add_suggestion(self, suggested_to_email: str, profile_of_email: str, status: str = "Pending") -> bool:
        """Add a new suggestion to Supabase."""
        if self.client is None:
            return False

        try:
            data = {
                'suggested_to_email': suggested_to_email.lower().strip(),
                'profile_of_email': profile_of_email.lower().strip(),
                'status': status
            }
            response = self.client.table('suggestions').insert(data).execute()
            return bool(response.data)
        except Exception as e:
            st.error(f"Failed to add suggestion to Supabase: {e}")
            return False

    def update_suggestion_status(self, suggested_to_email: str, profile_of_email: str, new_status: str) -> bool:
        """Update suggestion status in Supabase."""
        if self.client is None:
            return False

        try:
            response = self.client.table('suggestions').update({'status': new_status}).eq('suggested_to_email', suggested_to_email.lower().strip()).eq('profile_of_email', profile_of_email.lower().strip()).execute()
            return bool(response.data)
        except Exception as e:
            st.error(f"Failed to update suggestion in Supabase: {e}")
            return False

    def suggestion_exists(self, suggested_to_email: str, profile_of_email: str) -> bool:
        """Check if a suggestion exists in Supabase."""
        if self.client is None:
            return False

        try:
            response = self.client.table('suggestions').select('id').eq('suggested_to_email', suggested_to_email.lower().strip()).eq('profile_of_email', profile_of_email.lower().strip()).execute()
            return bool(response.data and len(response.data) > 0)
        except Exception:
            return False
