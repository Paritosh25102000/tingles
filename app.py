import streamlit as st
import pandas as pd
from urllib.parse import quote_plus
from pathlib import Path

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

# Prefer Streamlit's connection API, but fall back to gspread if unavailable
conn = None
gspread_client = None
gspread_sh = None
gspread_ws = None
credentials_ws = None  # For credentials sheet

try:
    conn = st.connection("gsheets", type="gsheets")
except Exception:
    conn = None

def init_gspread_from_toml():
    """Initialize gspread client from secrets (st.secrets on Cloud, or .streamlit/secrets.toml locally)."""
    global gspread_client, gspread_sh, gspread_ws, credentials_ws

    # Return early if already initialized
    if gspread_ws is not None:
        return True, "ok"

    try:
        import gspread
    except Exception:
        return False, "gspread package not installed"

    # Try st.secrets first (works on Streamlit Cloud)
    data = None
    try:
        data = dict(st.secrets)
    except Exception:
        pass

    # Fallback to local file
    if not data:
        try:
            import toml
            p = Path(".streamlit/secrets.toml")
            if p.exists():
                data = toml.loads(p.read_text())
        except Exception:
            pass

    if not data:
        return False, "no-secrets: st.secrets empty and no local secrets.toml"

    # Extract service account credentials (exclude non-credential keys)
    creds = {k: v for k, v in data.items() if k not in ("auth", "spreadsheet", "connections")}
    # Also check nested gsheets connection format
    if "connections" in data and "gsheets" in data["connections"]:
        gsheets_conn = data["connections"]["gsheets"]
        if "spreadsheet" in gsheets_conn:
            spreadsheet = gsheets_conn["spreadsheet"]
        else:
            spreadsheet = data.get("spreadsheet")
        # Service account info might be nested
        if "service_account" in gsheets_conn:
            creds = dict(gsheets_conn["service_account"])
    else:
        spreadsheet = data.get("spreadsheet")

    if not spreadsheet:
        return False, f"no-spreadsheet key in secrets. Keys found: {list(data.keys())}"

    try:
        gspread_client = gspread.service_account_from_dict(creds)
        gspread_sh = gspread_client.open_by_url(spreadsheet)
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
                credentials_ws.append_row(["username", "password", "role"])
            except Exception as e:
                return False, f"credentials sheet not found and could not create. Available sheets: {all_sheets}. Error: {e}"

    return True, "ok"

def load_credentials():
    """Load username/password/role from credentials sheet. Returns (df, error_msg) tuple."""
    # Use gspread (works on both local and Streamlit Cloud)
    ok, why = init_gspread_from_toml()
    if not ok:
        return None, f"gspread init failed: {why}"

    if credentials_ws is None:
        return None, "credentials_ws is None after init"

    try:
        records = credentials_ws.get_all_records()
        df = pd.DataFrame(records)
        return df, None
    except Exception as e:
        return None, f"Failed to read credentials sheet: {e}"

# Sheet helpers supporting both conn and gspread fallback
def load_sheet():
    if conn is not None:
        try:
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
            "photo_url": "ImageURL",
            "imageurl": "ImageURL",
            "image_url": "ImageURL",
            "height": "Height",
            "industry": "Industry",
            "education": "Education",
            "linkedin_url": "LinkedIn",
            "linkedin": "LinkedIn",
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
    st.session_state.username = None
    st.session_state.role = None

