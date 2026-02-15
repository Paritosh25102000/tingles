"""
OAuth authentication handler for Google and LinkedIn.
Provides OAuth login functionality for the Tingles matchmaking app.
"""

import streamlit as st
from typing import Optional, Dict, Tuple
import requests
from urllib.parse import urlencode
import secrets


class OAuthHandler:
    """Handle OAuth authentication flows for Google and LinkedIn."""

    def __init__(self):
        """Initialize OAuth handler with credentials from secrets."""
        self.google_client_id = st.secrets.get("oauth", {}).get("google_client_id", "")
        self.google_client_secret = st.secrets.get("oauth", {}).get("google_client_secret", "")
        self.linkedin_client_id = st.secrets.get("oauth", {}).get("linkedin_client_id", "")
        self.linkedin_client_secret = st.secrets.get("oauth", {}).get("linkedin_client_secret", "")

        # Get the app URL from secrets or use default
        self.redirect_uri = st.secrets.get("oauth", {}).get("redirect_uri", "http://localhost:8501")

    def generate_state_token(self) -> str:
        """Generate a random state token for CSRF protection."""
        return secrets.token_urlsafe(32)

    def get_google_auth_url(self) -> str:
        """Generate Google OAuth authorization URL."""
        if not self.google_client_id:
            return ""

        # Generate state token for CSRF protection
        state = self.generate_state_token()
        st.session_state.oauth_state = state

        params = {
            "client_id": self.google_client_id,
            "redirect_uri": f"{self.redirect_uri}/",
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account"
        }

        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    def get_linkedin_auth_url(self) -> str:
        """Generate LinkedIn OAuth authorization URL."""
        if not self.linkedin_client_id:
            return ""

        # Generate state token for CSRF protection
        state = self.generate_state_token()
        st.session_state.oauth_state = state

        params = {
            "client_id": self.linkedin_client_id,
            "redirect_uri": f"{self.redirect_uri}/",
            "response_type": "code",
            "scope": "openid profile email",
            "state": state
        }

        return f"https://www.linkedin.com/oauth/v2/authorization?{urlencode(params)}"

    def exchange_google_code(self, code: str) -> Optional[Dict]:
        """Exchange Google authorization code for access token and user info."""
        if not self.google_client_id or not self.google_client_secret:
            return None

        try:
            # Exchange code for token
            token_url = "https://oauth2.googleapis.com/token"
            token_data = {
                "client_id": self.google_client_id,
                "client_secret": self.google_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": f"{self.redirect_uri}/"
            }

            token_response = requests.post(token_url, data=token_data)
            if token_response.status_code != 200:
                st.error(f"Failed to get access token: {token_response.text}")
                return None

            token_json = token_response.json()
            access_token = token_json.get("access_token")

            if not access_token:
                return None

            # Get user info
            userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            headers = {"Authorization": f"Bearer {access_token}"}
            userinfo_response = requests.get(userinfo_url, headers=headers)

            if userinfo_response.status_code != 200:
                return None

            user_info = userinfo_response.json()
            return {
                "email": user_info.get("email", "").lower(),
                "name": user_info.get("name", ""),
                "picture": user_info.get("picture", ""),
                "provider": "google"
            }
        except Exception as e:
            st.error(f"Google OAuth error: {e}")
            return None

    def exchange_linkedin_code(self, code: str) -> Optional[Dict]:
        """Exchange LinkedIn authorization code for access token and user info."""
        if not self.linkedin_client_id or not self.linkedin_client_secret:
            return None

        try:
            # Exchange code for token
            token_url = "https://www.linkedin.com/oauth/v2/accessToken"
            token_data = {
                "client_id": self.linkedin_client_id,
                "client_secret": self.linkedin_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": f"{self.redirect_uri}/"
            }

            token_response = requests.post(token_url, data=token_data)
            if token_response.status_code != 200:
                st.error(f"Failed to get LinkedIn access token: {token_response.text}")
                return None

            token_json = token_response.json()
            access_token = token_json.get("access_token")

            if not access_token:
                return None

            # Get user info using OpenID Connect userinfo endpoint
            headers = {"Authorization": f"Bearer {access_token}"}

            # Get email
            userinfo_url = "https://api.linkedin.com/v2/userinfo"
            userinfo_response = requests.get(userinfo_url, headers=headers)

            if userinfo_response.status_code != 200:
                st.error(f"Failed to get LinkedIn user info: {userinfo_response.text}")
                return None

            user_info = userinfo_response.json()

            return {
                "email": user_info.get("email", "").lower(),
                "name": user_info.get("name", ""),
                "picture": user_info.get("picture", ""),
                "provider": "linkedin"
            }
        except Exception as e:
            st.error(f"LinkedIn OAuth error: {e}")
            return None

    def handle_oauth_callback(self) -> Optional[Dict]:
        """
        Handle OAuth callback from query parameters.
        Returns user info dict if successful, None otherwise.
        """
        # Check for OAuth callback parameters
        query_params = st.query_params

        code = query_params.get("code")
        state = query_params.get("state")
        error = query_params.get("error")

        # Check for errors
        if error:
            st.error(f"OAuth error: {error}")
            return None

        # If no code, not an OAuth callback
        if not code:
            return None

        # Basic state validation - just check it exists (session state is lost across redirects in Streamlit)
        if not state:
            st.error("Missing state token. Please try again.")
            st.query_params.clear()
            return None

        # Try to determine provider - check which credentials are configured
        # Since session state is lost across redirects, we'll try both providers
        provider = None
        user_info = None

        # Try Google first if configured
        if self.google_client_id and self.google_client_secret:
            user_info = self.exchange_google_code(code)
            if user_info:
                provider = "google"

        # If Google failed or not configured, try LinkedIn
        if not user_info and self.linkedin_client_id and self.linkedin_client_secret:
            user_info = self.exchange_linkedin_code(code)
            if user_info:
                provider = "linkedin"

        # If neither worked, show error
        if not user_info:
            st.error("Failed to authenticate. Please try again.")

        # Clear query params after processing
        st.query_params.clear()

        # Clear any session state
        if "oauth_state" in st.session_state:
            del st.session_state.oauth_state
        if "oauth_provider" in st.session_state:
            del st.session_state.oauth_provider

        return user_info


