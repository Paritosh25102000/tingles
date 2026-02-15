# OAuth Setup Guide

This guide will help you set up Google and LinkedIn OAuth login for your Tingles matchmaking app.

## Prerequisites

1. **Run the database migration** to add OAuth support to your Supabase credentials table:
   - Go to your [Supabase Dashboard](https://app.supabase.com)
   - Navigate to your project → SQL Editor
   - Copy and paste the contents of `migration/add_oauth_support.sql`
   - Click "Run" to execute the migration

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Google OAuth Setup

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google+ API** (for user profile access)

### Step 2: Create OAuth Credentials

1. In the Google Cloud Console, go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. If prompted, configure the OAuth consent screen:
   - User Type: **External**
   - App name: **Tingles** (or your app name)
   - User support email: Your email
   - Developer contact email: Your email
   - Scopes: Add `email`, `profile`, `openid`
   - Save and continue

4. Create OAuth Client ID:
   - Application type: **Web application**
   - Name: **Tingles Web Client**
   - Authorized redirect URIs:
     - For local development: `http://localhost:8501/`
     - For production: `https://yourdomain.com/`
   - Click **Create**

5. Copy your **Client ID** and **Client Secret**

### Step 3: Add to secrets.toml

Open `.streamlit/secrets.toml` and add your Google credentials:

```toml
[oauth]
google_client_id = "YOUR_GOOGLE_CLIENT_ID"
google_client_secret = "YOUR_GOOGLE_CLIENT_SECRET"
redirect_uri = "http://localhost:8501"  # Change to your domain in production
```

## LinkedIn OAuth Setup

### Step 1: Create LinkedIn App

1. Go to [LinkedIn Developers](https://www.linkedin.com/developers/apps)
2. Click **Create app**
3. Fill in the details:
   - App name: **Tingles**
   - LinkedIn Page: Select or create a company page
   - Privacy policy URL: Your privacy policy URL
   - App logo: Upload your logo
4. Click **Create app**

### Step 2: Configure OAuth Settings

1. In your LinkedIn app, go to the **Auth** tab
2. Add **Redirect URLs**:
   - For local development: `http://localhost:8501/`
   - For production: `https://yourdomain.com/`
3. In **OAuth 2.0 scopes**, request:
   - `openid`
   - `profile`
   - `email`
4. Copy your **Client ID** and **Client Secret** from the Auth tab

### Step 3: Add to secrets.toml

Open `.streamlit/secrets.toml` and add your LinkedIn credentials:

```toml
[oauth]
google_client_id = "YOUR_GOOGLE_CLIENT_ID"
google_client_secret = "YOUR_GOOGLE_CLIENT_SECRET"
linkedin_client_id = "YOUR_LINKEDIN_CLIENT_ID"
linkedin_client_secret = "YOUR_LINKEDIN_CLIENT_SECRET"
redirect_uri = "http://localhost:8501"  # Change to your domain in production
```

## Testing OAuth Login

1. **Start your Streamlit app**:
   ```bash
   streamlit run app.py
   ```

2. **Test the login flow**:
   - Go to the login page
   - You should see Google and/or LinkedIn buttons (depending on which you configured)
   - Click a button to test OAuth login
   - You'll be redirected to the provider's login page
   - After authentication, you'll be redirected back to your app

3. **Verify in Supabase**:
   - Check the `credentials` table
   - New OAuth users should have:
     - `auth_provider`: `google` or `linkedin`
     - `password`: `NULL`
     - `oauth_id`: User's email or unique ID

## Troubleshooting

### "Redirect URI mismatch" error
- Make sure the redirect URI in your OAuth app settings **exactly** matches the one in `secrets.toml`
- Include the trailing slash: `http://localhost:8501/`

### OAuth buttons not showing
- Check that your credentials are correctly added to `secrets.toml`
- Verify the `[oauth]` section exists and is properly formatted
- Restart the Streamlit app after changing `secrets.toml`

### "Invalid state token" error
- This is a security check. Try clearing your browser cache/cookies
- Make sure you're clicking the OAuth button from the login page (not using a bookmarked OAuth URL)

### User can't sign in after OAuth signup
- Check the Supabase `credentials` table to verify the user was created
- Ensure the `auth_provider` column exists (run the migration if not)

## Production Deployment

When deploying to production:

1. **Update redirect URIs** in both:
   - Your OAuth provider settings (Google/LinkedIn)
   - `.streamlit/secrets.toml` → `oauth.redirect_uri`

2. **Use HTTPS**: OAuth providers require HTTPS in production
   - Example: `redirect_uri = "https://tingles.streamlit.app"`

3. **Secure your secrets**:
   - Never commit `secrets.toml` to version control
   - Use Streamlit Cloud's secrets management or environment variables

4. **Test thoroughly**:
   - Test both OAuth login and traditional email/password login
   - Verify existing users can still log in
   - Test account linking (email user switching to OAuth)

## How It Works

1. **User clicks OAuth button** → Redirected to Google/LinkedIn
2. **User authorizes** → Provider redirects back with authorization code
3. **App exchanges code** → Gets access token and user info (email, name)
4. **App checks database**:
   - If user exists → Log them in
   - If new user → Create account with OAuth provider info
5. **User is logged in** → Can access the app

## Security Features

- **CSRF Protection**: State token prevents cross-site request forgery
- **No password storage**: OAuth users don't have passwords in the database
- **Provider verification**: Users must authenticate with their OAuth provider
- **Account linking**: Email users can upgrade to OAuth login

## Support

If you encounter issues:
1. Check the Streamlit console for error messages
2. Verify your OAuth credentials are correct
3. Check Supabase logs for database errors
4. Review this guide for common issues

For additional help, refer to:
- [Google OAuth Documentation](https://developers.google.com/identity/protocols/oauth2)
- [LinkedIn OAuth Documentation](https://docs.microsoft.com/en-us/linkedin/shared/authentication/authentication)
- [Streamlit Documentation](https://docs.streamlit.io/)