def authenticate_user(username, password):
    """Verify username/password against credentials sheet. Returns (success, role, error_msg) tuple."""
    creds_df, load_error = load_credentials()
    if creds_df is None:
        return False, None, f"Could not load credentials: {load_error}"
    if creds_df.empty:
        return False, None, "Credentials sheet is empty. Add users to the 'credentials' sheet."

    # Normalize column names (handle common variants)
    creds_df.columns = creds_df.columns.str.lower().str.strip()

    # Find username/password/role columns
    username_col = None
    password_col = None
    role_col = None

    for col in creds_df.columns:
        if "username" in col or "user" in col:
            username_col = col
        if "password" in col or "pass" in col:
            password_col = col
        if "role" in col:
            role_col = col

    if not username_col or not password_col or not role_col:
        return False, None, f"Credentials sheet missing required columns. Found: {list(creds_df.columns)}"

    # Find matching user
    for idx, row in creds_df.iterrows():
        if str(row.get(username_col, "")).strip() == str(username).strip():
            if str(row.get(password_col, "")).strip() == str(password).strip():
                role = str(row.get(role_col, "")).strip().lower()
                return True, role, None

    return False, None, "Invalid username or password."

def logout():
    """Clear login session."""
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None

def username_exists(username):
    """Check if username is already taken."""
    creds_df, _ = load_credentials()
    if creds_df is None or creds_df.empty:
        return False
    creds_df.columns = creds_df.columns.str.lower().str.strip()
    for col in creds_df.columns:
        if "username" in col or "user" in col:
            for idx, row in creds_df.iterrows():
                if str(row.get(col, "")).strip().lower() == str(username).strip().lower():
                    return True
    return False

def create_new_user(username, password, role="user"):
    """Add new user to credentials sheet. Returns (success, message)."""
    if username_exists(username):
        return False, "Username already taken."
    
    ok, why = init_gspread_from_toml()
    if not ok:
        return False, f"Could not connect to sheet: {why}"
    
    if credentials_ws is None:
        return False, "Could not create or access credentials sheet. Ensure service account has edit permissions."
    
    try:
        # Get header to determine column order
        header = credentials_ws.row_values(1)
        if not header or header == []:
            # Sheet exists but is empty; add headers
            credentials_ws.append_row(["username", "password", "role"])
            header = ["username", "password", "role"]
        
        username_col = None
        password_col = None
        role_col = None
        
        for i, col in enumerate(header):
            col_lower = str(col).strip().lower()
            if "username" in col_lower or "user" in col_lower:
                username_col = i
            if "password" in col_lower or "pass" in col_lower:
                password_col = i
            if "role" in col_lower:
                role_col = i
        
        if username_col is None or password_col is None or role_col is None:
            return False, "Credentials sheet missing required columns (username, password, role). Please set up the sheet manually."
        
        # Build row values matching header order
        row_values = [""] * len(header)
        row_values[username_col] = username
        row_values[password_col] = password
        row_values[role_col] = role
        
        credentials_ws.append_row(row_values)
        return True, "Account created successfully! Please log in."
    except Exception as e:
        return False, f"Failed to create account: {str(e)}"

# ============ LOGIN / SIGN-UP PAGE ============
# Initialize signup mode state
if "signup_mode" not in st.session_state:
    st.session_state.signup_mode = False

if not st.session_state.logged_in:
    st.markdown("<div style='text-align: center; padding: 60px 20px;'>", unsafe_allow_html=True)
    st.markdown("<h2 style='font-family: Playfair Display, serif; font-size: 48px; margin-bottom: 30px;'>Welcome to Tingles</h2>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 18px; color: #98a2ab; margin-bottom: 50px;'>Boutique Matchmaking Platform</p>", unsafe_allow_html=True)
    
    login_col1, login_col2, login_col3 = st.columns([1, 2, 1])
    with login_col2:
        # Toggle between Login and Sign Up
        tab1, tab2 = st.tabs(["Sign In", "Sign Up"])
        
        with tab1:
            st.markdown("### Login to Your Account")
            username = st.text_input("Username", placeholder="Enter your username", key="login_username")
            password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_password")
            
            if st.button("Sign In", use_container_width=True, key="signin_btn"):
                if username and password:
                    success, role, error_msg = authenticate_user(username, password)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.session_state.role = role
                        st.success(f"Welcome, {username}!")
                        st.rerun()
                    else:
                        st.error(error_msg)
                else:
                    st.warning("Please enter both username and password.")
        
        with tab2:
            st.markdown("### Create a New Account")
            signup_username = st.text_input("Choose a username", placeholder="Enter your desired username", key="signup_username")
            signup_password = st.text_input("Choose a password", type="password", placeholder="Enter a password", key="signup_password")
            signup_confirm = st.text_input("Confirm password", type="password", placeholder="Re-enter your password", key="signup_confirm")
            
            if st.button("Create Account", use_container_width=True, key="signup_btn"):
                if not signup_username or not signup_password or not signup_confirm:
                    st.warning("Please fill in all fields.")
                elif signup_password != signup_confirm:
                    st.error("Passwords do not match.")
                elif len(signup_password) < 6:
                    st.error("Password must be at least 6 characters long.")
                elif len(signup_username) < 3:
                    st.error("Username must be at least 3 characters long.")
                else:
                    success, message = create_new_user(signup_username, signup_password, role="user")
                    if success:
                        st.success(message)
                        st.info("Redirecting to login page in 2 seconds...")
                        import time
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(message)
    
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()  # Stop execution here; don't show main app until logged in

