# Quick Start: Setting Up Credentials in Your Google Sheet

## What Changed?

Your Tingles app now has a **login page** instead of a hardcoded password. This provides:
- Standardized login experience for all users
- Role-based access control (founder vs. regular users)
- User management stored in a sheet (no code changes needed to add/remove users)

## Setup in 3 Steps

### Step 1: Create a New Sheet Named "credentials"

1. Open your Google Sheet used by Tingles
2. Click the **"+"** button to add a new sheet
3. Name it **`credentials`** (the app will look for this sheet)

### Step 2: Add Column Headers

In the first row of the credentials sheet, add:
- **A1:** `username`
- **B1:** `password`
- **C1:** `role`

### Step 3: Add Your First User (Founder)

In the second row, add:
- **A2:** `virat` (or your preferred username)
- **B2:** `Virat@1105` (your password)
- **C2:** `founder` (role)

You can add more users by adding more rows. Example:

| username | password | role |
|----------|----------|------|
| virat | Virat@1105 | founder |
| alice | alice_pass | user |
| bob | bob_pass | user |

## How It Works

**Founder Login** (`role: founder`):
- Sees **God Mode** when they log in
- Can add profiles, delete profiles, edit MatchStage, clear interests

**User Login** (`role: user`):
- Sees **Gallery** when they log in
- Can browse available profiles and express interest
- Logout button in top-right corner

## Testing Locally

The app is live at http://localhost:8501

1. Try logging in with `virat` / `Virat@1105`
   - You should see God Mode with founder tools
2. Try with a regular user account (if you added any)
   - You should see Gallery only

## Security Reminder

⚠️ **Passwords in plaintext**: The credentials sheet stores passwords as plain text. For production:
- Consider using `bcrypt` for password hashing
- Restrict sheet access to trusted team members only
- Keep your service account JSON secret

## Deploying to Streamlit Cloud

Same process as before:
1. Push to GitHub (already done ✓)
2. Log in to Streamlit Cloud (streamlit.io/cloud)
3. Select your `Paritosh25102000/tingles` repo
4. Configure secrets in the dashboard (your service account JSON)
5. Deploy!

The credentials sheet will automatically be read from your Google Sheet during login.

---

**Questions?** Refer to `CREDENTIALS_SETUP.md` for detailed troubleshooting.
