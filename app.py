import streamlit as st
import pandas as pd
from urllib.parse import quote_plus
from pathlib import Path
import base64
import io
from PIL import Image

st.set_page_config(page_title="Tingles — Boutique Matchmaking", layout="wide")

# Load custom CSS
try:
    with open("style.css", "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    st.warning("style.css not found — default styling will apply.")

st.markdown(
    """
<div class="app-container">
  <div class="brand">
    <h1>Tingles</h1>
    <p class="tag">Boutique Matchmaking</p>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ============ IMAGE UPLOAD HELPER ============
def upload_images_to_base64(uploaded_files, max_images=3):
    """Convert uploaded images to base64 data URIs (max 3 images, compressed to <500KB each)."""
    if not uploaded_files:
        return ""

    image_urls = []
    for file in uploaded_files[:max_images]:
        try:
            # Read image
            img = Image.open(file)

            # Convert RGBA to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background

            # Resize if too large (max 1200px width)
            max_width = 1200
            if img.width > max_width:
                ratio = max_width / img.width
                new_size = (max_width, int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            # Convert to base64
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=85, optimize=True)
            img_str = base64.b64encode(buffered.getvalue()).decode()

            # Create data URI
            data_uri = f"data:image/jpeg;base64,{img_str}"
            image_urls.append(data_uri)
        except Exception as e:
            st.warning(f"Failed to process {file.name}: {e}")
            continue

    # Return comma-separated URLs
    return ", ".join(image_urls)

# Prefer Streamlit's connection API, but fall back to gspread if unavailable
conn = None
gspread_client = None
gspread_sh = None
gspread_ws = None
credentials_ws = None  # For credentials sheet
suggestions_ws = None  # For suggestions sheet

# Founder email for God Mode access (configure in secrets.toml)
try:
    FOUNDER_EMAIL = st.secrets.get("founder_email", "founder@tingles.com")
except Exception:
    FOUNDER_EMAIL = "founder@tingles.com"

try:
    conn = st.connection("gsheets", type="gsheets")
except Exception:
    conn = None

def init_gspread_from_toml():
    """Initialize gspread client from secrets (st.secrets on Cloud, or .streamlit/secrets.toml locally)."""
    global gspread_client, gspread_sh, gspread_ws, credentials_ws, suggestions_ws

    # Return early if already initialized
    if gspread_ws is not None:
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
            creds = {k: v for k, v in st.secrets.items() if k not in ("connections", "spreadsheet")}
            # Or they might be nested
            if not creds or "type" not in creds:
                if "service_account" in gsheets_secrets:
                    creds = dict(gsheets_secrets["service_account"])
        # Check for flat format (spreadsheet + service account at root)
        elif "spreadsheet" in st.secrets:
            spreadsheet = st.secrets["spreadsheet"]
            creds = {k: v for k, v in st.secrets.items() if k != "spreadsheet"}
        # Check for type key (service account JSON directly at root)
        elif "type" in st.secrets:
            creds = dict(st.secrets)
            # spreadsheet might be in a different key
            spreadsheet = st.secrets.get("spreadsheet") or st.secrets.get("sheet_url")
    except Exception as e:
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
                    creds = creds or {k: v for k, v in data.items() if k not in ("connections", "spreadsheet")}
                else:
                    spreadsheet = spreadsheet or data.get("spreadsheet")
                    creds = creds or {k: v for k, v in data.items() if k != "spreadsheet"}
        except Exception:
            pass

    if not spreadsheet:
        # Debug: show what keys are available
        try:
            available_keys = list(st.secrets.keys()) if hasattr(st.secrets, 'keys') else "st.secrets has no keys()"
        except Exception:
            available_keys = "could not read st.secrets"
        return False, f"no spreadsheet URL found. Available secret keys: {available_keys}"

    if not creds or "type" not in creds:
        return False, f"no service account credentials found. Creds keys: {list(creds.keys()) if creds else 'None'}"

    try:
        gspread_client = gspread.service_account_from_dict(creds)
        gspread_sh = gspread_client.open_by_url(spreadsheet)
        # Try to get "profiles" sheet (renamed from Sheet1)
        try:
            gspread_ws = gspread_sh.worksheet("profiles")
        except Exception:
            # Fallback to Sheet1 if profiles doesn't exist
            try:
                gspread_ws = gspread_sh.worksheet("Sheet1")
            except Exception:
                gspread_ws = gspread_sh.sheet1
    except Exception as e:
        return False, f"gspread init failed: {e}"

    # Try to get credentials sheet - list all sheets for debugging
    try:
        all_sheets = [ws.title for ws in gspread_sh.worksheets()]
    except Exception:
        all_sheets = []

    try:
        credentials_ws = gspread_sh.worksheet("credentials")
    except Exception:
        try:
            credentials_ws = gspread_sh.worksheet("Credentials")
        except Exception:
            # Try to create it
            try:
                credentials_ws = gspread_sh.add_worksheet(title="credentials", rows=100, cols=3)
                credentials_ws.append_row(["email", "password", "role"])
            except Exception as e:
                return False, f"credentials sheet not found and could not create. Available sheets: {all_sheets}. Error: {e}"

    # Initialize Suggestions sheet
    try:
        suggestions_ws = gspread_sh.worksheet("Suggestions")
    except Exception:
        try:
            suggestions_ws = gspread_sh.worksheet("suggestions")
        except Exception:
            try:
                suggestions_ws = gspread_sh.add_worksheet(title="Suggestions", rows=1000, cols=5)
                suggestions_ws.append_row(["Suggested_To_Email", "Profile_Of_Email", "Status"])
            except Exception as e:
                # Non-fatal: suggestions sheet is optional for backward compat
                suggestions_ws = None

    return True, "ok"

def load_credentials():
    """Load email/password/role from credentials sheet. Returns (df, error_msg) tuple."""
    # Use gspread (works on both local and Streamlit Cloud)
    ok, why = init_gspread_from_toml()
    if not ok:
        return None, f"gspread init failed: {why}"

    if credentials_ws is None:
        return None, "credentials_ws is None after init"

    try:
        records = credentials_ws.get_all_records()
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
        return df, None
    except Exception as e:
        return None, f"Failed to read credentials sheet: {e}"


def add_credential(email, password, role="user"):
    """Add a new user to the credentials sheet. Returns True on success."""
    ok, why = init_gspread_from_toml()
    if not ok or credentials_ws is None:
        return False, f"Could not initialize credentials: {why}"

    try:
        # Check if email already exists
        creds_df, err = load_credentials()
        if creds_df is not None and 'email' in creds_df.columns:
            if email.lower().strip() in creds_df['email'].fillna('').astype(str).str.lower().str.strip().values:
                return False, "Email already registered. Please sign in."

        # Get header to determine column order
        header = credentials_ws.row_values(1)
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

        credentials_ws.append_row(row_values)

        # Note: We don't auto-create a profile stub anymore
        # Users will create their full profile after first login

        return True, None
    except Exception as e:
        return False, f"Failed to add credential: {e}"

# Sheet helpers supporting both conn and gspread fallback
def load_sheet(force_refresh=False):
    """Load the profiles sheet. Set force_refresh=True to bypass cache."""
    if conn is not None:
        try:
            # Use ttl=0 to bypass cache if force_refresh requested
            if force_refresh:
                df = conn.read(ttl=0)
            else:
                df = conn.read()
            if isinstance(df, pd.DataFrame):
                return df
            return pd.DataFrame(df)
        except Exception as e:
            st.error(f"Failed to read sheet via st.connection: {e}")
            return None
    # fallback
    ok, why = init_gspread_from_toml()
    if not ok:
        if why == "missing-packages":
            st.error("Required packages not installed in environment (toml/gspread).")
        else:
            st.error(f"Could not initialize gspread: {why}")
        return None
    try:
        records = gspread_ws.get_all_records()
        return pd.DataFrame(records)
    except Exception as e:
        st.error(f"gspread read failed: {e}")
        return None

def write_sheet(df):
    """Overwrite entire sheet (only used when st.connection is available)."""
    if conn is not None:
        try:
            # Try profiles first, fallback to Sheet1
            try:
                conn.update(worksheet="profiles", data=df)
            except Exception:
                conn.update(worksheet="Sheet1", data=df)
            return True
        except Exception as e:
            st.error(f"Failed to write via st.connection: {e}")
            return False
    st.error("Full-sheet overwrite not supported in fallback mode.")
    return False

def append_row(row_dict):
    if conn is not None:
        try:
            # Normalize column names to match sheet headers
            # Get current sheet to check actual column names
            current_df = load_sheet()
            if current_df is not None and not current_df.empty:
                # Map row_dict keys to actual column names (case-insensitive)
                actual_cols = {col.lower().strip(): col for col in current_df.columns}
                normalized_dict = {}
                for key, value in row_dict.items():
                    key_lower = key.lower().strip()
                    if key_lower in actual_cols:
                        # Use the actual column name from the sheet
                        normalized_dict[actual_cols[key_lower]] = value
                    else:
                        # Keep original key if no match found
                        normalized_dict[key] = value
                conn.write(normalized_dict, mode="append")
            else:
                conn.write(row_dict, mode="append")
            return True
        except Exception as e:
            st.error(f"Failed to append via st.connection: {e}")
            return False
    # fallback: use gspread
    ok, why = init_gspread_from_toml()
    if not ok:
        st.error(f"gspread not initialized: {why}")
        return False
    try:
        # ensure order matches header if present
        header = gspread_ws.row_values(1)
        # build a small alias map to match common header variants
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
            if h in row_dict and row_dict.get(h) not in (None, ""):
                return row_dict.get(h)
            hl = str(h).strip().lower()
            # try direct lower-key
            if hl in row_dict and row_dict.get(hl) not in (None, ""):
                return row_dict.get(hl)
            # try canonical alias mapping
            canon = alias_map_local.get(hl)
            if canon and canon in row_dict and row_dict.get(canon) not in (None, ""):
                return row_dict.get(canon)
            # try common keys
            for k in (hl, canon, h, h.title()):
                if k and k in row_dict and row_dict.get(k) not in (None, ""):
                    return row_dict.get(k)
            return ""

        values = [_get_for_header(h) for h in header]
        gspread_ws.append_row(values)
        return True
    except Exception as e:
        st.error(f"gspread append failed: {e}")
        return False

def update_row_by_number(row_number, updates: dict):
    """Update specific columns by worksheet row number (1-based including header). Always uses gspread."""
    ok, why = init_gspread_from_toml()
    if not ok:
        st.error(f"gspread not initialized: {why}")
        return False
    try:
        header = gspread_ws.row_values(1)
        updates_cells = []
        for col_idx, col_name in enumerate(header, start=1):
            if col_name in updates:
                updates_cells.append((row_number, col_idx, updates[col_name]))
        # perform updates
        for r, c, val in updates_cells:
            gspread_ws.update_cell(r, c, val)
        return True
    except Exception as e:
        st.error(f"gspread update failed: {e}")
        return False


def find_sheet_row_number(identifiers: dict):
    """Find the worksheet row number for a record using ID or Name columns.
    Returns 1-based worksheet row number (including header row), or None if not found.
    """
    ok, why = init_gspread_from_toml()
    if not ok:
        return None
    try:
        header = gspread_ws.row_values(1)
    except Exception:
        return None

    # normalize header names for matching
    header_lc = [str(h).strip().lower() for h in header]

    # build common alias lists (kept small and robust)
    id_aliases = {"id", "identifier", "unique id", "uid"}
    name_aliases = {"name", "full name", "full_name", "displayname", "display name"}

    # helper to find column index by alias set
    def find_col_index_by_alias(aliases_set):
        for i, h in enumerate(header_lc):
            if h in aliases_set:
                return i + 1
        # fallback: try exact 'id' or 'name' presence
        for i, h in enumerate(header_lc):
            if h == 'id' and 'id' in aliases_set:
                return i + 1
            if h == 'name' and 'name' in aliases_set:
                return i + 1
        return None

    # try ID column first
    id_val = identifiers.get('ID') or identifiers.get('Id') or identifiers.get('id')
    id_col = find_col_index_by_alias(id_aliases)
    if id_val and id_col:
        try:
            col_vals = gspread_ws.col_values(id_col)
            for r_idx, v in enumerate(col_vals, start=1):
                if str(v).strip() == str(id_val).strip():
                    return r_idx
        except Exception:
            pass

    # try Name column
    name_val = identifiers.get('Name') or identifiers.get('name')
    name_col = find_col_index_by_alias(name_aliases)
    if name_val and name_col:
        try:
            col_vals = gspread_ws.col_values(name_col)
            for r_idx, v in enumerate(col_vals, start=1):
                if str(v).strip().lower() == str(name_val).strip().lower():
                    return r_idx
        except Exception:
            pass

    # fallback: scan all records
    try:
        records = gspread_ws.get_all_records()
        for i, rec in enumerate(records, start=2):
            # check id
            if id_val and str(rec.get('ID','')).strip() == str(id_val).strip():
                return i
            if name_val and str(rec.get('Name','')).strip().lower() == str(name_val).strip().lower():
                return i
    except Exception:
        pass
    return None


def resolve_image_url(url: str) -> str:
    """Convert hosting page URLs to direct image URLs.
    Handles ibb.co by fetching the page and extracting the actual image URL.
    """
    if not url:
        return None
    s = str(url).strip()
    # If already a direct image URL (i.ibb.co or ends in image extension), return as-is
    if s.startswith('https://i.ibb.co/') or s.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
        return s
    # For ibb.co page URLs, fetch and extract the image URL
    if 'ibb.co' in s:
        try:
            import requests as _requests
            import re as _re
            r = _requests.get(s, timeout=5, allow_redirects=True)
            if r.status_code == 200:
                # Look for i.ibb.co URLs in the HTML
                pattern = r'https://i\.ibb\.co/[a-zA-Z0-9]+/[a-zA-Z0-9._%\-]+\.(jpg|jpeg|png|gif|webp)'
                imgs = _re.findall(pattern, r.text, _re.IGNORECASE)
                if imgs:
                    # Extract just the URL part (regex returns tuples with groups)
                    # Find the full match instead
                    matches = _re.finditer(r'https://i\.ibb\.co/[a-zA-Z0-9]+/[a-zA-Z0-9._%\-]+\.(jpg|jpeg|png|gif|webp)', r.text, _re.IGNORECASE)
                    for m in matches:
                        return m.group(0)
        except Exception:
            pass
    return s


# ============ SUGGESTIONS SHEET FUNCTIONS ============
def load_suggestions():
    """Load all suggestions from the Suggestions sheet. Returns DataFrame or None."""
    ok, why = init_gspread_from_toml()
    if not ok or suggestions_ws is None:
        return None
    try:
        records = suggestions_ws.get_all_records()
        return pd.DataFrame(records)
    except Exception as e:
        return None


def get_suggestions_for_user(user_email):
    """Get all profiles suggested to a specific user. Returns DataFrame of profile data with suggestion status."""
    suggestions_df = load_suggestions()
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
    profiles_df = load_sheet()
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


def add_suggestion(suggested_to_email, profile_of_email, status="Pending"):
    """Add a new suggestion row. Returns True on success."""
    ok, why = init_gspread_from_toml()
    if not ok or suggestions_ws is None:
        return False
    try:
        suggestions_ws.append_row([suggested_to_email, profile_of_email, status])
        return True
    except Exception as e:
        st.error(f"Failed to add suggestion: {e}")
        return False


def update_suggestion_status(suggested_to_email, profile_of_email, new_status):
    """Update the status of a specific suggestion. Returns True on success."""
    ok, why = init_gspread_from_toml()
    if not ok or suggestions_ws is None:
        return False
    try:
        records = suggestions_ws.get_all_records()
        for i, rec in enumerate(records, start=2):  # Start at row 2 (after header)
            if (str(rec.get('Suggested_To_Email', '')).lower().strip() == str(suggested_to_email).lower().strip() and
                str(rec.get('Profile_Of_Email', '')).lower().strip() == str(profile_of_email).lower().strip()):
                # Update Status column (column 3)
                suggestions_ws.update_cell(i, 3, new_status)
                return True
        return False
    except Exception as e:
        st.error(f"Failed to update suggestion: {e}")
        return False


def suggestion_exists(suggested_to_email, profile_of_email):
    """Check if a suggestion already exists."""
    suggestions_df = load_suggestions()
    if suggestions_df is None or suggestions_df.empty:
        return False

    existing = suggestions_df[
        (suggestions_df['Suggested_To_Email'].fillna('').astype(str).str.lower().str.strip() == str(suggested_to_email).lower().strip()) &
        (suggestions_df['Profile_Of_Email'].fillna('').astype(str).str.lower().str.strip() == str(profile_of_email).lower().strip())
    ]
    return not existing.empty


def get_profile_by_email(email, force_refresh=False):
    """Get a single profile by email. Returns dict or None.
    Set force_refresh=True to bypass cache and get fresh data from sheet."""
    profiles_df = load_sheet(force_refresh=force_refresh)
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
    return match.iloc[0].to_dict()


def update_profile_by_email(email, updates: dict):
    """Update specific fields for a profile identified by email. Returns True on success."""
    ok, why = init_gspread_from_toml()
    if not ok:
        return False
    try:
        header = gspread_ws.row_values(1)
        email_col = None
        for i, h in enumerate(header):
            if h.lower().strip() == 'email':
                email_col = i + 1
                break

        if not email_col:
            return False

        # Find row by email
        col_vals = gspread_ws.col_values(email_col)
        row_number = None
        for r_idx, v in enumerate(col_vals, start=1):
            if str(v).strip().lower() == str(email).strip().lower():
                row_number = r_idx
                break

        if not row_number:
            return False

        # Build case-insensitive column mapping
        # Map lowercase column names to their positions and actual names
        col_map = {}
        for col_idx, col_name in enumerate(header, start=1):
            col_map[col_name.lower().strip()] = (col_idx, col_name)

        # Update cells - match both exact case and lowercase
        updates_made = 0
        for update_key, update_value in updates.items():
            # Try exact match first
            if update_key in header:
                col_idx = header.index(update_key) + 1
                gspread_ws.update_cell(row_number, col_idx, update_value)
                updates_made += 1
            # Try case-insensitive match
            elif update_key.lower().strip() in col_map:
                col_idx, actual_name = col_map[update_key.lower().strip()]
                gspread_ws.update_cell(row_number, col_idx, update_value)
                updates_made += 1

        return updates_made > 0
    except Exception as e:
        st.error(f"Profile update failed: {e}")
        return False


# Small connection checker UI (hidden from clients)
if False:  # Disabled for client view
    with st.expander("Connection / Sheet check", expanded=True):
        if conn is None:
            st.info("No Streamlit connection named \"gsheets\" is available. Check your .streamlit/secrets.toml and Streamlit connections.")
        else:
            if st.button("Test connection and load sheet"):
                df_test = load_sheet()
                if df_test is not None:
                    st.success("Sheet loaded — preview below")
                    st.dataframe(df_test.head())

# ============ LOGIN SYSTEM ============
# Initialize login state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_email = None
    st.session_state.role = None


def authenticate_user(email, password):
    """Verify email and password against credentials sheet. Returns (success, role, error_msg) tuple."""
    creds_df, err = load_credentials()
    if creds_df is None:
        return False, None, f"Could not load credentials: {err}"
    if creds_df.empty:
        return False, None, "No users registered. Please sign up first."

    # Normalize email comparison
    email_lower = str(email).strip().lower()

    # Check if email column exists
    if 'email' not in creds_df.columns:
        return False, None, "Credentials sheet missing 'email' column. Please add it to your Google Sheet."

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
    if email_lower == FOUNDER_EMAIL.lower().strip():
        role = 'founder'

    return True, role, None


def logout():
    """Clear login session."""
    st.session_state.logged_in = False
    st.session_state.user_email = None
    st.session_state.role = None

# ============ LOGIN / SIGNUP PAGE ============
if not st.session_state.logged_in:
    st.markdown("<div style='padding: 40px 20px;'>", unsafe_allow_html=True)

    login_col1, login_col2, login_col3 = st.columns([1, 2, 1])
    with login_col2:
        auth_tab = st.tabs(["Sign In", "Sign Up"])

        # ============ SIGN IN TAB ============
        with auth_tab[0]:
            st.markdown("<p style='color: #6b7280; font-size: 14px;'>Enter your credentials to sign in.</p>", unsafe_allow_html=True)
            login_email = st.text_input("Email", placeholder="Enter your email", key="login_email")
            login_password = st.text_input("Password", placeholder="Enter your password", type="password", key="login_password")

            if st.button("Sign In", use_container_width=True, key="signin_btn"):
                if login_email and login_password:
                    success, role, error_msg = authenticate_user(login_email, login_password)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.user_email = login_email
                        st.session_state.role = role
                        # Get user's name for greeting
                        profile = get_profile_by_email(login_email)
                        name = profile.get('Name', login_email) if profile else login_email
                        st.success(f"Welcome, {name}!")
                        st.rerun()
                    else:
                        st.error(error_msg)
                else:
                    st.warning("Please enter both email and password.")

        # ============ SIGN UP TAB ============
        with auth_tab[1]:
            st.markdown("<p style='color: #6b7280; font-size: 14px;'>Create a new account to join Tingles.</p>", unsafe_allow_html=True)
            signup_email = st.text_input("Email", placeholder="Enter your email", key="signup_email")
            signup_password = st.text_input("Password", placeholder="Create a password", type="password", key="signup_password")
            signup_password_confirm = st.text_input("Confirm Password", placeholder="Confirm your password", type="password", key="signup_password_confirm")

            if st.button("Sign Up", use_container_width=True, key="signup_btn"):
                if not signup_email:
                    st.warning("Please enter your email address.")
                elif not signup_password:
                    st.warning("Please enter a password.")
                elif len(signup_password) < 6:
                    st.warning("Password must be at least 6 characters.")
                elif signup_password != signup_password_confirm:
                    st.error("Passwords do not match.")
                else:
                    success, err = add_credential(signup_email, signup_password, "user")
                    if success:
                        st.success("Account created! You can now sign in.")
                    else:
                        st.error(err)

    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()  # Stop execution here; don't show main app until logged in

# ============ MAIN APP (logged in) ============
# Get user profile for display
user_profile = get_profile_by_email(st.session_state.user_email)
user_display_name = user_profile.get('Name', st.session_state.user_email) if user_profile else st.session_state.user_email

# Determine which view to show based on role
is_founder = st.session_state.role == "founder"

# Sidebar navigation
with st.sidebar:
    # Show greeting with name (not email twice)
    greeting_name = user_profile.get('Name', '').strip() if user_profile else ''
    if not greeting_name:
        # Use part before @ from email as fallback
        greeting_name = st.session_state.user_email.split('@')[0]
    st.markdown(f"### Hi, {greeting_name}!")

    if is_founder:
        view = st.radio("Navigate", ["God Mode", "All Profiles"], label_visibility="collapsed")
    else:
        view = st.radio("Navigate", ["Curated For You", "My Profile"], label_visibility="collapsed")

    st.markdown("---")
    if st.button("Logout", use_container_width=True):
        logout()
        st.rerun()

# Admin authentication (God Mode)

# Load sheet into session state; refresh on each page load to catch external changes from the sheet
# This ensures Express Interest and other updates are always visible when returning to the page
st.session_state.df = load_sheet()

# Ensure DataFrame exists
if st.session_state.df is None:
    st.warning("Sheet data not loaded. Use the connection checker above and ensure your secrets are configured.")
else:
    df = st.session_state.df
    # Normalize column names (accept common aliases from the sheet)
    alias_map = {
        "name": "Name",
        "full_name": "Name",
        "email": "Email",
        "email_address": "Email",
        "gender": "Gender",
        "sex": "Gender",
        "age": "Age",
        "bio": "Bio",
        "biography": "Bio",
        "about": "Bio",
        "photo_url": "PhotoURL",
        "photourl": "PhotoURL",
        "imageurl": "PhotoURL",
        "image_url": "PhotoURL",
        "height": "Height",
        "profession": "Profession",
        "job": "Profession",
        "industry": "Industry",
        "education": "Education",
        "religion": "Religion",
        "residency_status": "Residency_Status",
        "residency": "Residency_Status",
        "location": "Location",
        "city": "Location",
        "linkedin_url": "LinkedIn",
        "linkedin": "LinkedIn",
        "whatsapp": "WhatsApp",
        "whatsapp_number": "WhatsApp",
        "phone": "WhatsApp",
        "status": "Status",
        "id": "ID",
    }
    # Build rename mapping based on existing df columns
    from collections import defaultdict
    rename_map = {}
    target_groups = defaultdict(list)
    for col in list(df.columns):
        lower = str(col).strip().lower()
        if lower in alias_map:
            target = alias_map[lower]
            target_groups[target].append(col)

    # If multiple source columns map to the same target, merge them (first non-empty wins)
    for target, srcs in target_groups.items():
        if len(srcs) == 1:
            rename_map[srcs[0]] = target
        else:
            # combine values from srcs into a single column
            try:
                import numpy as _np
            except Exception:
                _np = None
            combined = pd.Series([""] * len(df), index=df.index)
            for s in srcs:
                vals = df[s].fillna("").astype(str)
                # keep existing combined where non-empty, else take from vals
                combined = combined.where(combined.str.strip() != "", vals)
            # assign combined to target (overwrite if exists)
            df[target] = combined
            # drop original source columns except the one equal to target if present
            for s in srcs:
                if s != target and s in df.columns:
                    df.drop(columns=[s], inplace=True)
    if rename_map:
        df = df.rename(columns=rename_map)
    # Ensure expected columns exist
    expected_columns = ["Email", "Name", "Gender", "Age", "Bio", "LinkedIn", "WhatsApp", "PhotoURL",
                        "Profession", "Industry", "Education", "Religion", "Residency_Status",
                        "Location", "Height", "Status"]
    for col in expected_columns:
        if col not in df.columns:
            df[col] = ""
    st.session_state.df = df

    # ============ HELPER: Render Profile Card ============
    def render_profile_card(row, show_interest_button=False, card_index=0):
        """Render a profile card with optional interest button."""
        def _scalar(v):
            if v is None:
                return ""
            if isinstance(v, pd.Series) or isinstance(v, list) or isinstance(v, tuple):
                try:
                    return str(v.iloc[0]) if hasattr(v, 'iloc') else str(v[0])
                except Exception:
                    return str(v)
            return str(v)

        st.markdown("<div class='profile-card'>", unsafe_allow_html=True)

        # Images - support multiple comma-separated URLs
        img_raw = _scalar(row.get("PhotoURL", "") or row.get("ImageURL", ""))
        if img_raw and img_raw.strip():
            # Split by comma for multiple images
            img_urls = [url.strip() for url in img_raw.split(',') if url.strip()]

            # Display images
            if len(img_urls) == 1:
                # Single image
                img_url = resolve_image_url(img_urls[0])
                if img_url:
                    try:
                        st.image(img_url, width=300)
                    except Exception:
                        st.markdown("<div style='height:260px;background:#2a2a2a;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#666'>Image unavailable</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='height:260px;background:#2a2a2a;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#666'>No image</div>", unsafe_allow_html=True)
            else:
                # Multiple images - show in tabs
                img_tabs = st.tabs([f"Photo {i+1}" for i in range(len(img_urls[:5]))])
                for idx, (tab, url) in enumerate(zip(img_tabs, img_urls[:5])):
                    with tab:
                        resolved_url = resolve_image_url(url)
                        if resolved_url:
                            try:
                                st.image(resolved_url, width=300)
                            except Exception:
                                st.markdown("<div style='height:260px;background:#2a2a2a;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#666'>Image unavailable</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='height:260px;background:#2a2a2a;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#666'>No image</div>", unsafe_allow_html=True)

        # Name and age
        name = _scalar(row.get('Name', ''))
        age = _scalar(row.get('Age', ''))
        name_display = f"{name}, {age}" if age else name
        st.markdown(f"<h3 class='name'>{name_display}</h3>", unsafe_allow_html=True)

        # Profession and Location
        profession = _scalar(row.get('Profession', '')) or _scalar(row.get('Industry', ''))
        location = _scalar(row.get('Location', ''))
        if profession or location:
            info_line = " | ".join(filter(None, [profession, location]))
            st.markdown(f"<p class='stats' style='color:#dc2626;font-weight:500;'>{info_line}</p>", unsafe_allow_html=True)

        # Details line
        height = _scalar(row.get('Height', ''))
        education = _scalar(row.get('Education', ''))
        details = " | ".join(filter(None, [f"Height: {height}" if height else "", education]))
        if details:
            st.markdown(f"<p class='stats'>{details}</p>", unsafe_allow_html=True)

        # Bio
        bio = _scalar(row.get('Bio', ''))
        if bio:
            st.markdown(f"<p style='color:#a0a0a0; font-size:14px;'>{bio[:200]}{'...' if len(bio) > 200 else ''}</p>", unsafe_allow_html=True)

        # LinkedIn button
        linkedin = _scalar(row.get("LinkedIn", ""))
        if linkedin:
            st.markdown(f"<a class='btn btn-link' target='_blank' href='{linkedin}'>View LinkedIn</a>", unsafe_allow_html=True)

        # Interest button
        if show_interest_button:
            profile_email = _scalar(row.get('Email', ''))
            if st.button("I'm Interested", key=f"interest_{card_index}_{profile_email}"):
                if update_suggestion_status(st.session_state.user_email, profile_email, "Liked"):
                    st.success("Interest recorded! The matchmaker will be in touch.")
                    st.rerun()
                else:
                    st.error("Could not record interest. Please try again.")

        st.markdown("</div>", unsafe_allow_html=True)

    # ============ VIEWS ============
    if view == "Curated For You":
        st.header("Curated For You")
        st.markdown("<p style='color:#6b7280;'>Profiles handpicked by your matchmaker.</p>", unsafe_allow_html=True)

        # Get suggestions for this user
        user_email = st.session_state.user_email
        curated_profiles = get_suggestions_for_user(user_email)

        # Filter to only show Pending suggestions
        if curated_profiles is not None and not curated_profiles.empty:
            pending = curated_profiles[
                curated_profiles['SuggestionStatus'].fillna('Pending').astype(str).str.lower() == 'pending'
            ]
        else:
            pending = pd.DataFrame()

        if pending.empty:
            st.info("No new profiles curated for you yet. Check back soon!")
        else:
            cols = st.columns(3)
            for i, (_, row) in enumerate(pending.iterrows()):
                with cols[i % 3]:
                    render_profile_card(row, show_interest_button=True, card_index=i)

    elif view == "My Profile":
        st.header("My Profile")

        # Force refresh to get latest data (important after profile creation/edit)
        my_profile = get_profile_by_email(st.session_state.user_email, force_refresh=True)

        # DEBUG: Show what's happening
        if my_profile is None:
            with st.expander("🔍 Debug Info - Why is my profile not showing?", expanded=False):
                st.write("**Your email (searching for):**", st.session_state.user_email)
                debug_df = load_sheet(force_refresh=True)
                if debug_df is not None and not debug_df.empty:
                    st.write("**Sheet columns:**", list(debug_df.columns))
                    if 'Email' in debug_df.columns or any('email' in col.lower() for col in debug_df.columns):
                        email_col = next((col for col in debug_df.columns if 'email' in col.lower()), None)
                        if email_col:
                            st.write(f"**Emails in sheet (from '{email_col}' column):**")
                            emails_in_sheet = debug_df[email_col].dropna().tolist()
                            for email in emails_in_sheet:
                                st.write(f"- `{email}` (matches: {str(email).strip().lower() == st.session_state.user_email.strip().lower()})")
                    st.write("**Sample of sheet data:**")
                    st.dataframe(debug_df.head(10))
                else:
                    st.error("Could not load sheet data for debugging")

        if my_profile is None:
            # Profile not found - show create profile form
            st.info("Welcome! Please complete your profile to get started.")
            st.markdown("<p style='color:#a0a0a0;'>Fill in your details below to complete your profile.</p>", unsafe_allow_html=True)

            with st.form("create_profile"):
                cp_name = st.text_input("Full Name *", placeholder="Enter your full name")

                col1, col2, col3 = st.columns(3)
                with col1:
                    cp_age = st.text_input("Age", placeholder="e.g., 28")
                with col2:
                    cp_height = st.text_input("Height", placeholder="e.g., 5'10\"")
                with col3:
                    cp_gender = st.selectbox("Gender", ["", "Male", "Female", "Other"])

                col4, col5 = st.columns(2)
                with col4:
                    cp_profession = st.text_input("Profession", placeholder="e.g., Software Engineer")
                with col5:
                    cp_industry = st.text_input("Industry", placeholder="e.g., Technology")

                col6, col7 = st.columns(2)
                with col6:
                    cp_education = st.text_input("Education", placeholder="e.g., MBA from IIM")
                with col7:
                    cp_religion = st.text_input("Religion", placeholder="e.g., Hindu")

                col8, col9 = st.columns(2)
                with col8:
                    cp_residency = st.text_input("Residency Status", placeholder="e.g., Citizen, PR, Work Visa")
                with col9:
                    cp_location = st.text_input("Location", placeholder="e.g., Mumbai, India")

                cp_linkedin = st.text_input("LinkedIn URL", placeholder="https://linkedin.com/in/yourprofile")

                st.markdown("#### Upload Photos (up to 3)")
                st.markdown("<p style='color:#a0a0a0; font-size:14px;'>⚠️ Limit 3 photos to avoid storage issues. For more photos, use image URLs below.</p>", unsafe_allow_html=True)

                uploaded_files = st.file_uploader(
                    "Choose images",
                    type=["jpg", "jpeg", "png", "webp"],
                    accept_multiple_files=True,
                    key="create_profile_images",
                    label_visibility="collapsed"
                )

                # Show image previews
                if uploaded_files:
                    if len(uploaded_files) > 3:
                        st.warning("Maximum 3 images allowed. Only the first 3 will be used.")
                        uploaded_files = uploaded_files[:3]

                    cols = st.columns(min(len(uploaded_files), 3))
                    for idx, (col, file) in enumerate(zip(cols, uploaded_files)):
                        with col:
                            st.image(file, caption=f"Image {idx+1}", width=100)

                # Also allow URL input as fallback
                st.markdown("##### Or enter image URLs (comma-separated, recommended)")
                cp_photo = st.text_input("Photo URLs", placeholder="https://example.com/image1.jpg, https://example.com/image2.jpg", label_visibility="collapsed")

                cp_bio = st.text_area("Bio", placeholder="Tell us about yourself, your interests, and what you're looking for...", height=120)

                if st.form_submit_button("Complete Profile", use_container_width=True):
                    if not cp_name:
                        st.error("Please enter your full name.")
                    else:
                        # Generate ID
                        try:
                            existing_ids = pd.to_numeric(df["ID"], errors="coerce").dropna()
                            next_id = int(existing_ids.max()) + 1 if len(existing_ids) > 0 else 1
                        except Exception:
                            next_id = len(df) + 1

                        # Process uploaded images
                        photo_urls = []
                        if uploaded_files:
                            with st.spinner("Processing images..."):
                                base64_urls = upload_images_to_base64(uploaded_files)
                                if base64_urls:
                                    photo_urls.append(base64_urls)

                        # Add manually entered URLs
                        if cp_photo and cp_photo.strip():
                            photo_urls.append(cp_photo.strip())

                        # Combine all photo URLs
                        final_photo_url = ", ".join(photo_urls) if photo_urls else ""

                        # Validate photo URL length (Google Sheets has 50,000 char limit per cell)
                        if len(final_photo_url) > 45000:
                            st.error("❌ Photo data is too large (>45,000 characters). Please use fewer uploaded images or use image URLs instead of uploading files.")
                        else:
                            new_profile = {
                                "ID": str(next_id),
                                "Email": st.session_state.user_email,
                                "Name": cp_name,
                                "Gender": cp_gender,
                                "Age": cp_age,
                                "Height": cp_height,
                                "Profession": cp_profession,
                                "Industry": cp_industry,
                                "Education": cp_education,
                                "Religion": cp_religion,
                                "Residency_Status": cp_residency,
                                "Location": cp_location,
                                "LinkedIn": cp_linkedin,
                                "PhotoURL": final_photo_url,
                                "Bio": cp_bio,
                                "Status": "Active"
                            }

                            if append_row(new_profile):
                                st.success("Profile created successfully!")
                                # Force refresh to bypass cache
                                st.session_state.df = load_sheet(force_refresh=True)
                                st.rerun()
                            else:
                                st.error("Failed to create profile. Please try again.")
        else:
            col1, col2 = st.columns([1, 2])
            with col1:
                img_url = resolve_image_url(my_profile.get('PhotoURL', '') or my_profile.get('ImageURL', ''))
                if img_url:
                    try:
                        st.image(img_url, width=300)
                    except Exception:
                        st.markdown("<div style='height:300px;background:#2a2a2a;border-radius:12px;display:flex;align-items:center;justify-content:center;color:#666;'>No photo</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='height:300px;background:#2a2a2a;border-radius:12px;display:flex;align-items:center;justify-content:center;color:#666;'>No photo</div>", unsafe_allow_html=True)

            with col2:
                st.markdown(f"### {my_profile.get('Name', 'Unknown')}")
                st.markdown(f"**Email:** {my_profile.get('Email', '')}")

                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown(f"**Age:** {my_profile.get('Age', 'N/A')}")
                    st.markdown(f"**Gender:** {my_profile.get('Gender', 'N/A')}")
                    st.markdown(f"**Height:** {my_profile.get('Height', 'N/A')}")
                    st.markdown(f"**Profession:** {my_profile.get('Profession', 'N/A')}")
                    st.markdown(f"**Industry:** {my_profile.get('Industry', 'N/A')}")

                with col_b:
                    st.markdown(f"**Education:** {my_profile.get('Education', 'N/A')}")
                    st.markdown(f"**Religion:** {my_profile.get('Religion', 'N/A')}")
                    st.markdown(f"**Location:** {my_profile.get('Location', 'N/A')}")
                    st.markdown(f"**Residency:** {my_profile.get('Residency_Status', 'N/A')}")
                    st.markdown(f"**WhatsApp:** {my_profile.get('WhatsApp', 'N/A')}")

                if my_profile.get('LinkedIn'):
                    st.markdown(f"**LinkedIn:** [View Profile]({my_profile.get('LinkedIn')})")

                if my_profile.get('Bio'):
                    st.markdown("**Bio:**")
                    st.markdown(f"<p style='color:#a0a0a0;'>{my_profile.get('Bio', '')}</p>", unsafe_allow_html=True)

            st.markdown("---")
            st.subheader("Edit Your Profile")
            st.markdown("<p style='color:#a0a0a0;'>Update your profile information below.</p>", unsafe_allow_html=True)

            with st.form("edit_profile"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    new_age = st.text_input("Age", value=my_profile.get('Age', '') or '')
                with col2:
                    new_height = st.text_input("Height", value=my_profile.get('Height', '') or '')
                with col3:
                    new_profession = st.text_input("Profession", value=my_profile.get('Profession', '') or '')

                col4, col5 = st.columns(2)
                with col4:
                    new_industry = st.text_input("Industry", value=my_profile.get('Industry', '') or '')
                with col5:
                    new_education = st.text_input("Education", value=my_profile.get('Education', '') or '')

                col6, col7 = st.columns(2)
                with col6:
                    new_religion = st.text_input("Religion", value=my_profile.get('Religion', '') or '')
                with col7:
                    new_location = st.text_input("Location", value=my_profile.get('Location', '') or '')

                col8, col9 = st.columns(2)
                with col8:
                    new_residency = st.text_input("Residency Status", value=my_profile.get('Residency_Status', '') or '')
                with col9:
                    new_whatsapp = st.text_input("WhatsApp", value=my_profile.get('WhatsApp', '') or '')

                new_linkedin = st.text_input("LinkedIn URL", value=my_profile.get('LinkedIn', '') or '')

                st.markdown("#### Update Photos (up to 3)")
                st.markdown("<p style='color:#a0a0a0; font-size:14px;'>⚠️ Limit 3 photos to avoid storage issues. For more photos, use image URLs below.</p>", unsafe_allow_html=True)

                edit_uploaded_files = st.file_uploader(
                    "Choose new images",
                    type=["jpg", "jpeg", "png", "webp"],
                    accept_multiple_files=True,
                    key="edit_profile_images",
                    label_visibility="collapsed"
                )

                # Show image previews
                if edit_uploaded_files:
                    if len(edit_uploaded_files) > 3:
                        st.warning("Maximum 3 images allowed. Only the first 3 will be used.")
                        edit_uploaded_files = edit_uploaded_files[:3]

                    cols = st.columns(min(len(edit_uploaded_files), 3))
                    for idx, (col, file) in enumerate(zip(cols, edit_uploaded_files)):
                        with col:
                            st.image(file, caption=f"New Image {idx+1}", width=100)

                # Also allow URL input
                st.markdown("##### Or enter image URLs (comma-separated, recommended)")
                new_photo = st.text_input("Photo URLs", value=my_profile.get('PhotoURL', '') or my_profile.get('ImageURL', '') or '', label_visibility="collapsed")

                new_bio = st.text_area("Bio", value=my_profile.get('Bio', '') or '', height=100)

                if st.form_submit_button("Save Changes", use_container_width=True):
                    # Process uploaded images
                    photo_urls = []
                    if edit_uploaded_files:
                        with st.spinner("Processing images..."):
                            base64_urls = upload_images_to_base64(edit_uploaded_files, max_images=3)
                            if base64_urls:
                                photo_urls.append(base64_urls)

                    # Add manually entered URLs (or keep existing if not changed)
                    if new_photo and new_photo.strip():
                        photo_urls.append(new_photo.strip())

                    # Combine all photo URLs
                    final_photo_url = ", ".join(photo_urls) if photo_urls else new_photo

                    # Validate photo URL length (Google Sheets has 50,000 char limit per cell)
                    if len(final_photo_url) > 45000:
                        st.error("❌ Photo data is too large (>45,000 characters). Please use fewer uploaded images or use image URLs instead of uploading files.")
                    elif update_profile_by_email(st.session_state.user_email, {
                        'Age': new_age,
                        'Height': new_height,
                        'Profession': new_profession,
                        'Industry': new_industry,
                        'Education': new_education,
                        'Religion': new_religion,
                        'Location': new_location,
                        'Residency_Status': new_residency,
                        'WhatsApp': new_whatsapp,
                        'LinkedIn': new_linkedin,
                        'PhotoURL': final_photo_url,
                        'Bio': new_bio
                    }):
                        st.success("Profile updated successfully!")
                        # Force refresh to show updated data
                        st.session_state.df = load_sheet(force_refresh=True)
                        st.rerun()
                    else:
                        st.error("Failed to update profile. Please try again.")

    elif view == "All Profiles":
        # Founder view: see all profiles
        st.header("All Profiles")
        avail_set = {"available", "single", "open", "active"}
        available = df[df["Status"].fillna("").astype(str).str.lower().isin(avail_set)]
        if available.empty:
            st.info("No available profiles at the moment.")
        else:
            cols = st.columns(3)
            for i, (_, row) in enumerate(available.iterrows()):
                with cols[i % 3]:
                    render_profile_card(row, show_interest_button=False, card_index=i)

    elif view == "God Mode":
        st.markdown("<h2 style='text-align: center;'>God Mode Tools</h2>", unsafe_allow_html=True)
        if not is_founder:
            st.warning("Founder access required. Please log in with a founder account.")
        else:
            tab1, tab2, tab3, tab4 = st.tabs(["Matchmaker", "Pipeline", "Stage Updater", "Manage Profiles"])

            # ============ MATCHMAKER TOOL ============
            with tab1:
                st.subheader("Matchmaker Tool")
                st.markdown("<p style='color:#6b7280;'>Create a new suggestion by selecting a user and a candidate profile.</p>", unsafe_allow_html=True)

                if df.empty or 'Email' not in df.columns:
                    st.warning("No profiles with Email column found.")
                else:
                    all_emails = df['Email'].dropna().tolist()
                    all_emails = [e for e in all_emails if str(e).strip()]

                    if len(all_emails) < 2:
                        st.info(f"📋 You have {len(all_emails)} profile(s) with email. Need at least 2 profiles to create suggestions. Add more profiles in the 'Manage Profiles' tab.")
                    else:
                        selected_user = st.selectbox(
                            "Select User (receives suggestion)",
                            all_emails,
                            key="mm_user",
                            format_func=lambda e: f"{df[df['Email']==e]['Name'].values[0] if len(df[df['Email']==e])>0 else e} ({e})"
                        )

                        candidate_emails = [e for e in all_emails if e != selected_user]
                        selected_candidate = st.selectbox(
                            "Select Candidate (profile to suggest)",
                            candidate_emails,
                            key="mm_candidate",
                            format_func=lambda e: f"{df[df['Email']==e]['Name'].values[0] if len(df[df['Email']==e])>0 else e} ({e})"
                        )

                        if st.button("Add Suggestion", key="add_suggestion_btn"):
                            if suggestion_exists(selected_user, selected_candidate):
                                st.warning("This suggestion already exists.")
                            else:
                                if add_suggestion(selected_user, selected_candidate, "Pending"):
                                    st.success(f"Suggested {selected_candidate} to {selected_user}!")
                                else:
                                    st.error("Failed to add suggestion.")

            # ============ PIPELINE TRACKER ============
            with tab2:
                st.subheader("Pipeline Tracker")
                st.markdown("<p style='color:#6b7280;'>View all 'Liked' suggestions - users who expressed interest.</p>", unsafe_allow_html=True)

                suggestions_df = load_suggestions()
                if suggestions_df is None or suggestions_df.empty:
                    st.info("No suggestions yet.")
                else:
                    liked = suggestions_df[suggestions_df['Status'].fillna('').astype(str).str.lower() == 'liked']

                    if liked.empty:
                        st.info("No 'Liked' suggestions yet. Users haven't expressed interest in any suggestions.")
                    else:
                        display_data = []
                        for _, row in liked.iterrows():
                            user_profile = get_profile_by_email(row['Suggested_To_Email'])
                            candidate_profile = get_profile_by_email(row['Profile_Of_Email'])
                            display_data.append({
                                'User': user_profile.get('Name', row['Suggested_To_Email']) if user_profile else row['Suggested_To_Email'],
                                'User Email': row['Suggested_To_Email'],
                                'Interested In': candidate_profile.get('Name', row['Profile_Of_Email']) if candidate_profile else row['Profile_Of_Email'],
                                'Candidate Email': row['Profile_Of_Email'],
                                'Status': row['Status']
                            })

                        st.dataframe(pd.DataFrame(display_data))

                        st.markdown("---")
                        st.markdown("<p style='color:#6b7280;'>Next step: Contact both parties via WhatsApp to arrange an introduction.</p>", unsafe_allow_html=True)

            # ============ STAGE UPDATER ============
            with tab3:
                st.subheader("Stage Updater")
                st.markdown("<p style='color:#6b7280;'>Move matches through relationship stages.</p>", unsafe_allow_html=True)

                suggestions_df = load_suggestions()
                if suggestions_df is None or suggestions_df.empty:
                    st.info("No suggestions to update.")
                else:
                    active = suggestions_df[suggestions_df['Status'].fillna('').astype(str).str.lower().isin(['liked', 'match', 'date', 'married'])]

                    if active.empty:
                        st.info("No active matches to update. Wait for users to express interest.")
                    else:
                        active = active.copy()
                        active['display'] = active.apply(
                            lambda r: f"{r['Suggested_To_Email']} + {r['Profile_Of_Email']} ({r['Status']})",
                            axis=1
                        )
                        selected = st.selectbox("Select Match", active['display'].tolist(), key="stage_select")

                        if selected:
                            row = active[active['display'] == selected].iloc[0]
                            current_status = row['Status']

                            stages = ["Liked", "Match", "Date", "Married"]
                            current_idx = stages.index(current_status) if current_status in stages else 0

                            new_status = st.selectbox(
                                "Update Status",
                                stages,
                                index=current_idx,
                                key="new_stage"
                            )

                            if st.button("Save Status", key="save_stage_btn"):
                                if update_suggestion_status(row['Suggested_To_Email'], row['Profile_Of_Email'], new_status):
                                    st.success(f"Updated to {new_status}!")
                                    st.rerun()
                                else:
                                    st.error("Failed to update status.")

            # ============ MANAGE PROFILES ============
            with tab4:
                st.subheader("Manage Profiles")

                # Add New Profile
                st.markdown("### Add New Profile")
                with st.form("new_profile_form"):
                    n_email = st.text_input("Email (required)")
                    n_name = st.text_input("Name")
                    n_gender = st.selectbox("Gender", ["", "Male", "Female", "Other"])
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        n_height = st.text_input("Height")
                    with col2:
                        n_industry = st.text_input("Industry")
                    with col3:
                        n_education = st.text_input("Education")

                    n_linkedin = st.text_input("LinkedIn URL")
                    n_whatsapp = st.text_input("WhatsApp Number")
                    n_bio = st.text_area("Bio", height=80)
                    n_photo = st.text_input("Photo URL")
                    n_status = st.selectbox("Status", ["Active", "Available", "Hidden"], index=0)

                    submitted = st.form_submit_button("Add Profile")
                    if submitted:
                        if not n_email:
                            st.error("Email is required.")
                        else:
                            try:
                                existing_ids = pd.to_numeric(df["ID"], errors="coerce").dropna()
                                next_id = int(existing_ids.max()) + 1 if len(existing_ids) > 0 else 1
                            except Exception:
                                next_id = len(df) + 1
                            new_row = {
                                "ID": str(next_id),
                                "Email": n_email,
                                "Name": n_name,
                                "Gender": n_gender,
                                "Height": n_height,
                                "Industry": n_industry,
                                "Education": n_education,
                                "LinkedIn": n_linkedin,
                                "WhatsApp": n_whatsapp,
                                "Bio": n_bio,
                                "PhotoURL": n_photo,
                                "Status": n_status
                            }
                            if append_row(new_row):
                                st.success("Profile added.")
                                st.session_state.df = load_sheet()
                                st.rerun()
                            else:
                                st.error("Failed to add profile.")

                st.markdown("---")
                st.markdown("### All Profiles")
                st.dataframe(df[['Email', 'Name', 'Gender', 'Industry', 'Status']].head(50))

# Footer note
st.markdown("<div class='footer'>Premium matchmaking — built with care.</div>", unsafe_allow_html=True)