# ============ MAIN APP (logged in) ============
# Top-right logout button
logout_col1, logout_col2 = st.columns([8, 2])
with logout_col2:
    st.markdown(f"**{st.session_state.username}** ({st.session_state.role})")
    if st.button("Logout", use_container_width=True):
        logout()
        st.rerun()

# Determine which view to show based on role
is_founder = st.session_state.role == "founder"

if is_founder:
    view = "God Mode"  # Founder always sees God Mode (no choice)
else:
    view = "Gallery"  # Regular users always see Gallery

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
        "photo_url": "ImageURL",
        "imageurl": "ImageURL",
        "image_url": "ImageURL",
        "height": "Height",
        "industry": "Industry",
        "profession": "Industry",
        "job": "Industry",
        "education": "Education",
        "linkedin_url": "LinkedIn",
        "linkedin": "LinkedIn",
        "status": "Status",
        "match_stage": "MatchStage",
        "matchstage": "MatchStage",
        "phone": "Phone",
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
    expected_columns = ["Name", "ImageURL", "Height", "Industry", "Education", "LinkedIn", "Status", "MatchStage", "Phone"]
    for col in expected_columns:
        if col not in df.columns:
            df[col] = ""
    st.session_state.df = df

    if view == "Gallery":
        st.header("Gallery")
        # Treat common 'available' synonyms from sheets as available
        avail_set = {"available", "single", "open"}
        available = df[df["Status"].fillna("").astype(str).str.lower().isin(avail_set)]
        if available.empty:
            st.info("No available profiles at the moment.")
        else:
            cols = st.columns(3)
            for i, (_, row) in enumerate(available.iterrows()):
                with cols[i % 3]:
                    st.markdown(f"<div class='profile-card'>", unsafe_allow_html=True)
                    def _scalar(v):
                        import pandas as _pd
                        if v is None:
                            return ""
                        if isinstance(v, _pd.Series) or isinstance(v, list) or isinstance(v, tuple):
                            try:
                                return str(v.iloc[0]) if hasattr(v, 'iloc') else str(v[0])
                            except Exception:
                                return str(v)
                        return str(v)
                    img_raw = _scalar(row.get("ImageURL",""))
                    img_url = resolve_image_url(img_raw) if img_raw else None
                    if img_url:
                        try:
                            st.image(img_url, width=300)
                        except Exception as e:
                            st.markdown(f"<div style='height:260px;background:#0f1724;border-radius:8px;display:flex;align-items:center;justify-content:center;color:var(--muted)'>Image unavailable<br/><small>{str(e)[:50]}</small></div>", unsafe_allow_html=True)
                    else:
                        st.markdown("<div style='height:260px;background:#0f1724;border-radius:8px;display:flex;align-items:center;justify-content:center;color:var(--muted)'>No image</div>", unsafe_allow_html=True)
                    st.markdown(f"<h3 class='name'>{_scalar(row.get('Name',''))}</h3>", unsafe_allow_html=True)
                    st.markdown(f"<p class='stats'>Height: {_scalar(row.get('Height','N/A'))} &nbsp;|&nbsp; Industry: {_scalar(row.get('Industry','N/A'))} &nbsp;|&nbsp; Education: {_scalar(row.get('Education','N/A'))}</p>", unsafe_allow_html=True)
                    # LinkedIn button (opens in new tab)
                    linkedin = row.get("LinkedIn", "")
                    if linkedin:
                        st.markdown(f"<a class='btn btn-link' target='_blank' href='{linkedin}'>View LinkedIn</a>", unsafe_allow_html=True)
                    # If MatchStage == Date, show WhatsApp
                    if str(row.get("MatchStage","")).lower() == "date":
                        phone = row.get("Phone","")
                        if phone:
                            wa_link = f"https://wa.me/{quote_plus(str(phone))}"
                            st.markdown(f"<a class='btn btn-wa' target='_blank' href='{wa_link}'>Chat on WhatsApp</a>", unsafe_allow_html=True)
                    # Express Interest button
                    key = f"express_{i}"
                    if st.button("Express Interest", key=key):
                        # Persist to Google Sheet using gspread (most reliable method)
                        persist_ok = False

                        # Always use gspread for writes - it's more reliable than st.connection
                        identifiers = {"ID": row.get("ID"), "Name": row.get("Name")}
                        row_number = find_sheet_row_number(identifiers)

                        if row_number:
                            try:
                                persist_ok = update_row_by_number(row_number, {"Status": "Interested", "MatchStage": "Requested"})
                            except Exception as e:
                                st.error(f"Failed to update sheet: {e}")

                        if not persist_ok:
                            st.error("Could not update the Google Sheet. Please check service account permissions.")
                        else:
                            st.success("Interest recorded!")

                        # Reload data from sheet to reflect changes
                        st.session_state.df = load_sheet()
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

    elif view == "God Mode":
        st.header("God Mode — Founder Tools")
        if not is_founder:
            st.warning("Founder access required. Please log in with a founder account.")
        else:
            st.success("Founder access granted")
            # Show table of Interested profiles
            interested = df[df["Status"].str.lower() == "interested"]
            st.subheader("Interested Profiles")
            st.dataframe(interested)

            # Select a profile to edit MatchStage
            if not interested.empty:
                sel_index = st.selectbox("Select profile to update", interested.index.tolist(), format_func=lambda idx: df.at[idx, "Name"])
                current_stage = df.at[sel_index, "MatchStage"]
                new_stage = st.selectbox("MatchStage", ["Requested","Date","Relationship","Engaged","Married"], index=(0 if current_stage not in ["Requested","Date","Relationship","Engaged","Married"] else ["Requested","Date","Relationship","Engaged","Married"].index(current_stage)))
                if st.button("Save MatchStage"):
                    if conn is not None:
                        df.at[sel_index, "MatchStage"] = new_stage
                        if write_sheet(df):
                            st.success("MatchStage updated.")
                            st.session_state.df = load_sheet()
                        else:
                            st.error("Failed to save MatchStage.")
                    else:
                        row_number = int(sel_index) + 2
                        ok = update_row_by_number(row_number, {"MatchStage": new_stage})
                        if ok:
                            st.success("MatchStage updated.")
                            st.session_state.df = load_sheet()
                        else:
                            st.error("Failed to save MatchStage via gspread.")

                # Founder controls: clear interest or delete profile
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Clear Interest"):
                        # set status back to Available and clear MatchStage locally
                        try:
                            df.at[sel_index, "Status"] = "Available"
                            df.at[sel_index, "MatchStage"] = ""
                            st.session_state.df = df
                        except Exception:
                            pass
                        # persist
                        if conn is not None:
                            if write_sheet(df):
                                st.success("Interest cleared and persisted.")
                                st.session_state.df = load_sheet()
                            else:
                                st.warning("Cleared locally but failed to persist via st.connection.")
                        else:
                            identifiers = {"ID": df.at[sel_index, "ID"] if "ID" in df.columns else None, "Name": df.at[sel_index, "Name"]}
                            row_number = find_sheet_row_number(identifiers)
                            if row_number:
                                if update_row_by_number(row_number, {"Status": "Available", "MatchStage": ""}):
                                    st.success("Interest cleared.")
                                    st.session_state.df = load_sheet()
                                else:
                                    st.warning("Cleared locally but failed to persist via gspread.")
                            else:
                                st.warning("Cleared locally but could not locate sheet row to persist change.")
                with col2:
                    if st.button("Delete Profile"):
                        # remove profile from sheet and local df
                        identifiers = {"ID": df.at[sel_index, "ID"] if "ID" in df.columns else None, "Name": df.at[sel_index, "Name"]}
                        row_number = find_sheet_row_number(identifiers)
                        if conn is not None:
                            # remove from local df and overwrite sheet
                            try:
                                df2 = df.drop(index=sel_index).reset_index(drop=True)
                                if write_sheet(df2):
                                    st.success("Profile deleted.")
                                    st.session_state.df = load_sheet()
                                else:
                                    st.error("Failed to delete profile via st.connection.")
                            except Exception as e:
                                st.error(f"Deletion failed: {e}")
                        else:
                            if row_number:
                                try:
                                    gspread_ws.delete_rows(row_number)
                                    st.success("Profile deleted from sheet.")
                                    st.session_state.df = load_sheet()
                                except Exception as e:
                                    st.error(f"Failed to delete row via gspread: {e}")
                            else:
                                st.error("Could not locate profile row to delete.")

            st.markdown("---")
            st.subheader("Add New Profile")
            with st.form("new_profile_form"):
                n_name = st.text_input("Name")
                col1, col2, col3 = st.columns(3)
                with col1:
                    n_age = st.text_input("Age")
                    n_height = st.text_input("Height")
                with col2:
                    n_profession = st.text_input("Profession")
                    n_industry = st.text_input("Industry")
                with col3:
                    n_education = st.text_input("Education")
                    n_religion = st.text_input("Religion")
                
                n_residency = st.text_input("Residency Status")
                n_location = st.text_input("Location")
                n_linkedin = st.text_input("LinkedIn URL")
                n_bio = st.text_area("Bio", height=80)
                n_photo = st.text_input("Photo URL")
                n_status = st.selectbox("Status", ["Available", "Interested", "Single", "Open"], index=0)
                n_phone = st.text_input("Phone (E.164) for WhatsApp")
                
                submitted = st.form_submit_button("Add Profile")
                if submitted:
                    # Generate a unique ID (max existing ID + 1, or 1 if none)
                    try:
                        existing_ids = pd.to_numeric(df["ID"], errors="coerce").dropna()
                        next_id = int(existing_ids.max()) + 1 if len(existing_ids) > 0 else 1
                    except Exception:
                        next_id = len(df) + 1
                    new_row = {
                        "ID": str(next_id),
                        "Name": n_name,
                        "Age": n_age,
                        "Height": n_height,
                        "Profession": n_profession,
                        "Industry": n_industry,
                        "Education": n_education,
                        "Religion": n_religion,
                        "Residency_Status": n_residency,
                        "Location": n_location,
                        "LinkedIn": n_linkedin,
                        "Bio": n_bio,
                        "ImageURL": n_photo,
                        "Status": n_status,
                        "Phone": n_phone,
                        "MatchStage": ""
                    }
                    if append_row(new_row):
                        st.success("Profile added.")
                        # Reload sheet
                        st.session_state.df = load_sheet()
                    else:
                        st.error("Failed to add profile.")

# Footer note
st.markdown("<div class='footer'>Premium matchmaking — built with care.</div>", unsafe_allow_html=True)
