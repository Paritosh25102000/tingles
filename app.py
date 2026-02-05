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
    """Fallback initializer that reads .streamlit/secrets.toml and creates a gspread client."""
    global gspread_client, gspread_sh, gspread_ws, credentials_ws
    try:
        import toml
        import gspread
    except Exception:
        return False, "missing-packages"
    p = Path(".streamlit/secrets.toml")
    if not p.exists():
        return False, "no-secrets"
    data = toml.loads(p.read_text())
    creds = {k: v for k, v in data.items() if k not in ("auth", "spreadsheet")}
    spreadsheet = data.get("spreadsheet")
    if not spreadsheet:
        return False, "no-spreadsheet"
    try:
        gspread_client = gspread.service_account_from_dict(creds)
        gspread_sh = gspread_client.open_by_url(spreadsheet)
        gspread_ws = gspread_sh.sheet1
        # Try to get credentials sheet (assumes it exists with name "credentials" or "Credentials")
        try:
            credentials_ws = gspread_sh.worksheet("credentials")
        except Exception:
            try:
                credentials_ws = gspread_sh.worksheet("Credentials")
            except Exception:
                credentials_ws = None
        return True, "ok"
    except Exception as e:
        return False, str(e)

def load_credentials():
    """Load username/password/role from credentials sheet."""
    if conn is not None:
        try:
            # Try to read from 'credentials' sheet via st.connection
            # st.connection for gsheets doesn't easily support multiple sheets, so fallback
            pass
        except Exception:
            pass
    
    # Use gspread fallback
    ok, why = init_gspread_from_toml()
    if not ok:
        return None
    
    if credentials_ws is None:
        return None
    
    try:
        records = credentials_ws.get_all_records()
        df = pd.DataFrame(records)
        return df
    except Exception:
        return None

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
            conn.write(df)
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
    """Update specific columns by worksheet row number (1-based including header)."""
    if conn is not None:
        st.error("Row-level update via st.connection not implemented; falling back to full write.")
        return False
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
    """Verify username/password against credentials sheet. Returns (success, role) tuple."""
    creds_df = load_credentials()
    if creds_df is None or creds_df.empty:
        return False, None
    
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
        return False, None
    
    # Find matching user
    for idx, row in creds_df.iterrows():
        if str(row.get(username_col, "")).strip() == str(username).strip():
            if str(row.get(password_col, "")).strip() == str(password).strip():
                role = str(row.get(role_col, "")).strip().lower()
                return True, role
    
    return False, None

def logout():
    """Clear login session."""
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None

# ============ LOGIN PAGE ============
if not st.session_state.logged_in:
    st.markdown("<div style='text-align: center; padding: 60px 20px;'>", unsafe_allow_html=True)
    st.markdown("<h2 style='font-family: Playfair Display, serif; font-size: 48px; margin-bottom: 30px;'>Welcome to Tingles</h2>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 18px; color: #98a2ab; margin-bottom: 50px;'>Boutique Matchmaking Platform</p>", unsafe_allow_html=True)
    
    login_col1, login_col2, login_col3 = st.columns([1, 2, 1])
    with login_col2:
        st.markdown("### Login")
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        
        if st.button("Sign In", use_container_width=True):
            if username and password:
                success, role = authenticate_user(username, password)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = role
                    st.success(f"Welcome, {username}!")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
            else:
                st.warning("Please enter both username and password.")
    
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
                        # Find the row index in the original df and update locally first
                        orig_index = row.name
                        # Update local copy so UI reflects interest immediately
                        try:
                            df.at[orig_index, "Status"] = "Interested"
                            df.at[orig_index, "MatchStage"] = "Requested"
                            st.session_state.df = df
                        except Exception:
                            st.warning("Could not update local state; proceeding to attempt sheet update.")

                        # Then persist the change to the sheet (preferred via st.connection)
                        persist_ok = False
                        if conn is not None:
                            try:
                                # write_sheet overwrites full sheet when using st.connection
                                persist_ok = write_sheet(df)
                                if not persist_ok:
                                    st.warning("Local state updated but failed to persist full sheet via st.connection.")
                            except Exception as e:
                                st.warning(f"Local state updated but st.connection write failed: {e}")
                        else:
                            # gspread fallback: locate the row by ID or Name then update
                            identifiers = {"ID": row.get("ID"), "Name": row.get("Name")}
                            row_number = find_sheet_row_number(identifiers)
                            if row_number:
                                try:
                                    persist_ok = update_row_by_number(row_number, {"Status": "Interested", "MatchStage": "Requested"})
                                    if not persist_ok:
                                        st.warning("Local state updated but failed to persist change via gspread.")
                                except Exception as e:
                                    st.warning(f"Local state updated but gspread update failed: {e}")
                            
                            # Always try to append as fallback to ensure persistence (creates a duplicate that founder can clean up)
                            if not row_number or not persist_ok:
                                try:
                                    new_row = {"Name": row.get("Name",""), "ImageURL": row.get("ImageURL",""), "Status": "Interested", "MatchStage": "Requested", "Phone": row.get("Phone","")}
                                    appended = append_row(new_row)
                                    if appended:
                                        st.info("Interest persisted by appending a new sheet record.")
                                        # Reload immediately to show persistence
                                        st.session_state.df = load_sheet()
                                except Exception as e:
                                    st.warning(f"Could not append persistence record: {e}")

                        st.success("Interest recorded locally.")
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
