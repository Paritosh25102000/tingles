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

try:
    conn = st.connection("gsheets", type="gsheets")
except Exception:
    conn = None

def init_gspread_from_toml():
    """Fallback initializer that reads .streamlit/secrets.toml and creates a gspread client."""
    global gspread_client, gspread_sh, gspread_ws
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
        return True, "ok"
    except Exception as e:
        return False, str(e)

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
        values = [row_dict.get(h, "") for h in header]
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

# Small connection checker UI
with st.expander("Connection / Sheet check", expanded=True):
    if conn is None:
        st.info("No Streamlit connection named \"gsheets\" is available. Check your .streamlit/secrets.toml and Streamlit connections.")
    else:
        if st.button("Test connection and load sheet"):
            df_test = load_sheet()
            if df_test is not None:
                st.success("Sheet loaded — preview below")
                st.dataframe(df_test.head())

# Main navigation
view = st.sidebar.radio("View", ["Gallery", "God Mode"]) 

# Admin authentication (God Mode)
admin_password = st.secrets.get("admin_password")
admin_input = st.sidebar.text_input("Founder password", type="password")
is_admin = admin_password and admin_input and (admin_input == admin_password)

# Load sheet into session state once
if "df" not in st.session_state:
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
    rename_map = {}
    for col in list(df.columns):
        lower = str(col).strip().lower()
        if lower in alias_map:
            rename_map[col] = alias_map[lower]
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
                    if row.get("ImageURL"):
                        st.image(row.get("ImageURL"), use_column_width=True)
                    st.markdown(f"<h3 class='name'>{row.get('Name','')}</h3>", unsafe_allow_html=True)
                    st.markdown(f"<p class='stats'>Height: {row.get('Height','N/A')} &nbsp;|&nbsp; Industry: {row.get('Industry','N/A')} &nbsp;|&nbsp; Education: {row.get('Education','N/A')}</p>", unsafe_allow_html=True)
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
                        # Find the row index in the original df and update
                        orig_index = row.name
                        if conn is not None:
                            df.at[orig_index, "Status"] = "Interested"
                            df.at[orig_index, "MatchStage"] = "Requested"
                            success = write_sheet(df)
                            if success:
                                st.success("Interest Recorded — the founder will be notified.")
                                st.session_state.df = load_sheet()
                            else:
                                st.error("Failed to record interest. Please check connection.")
                        else:
                            # gspread fallback: update particular row
                            row_number = int(orig_index) + 2
                            ok = update_row_by_number(row_number, {"Status": "Interested", "MatchStage": "Requested"})
                            if ok:
                                st.success("Interest Recorded — the founder will be notified.")
                                st.session_state.df = load_sheet()
                            else:
                                st.error("Failed to record interest via gspread.")
                    st.markdown("</div>", unsafe_allow_html=True)

    elif view == "God Mode":
        st.header("God Mode — Founder Tools")
        if not is_admin:
            st.warning("Enter the founder password in the sidebar to access God Mode.")
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

            st.markdown("---")
            st.subheader("Add New Profile")
            with st.form("new_profile_form"):
                n_name = st.text_input("Name")
                n_image = st.text_input("Image URL")
                n_height = st.text_input("Height")
                n_industry = st.text_input("Industry")
                n_education = st.text_input("Education")
                n_linkedin = st.text_input("LinkedIn URL")
                n_phone = st.text_input("Phone (E.164) for WhatsApp")
                submitted = st.form_submit_button("Add Profile")
                if submitted:
                    new_row = {"Name": n_name, "ImageURL": n_image, "Height": n_height, "Industry": n_industry, "Education": n_education, "LinkedIn": n_linkedin, "Phone": n_phone, "Status": "Available", "MatchStage": ""}
                    if append_row(new_row):
                        st.success("Profile added.")
                        # Reload sheet
                        st.session_state.df = load_sheet()
                    else:
                        st.error("Failed to add profile.")

# Footer note
st.markdown("<div class='footer'>Premium matchmaking — built with care.</div>", unsafe_allow_html=True)
