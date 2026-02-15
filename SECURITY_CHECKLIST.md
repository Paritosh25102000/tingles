# Security Checklist for Tingles App

Based on Google Cloud's security best practices notification (Feb 2026).

## ✅ Already Implemented

- [x] **Zero-Code Storage**: Service account credentials stored in `.streamlit/secrets.toml` (gitignored)
- [x] **No Hardcoded Keys**: No API keys or secrets in source code
- [x] **Secure Deployment**: Using Streamlit Cloud's secrets management
- [x] **API Scope Restrictions**: Service account only has Google Sheets API access

## ⚠️ Action Items (Recommended)

### 1. Review Service Account Permissions (HIGH PRIORITY)
**What to do:**
1. Go to [Google Cloud Console - IAM](https://console.cloud.google.com/iam-admin/iam)
2. Find your service account (the one in your secrets.toml)
3. Check its roles - it should ONLY have:
   - `Editor` access to your specific Google Sheet (not the entire project)
   - Or better: Use Google Sheets API sharing (share sheet with service account email)
4. **Remove any unnecessary roles** (like Project Editor, Owner, etc.)

**Best practice:** Don't grant project-wide permissions. Share the specific Google Sheet with the service account email instead.

### 2. Rotate Service Account Key (MEDIUM PRIORITY)
**What to do:**
1. Go to [Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Check the **key creation date** - if older than 90 days, rotate it
3. Create a new key → Download JSON → Update `.streamlit/secrets.toml` and Streamlit Cloud secrets
4. Delete the old key

**Why:** Google recommends rotating keys every 90 days to limit exposure window.

### 3. Implement Key Expiry Policy (OPTIONAL - For Stricter Security)
**What to do:**
1. Go to [Organization Policies](https://console.cloud.google.com/iam-admin/orgpolicies)
2. Set `iam.serviceAccountKeyExpiryHours` to enforce automatic key expiration (e.g., 2160 hours = 90 days)

**Note:** This is more relevant for organizations. For personal/small projects, manual rotation is sufficient.

### 4. Set Up Essential Contacts (LOW PRIORITY)
**What to do:**
1. Go to [Essential Contacts](https://console.cloud.google.com/iam-admin/essential-contacts)
2. Add your email for security notifications

### 5. Review Active Keys (MEDIUM PRIORITY)
**What to do:**
1. Go to your service account → Keys tab
2. Check if there are multiple keys listed
3. Delete any keys that are:
   - No longer in use
   - Older than 90 days
   - From testing/development

**Ideal state:** Only 1 active key in production.

## 🔄 When Migrating to Supabase

Once you migrate to Supabase, many of these issues will be resolved:
- ✅ No service account keys needed (Supabase handles auth internally)
- ✅ Row-level security (RLS) for fine-grained access control
- ✅ Built-in secret rotation via Supabase dashboard
- ✅ Better security posture overall

## 📋 Quick Action Checklist

**Do these NOW:**
- [ ] Check service account permissions in Google Cloud Console
- [ ] Verify key creation date - if >90 days old, rotate it
- [ ] Remove any unused/old service account keys
- [ ] Add your email to Essential Contacts

**Do these WHEN you have time:**
- [ ] Review Google Sheet sharing settings (share with service account email only, not entire project)
- [ ] Consider migrating to Supabase for better security and scalability

## 🔐 Your Current Security Score: 8/10

**Strong points:**
- No secrets in code ✅
- Using secure secrets management ✅
- Gitignore configured correctly ✅

**Improvement areas:**
- Service account key rotation (manual process)
- May have broader permissions than needed (need to verify)