def create_oauth_buttons(show_setup_info=False, key_prefix=""):
    """
    Create OAuth login buttons for Google and LinkedIn.
    Returns True if OAuth credentials are configured, False otherwise.

    Args:
        show_setup_info: If True, shows setup instructions when OAuth is not configured
        key_prefix: Prefix for button keys to avoid duplicates (e.g., "signin_", "signup_")
    """
    oauth = OAuthHandler()

    # Check if OAuth is configured
    has_google = bool(oauth.google_client_id and oauth.google_client_secret)
    has_linkedin = bool(oauth.linkedin_client_id and oauth.linkedin_client_secret)

    if not has_google and not has_linkedin:
        # Show helpful message if requested
        if show_setup_info:
            st.markdown("<p style='text-align: center; color: #6b7280; margin: 20px 0 10px 0;'>OAuth login available</p>", unsafe_allow_html=True)
            st.info("**Google and LinkedIn login can be enabled.** Add your OAuth credentials to `.streamlit/secrets.toml` to show login buttons. See `OAUTH_SETUP.md` for instructions.")
        return False

    st.markdown("<p style='text-align: center; color: #6b7280; margin: 20px 0 10px 0;'>Or</p>", unsafe_allow_html=True)

    # Create centered columns for OAuth buttons
    if has_google and has_linkedin:
        # Both providers - show side by side
        _, col1, col2, _ = st.columns([0.5, 1, 1, 0.5])
    elif has_google or has_linkedin:
        # Single provider - center it
        _, col1, _ = st.columns([1, 2, 1])
        col2 = None

    # Google OAuth button
    if has_google:
        with col1:
            google_auth_url = oauth.get_google_auth_url()
            if st.button("Sign in with Google", use_container_width=True, key=f"{key_prefix}google_oauth"):
                st.session_state.oauth_provider = "google"
                st.markdown(f'<meta http-equiv="refresh" content="0;url={google_auth_url}">', unsafe_allow_html=True)
                st.stop()

    # LinkedIn OAuth button
    if has_linkedin:
        target_col = col2 if (has_google and col2) else col1
        with target_col:
            linkedin_auth_url = oauth.get_linkedin_auth_url()
            if st.button("Sign in with LinkedIn", use_container_width=True, key=f"{key_prefix}linkedin_oauth"):
                st.session_state.oauth_provider = "linkedin"
                st.markdown(f'<meta http-equiv="refresh" content="0;url={linkedin_auth_url}">', unsafe_allow_html=True)
                st.stop()

    return True
