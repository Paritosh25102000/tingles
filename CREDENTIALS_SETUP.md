# Tingles — Credentials Sheet Setup

## Overview
Tingles now uses a **login system** with credentials stored in a separate sheet within your Google Sheet. This provides a standardized experience for both founder and regular users.

## Setup Instructions

### 1. Create a New Sheet for Credentials

In your Google Sheet (same one used for profiles), create a new sheet named **`credentials`** (lowercase).

**Column Headers (Row 1):**
- `username` — User's login username
- `password` — User's password (plaintext, stored in sheet)
- `role` — User's role: either `founder` or `user`

### 2. Add Users

Example data:

| username | password | role |
|----------|----------|------|
| Suman | godmode | founder |
| client1 | password123 | user |
| client2 | client_pass | user |

**Notes:**
- Column names are case-insensitive and flexible (e.g., "Username", "PASS", "Role" all work)
- Passwords are stored in plaintext — treat this sheet as sensitive
- Users with role `founder` will see God Mode (founder tools)
- Users with role `user` will see the Gallery only

### 3. Test Login

1. Start the app: `streamlit run app.py`
2. You'll see a login page before the main app
3. Enter credentials (e.g., `virat` / `Virat@1105`) and click "Sign In"
4. Founder will see God Mode; regular user will see Gallery
5. Logout button appears in top-right corner

## Security Notes

- **Plaintext Passwords**: Credentials are stored in plaintext in the Google Sheet. For production use, consider:
  - Using environment variables for founder credentials
  - Implementing password hashing
  - Using a dedicated authentication service
- **Sheet Visibility**: Ensure the credentials sheet is only accessible to trusted team members
- **API Keys**: Your service account JSON in `.streamlit/secrets.toml` grants full access to the sheet; keep it secure

## Troubleshooting

**Login fails with "Invalid username or password"**
- Check column names in the credentials sheet (should be: username, password, role)
- Verify exact spelling and case of username/password in the sheet
- Ensure the sheet is named `credentials` (case-insensitive in gspread but be consistent)

**Founder can't access God Mode**
- Confirm the user's role is set to `founder` (lowercase) in the credentials sheet
- Logout and log back in
- Check for extra spaces in the sheet data

**Credentials sheet not loading**
- Ensure `.streamlit/secrets.toml` has correct spreadsheet URL and service account credentials
- Verify gspread and service account have access to the sheet
- Check console for error messages

## Future Enhancements

- **Password Hashing**: Hash passwords using `bcrypt` or similar before storing
- **Two-Factor Auth**: Add optional 2FA for founder accounts
- **User Management UI**: Allow founder to manage user credentials within the app
- **Activity Logs**: Track login/logout events and user actions
