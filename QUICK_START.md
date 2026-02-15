# Quick Start Guide

## Current Status

Your Tingles app has been enhanced with:
- ✅ OAuth login support (Google & LinkedIn)
- ✅ Mandatory profile completion for new users
- ✅ Email/password authentication (already working)

## Running the App

### Option 1: Without OAuth (Email/Password Only)

The app works perfectly without OAuth configuration. Just run:

```bash
streamlit run app.py
```

**What you'll see:**
- Login page with email/password fields
- Sign up tab for new users
- ℹ️ Info message on Sign Up tab: "Google and LinkedIn login can be enabled!"
- No OAuth buttons (since not configured)

**User Flow:**
1. Users sign up with email/password
2. Log in
3. Complete profile (Name, Age, Gender required)
4. Access matches

---

### Option 2: With OAuth (Google/LinkedIn Login)

To enable OAuth buttons, you need to configure credentials.

#### Quick Test Setup (For Testing Only)

For quick testing, you can use these test redirect URIs in your OAuth apps:
- `http://localhost:8501/`
- `http://127.0.0.1:8501/`

#### Step 1: Get Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use existing)
3. Enable Google+ API
4. Create OAuth Client ID:
   - Type: Web application
   - Authorized redirect URIs: `http://localhost:8501/`
5. Copy Client ID and Client Secret

#### Step 2: Get LinkedIn OAuth Credentials (Optional)

1. Go to [LinkedIn Developers](https://www.linkedin.com/developers/apps)
2. Create an app
3. Add redirect URL: `http://localhost:8501/`
4. Request scopes: `openid`, `profile`, `email`
5. Copy Client ID and Client Secret

#### Step 3: Configure Secrets

Edit `.streamlit/secrets.toml`:

```toml
[oauth]
# Google OAuth
google_client_id = "your-actual-client-id-here.apps.googleusercontent.com"
google_client_secret = "your-actual-client-secret-here"

# LinkedIn OAuth (optional)
linkedin_client_id = "your-linkedin-client-id"
linkedin_client_secret = "your-linkedin-client-secret"

# Redirect URI
redirect_uri = "http://localhost:8501"
```

#### Step 4: Run the App

```bash
streamlit run app.py
```

**What you'll see:**
- Login page with email/password fields
- 🔵 **Google** button (if configured)
- 🔷 **LinkedIn** button (if configured)
- "Or continue with" separator

---

## Testing the New Features

### Test 1: Email/Password Signup with Profile Completion

1. Go to Sign Up tab
2. Create account: `test@example.com` / `password123`
3. Sign In with those credentials
4. **You'll see:** Profile completion form (mandatory)
5. Fill in: Name, Age, Gender (required)
6. Add optional: profession, photos, bio, etc.
7. Click "Complete Profile & Start Matchmaking"
8. **You'll see:** "Curated For You" page

### Test 2: OAuth Signup (If Configured)

1. Click 🔵 Google or 🔷 LinkedIn button
2. Authenticate with provider
3. **You'll see:** Profile completion form
4. Name is pre-filled from OAuth provider
5. Add Age and Gender (required)
6. Add optional fields
7. Click "Complete Profile & Start Matchmaking"
8. **You'll see:** "Curated For You" page

### Test 3: Returning User

1. Log in with existing account
2. **You'll see:** Directly to main app (no profile form)
3. Can view matches immediately

### Test 4: Incomplete Profile

1. Create new user
2. Start filling profile but DON'T complete it
3. Log out
4. Log back in
5. **You'll see:** Profile completion form again (blocked from accessing matches)

---

## Database Migration

**Required for OAuth to work:**

1. Open [Supabase Dashboard](https://app.supabase.com)
2. Go to SQL Editor
3. Copy contents of `migration/add_oauth_support.sql`
4. Run the migration
5. This adds `auth_provider` and `oauth_id` columns to `credentials` table

**Note:** The app will work with email/password without the migration, but you MUST run it before enabling OAuth.

---

## Current State

### What's Working Now (No Setup Required)
✅ Email/password signup
✅ Email/password login
✅ Profile completion requirement
✅ Matches system
✅ God Mode for founders

### What Needs OAuth Setup
⏸️ Google login button (needs credentials)
⏸️ LinkedIn login button (needs credentials)
⏸️ OAuth user creation (needs database migration)

---

## Troubleshooting

### "No OAuth buttons visible"
**Cause:** OAuth credentials not configured (this is normal!)
**Solution:** Either:
- Use email/password login (already works)
- OR configure OAuth credentials in `secrets.toml`

### "OAuth button appears but doesn't work"
**Cause:** Database migration not run
**Solution:** Run `migration/add_oauth_support.sql` in Supabase

### "Redirect URI mismatch"
**Cause:** Redirect URI in OAuth app doesn't match secrets.toml
**Solution:** Make sure both have `http://localhost:8501/` (with trailing slash)

### "Profile form appears every time"
**Cause:** Profile missing required fields (Name, Age, or Gender)
**Solution:** Complete all required fields marked with *

---

## Next Steps

### Minimal Setup (No OAuth)
```bash
# Just run the app - email/password already works
streamlit run app.py
```

### Full OAuth Setup
1. Read `OAUTH_SETUP.md` for detailed instructions
2. Get Google/LinkedIn credentials
3. Run database migration
4. Configure `secrets.toml`
5. Test OAuth login

### Production Deployment
1. Update redirect URIs to production domain (HTTPS)
2. Update `secrets.toml` with production URLs
3. Publish OAuth consent screens
4. Test all authentication methods

---

## Support

- **Detailed OAuth Setup:** See `OAUTH_SETUP.md`
- **Recent Changes:** See `OAUTH_CHANGES_SUMMARY.md`
- **Database Schema:** See `migration/add_oauth_support.sql`

The app is ready to use right now with email/password! OAuth is completely optional. 🚀
