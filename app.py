import streamlit as st
import pandas as pd
from urllib.parse import quote_plus
from pathlib import Path
import base64
import io
from PIL import Image
from db import get_db
from oauth_handler import OAuthHandler, create_oauth_buttons

st.set_page_config(
    page_title="Tingles — Boutique Matchmaking",
    layout="wide",
    initial_sidebar_state="expanded"  # Always show sidebar by default
)

# Load custom CSS
try:
    with open("style.css", "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    st.warning("style.css not found — default styling will apply.")

# Additional aggressive CSS override for dropdowns
st.markdown("""
<style>
/* Ultimate nuclear option for selectbox visibility */

/* Target all possible selectbox containers */
[data-baseweb="select"],
[data-baseweb="select"] *,
div[data-baseweb="select"],
div[data-baseweb="select"] *,
.stSelectbox [data-baseweb="select"],
.stSelectbox [data-baseweb="select"] * {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
    background: transparent !important;
}

/* Target the main control container */
div[data-baseweb="select"] > div[class*="control"] {
    background-color: rgba(255, 255, 255, 0.08) !important;
    border-color: rgba(255, 255, 255, 0.1) !important;
}

/* Target ALL possible value containers and their children */
div[data-baseweb="select"] [class*="ValueContainer"],
div[data-baseweb="select"] [class*="ValueContainer"] *,
div[data-baseweb="select"] [class*="singleValue"],
div[data-baseweb="select"] [class*="singleValue"] *,
div[data-baseweb="select"] [class*="placeholder"],
div[data-baseweb="select"] [class*="Input"],
div[data-baseweb="select"] [class*="Input"] * {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}

/* Make sure all divs and spans inside get white text */
div[data-baseweb="select"] div[class],
div[data-baseweb="select"] span[class] {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}

/* Override any opacity settings that might hide text */
div[data-baseweb="select"] * {
    opacity: 1 !important;
}

/* Force sidebar to be visible and prominent */
[data-testid="stSidebar"] {
    display: block !important;
    visibility: visible !important;
    min-width: 280px !important;
}

[data-testid="stSidebar"] > div {
    display: block !important;
    visibility: visible !important;
}

/* Ensure sidebar toggle button is visible */
[data-testid="collapsedControl"] {
    display: block !important;
    visibility: visible !important;
}
</style>
""", unsafe_allow_html=True)

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

# ============ IMAGE HELPERS ============
def split_image_urls(img_raw):
    """
    Split multiple image URLs that may be comma-separated.
    Handles data URIs correctly (which contain commas in 'base64,').
    Returns list of individual image URLs.
    """
    if not img_raw or not str(img_raw).strip():
        return []

    img_str = str(img_raw).strip()

    # If it looks like a data URI, use smart splitting
    if 'data:image' in img_str:
        # Split by the pattern that separates data URIs: ", data:image"
        import re
        # Split but keep the delimiter
        parts = re.split(r',\s*(?=data:image)', img_str)
        return [part.strip() for part in parts if part.strip()]
    else:
        # Regular comma split for HTTP URLs
        return [url.strip() for url in img_str.split(',') if url.strip()]


def resolve_image_url(url):
    """
    Resolve and validate image URL.
    For data URIs (base64), return as-is.
    For HTTP(S) URLs, return as-is.
    Returns None for invalid/empty URLs.
    """
    if not url or not str(url).strip():
        return None

    url_str = str(url).strip()

    # Data URI (base64 encoded images)
    if url_str.startswith('data:image'):
        return url_str

    # HTTP(S) URLs
    if url_str.startswith('http://') or url_str.startswith('https://'):
        return url_str

    # Google Drive direct download links
    if 'drive.google.com' in url_str:
        return url_str

    # Unknown format - return as-is and let the browser handle it
    return url_str if len(url_str) > 0 else None


def upload_images_to_base64(uploaded_files, max_images=3):
    """Convert uploaded images to base64 data URIs (max 3 images).

    Note: Supabase can handle much larger images than Google Sheets.
    Each image is compressed to ~75KB file size (~100KB base64).
    """
    if not uploaded_files:
        return ""

    image_urls = []
    MAX_BASE64_LENGTH_PER_IMAGE = 100000  # ~75KB file size after base64 encoding

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

            # Try progressively smaller sizes until under limit
            attempts = [
                (1200, 85),  # 1200px max dimension, quality 85
                (1000, 80),  # 1000px, quality 80
                (800, 75),   # 800px, quality 75
                (600, 70),   # 600px, quality 70
                (400, 60),   # 400px, quality 60 (last resort)
            ]

            success = False
            for max_dimension, quality in attempts:
                # Resize image maintaining aspect ratio
                img_copy = img.copy()
                img_copy.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

                # Convert to base64
                buffered = io.BytesIO()
                img_copy.save(buffered, format="JPEG", quality=quality, optimize=True)
                img_str = base64.b64encode(buffered.getvalue()).decode()

                data_uri = f"data:image/jpeg;base64,{img_str}"

                # Check if under limit
                if len(data_uri) <= MAX_BASE64_LENGTH_PER_IMAGE:
                    image_urls.append(data_uri)
                    success = True
                    break

            if not success:
                st.warning(f"Image '{file.name}' is too large even after compression. Please use a smaller image file.")
        except Exception as e:
            st.warning(f"Failed to process {file.name}: {e}")
            continue

    # Return comma-separated URLs
    return ", ".join(image_urls)

# Initialize database adapter (uses db_backend from secrets to select Google Sheets or Supabase)
db = get_db()

# Founder email for God Mode access (configure in secrets.toml)
try:
    FOUNDER_EMAIL = st.secrets.get("founder_email", "founder@tingles.com")
except Exception:
    FOUNDER_EMAIL = "founder@tingles.com"

# ============ LOGIN SYSTEM ============
# Initialize login state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_email = None
    st.session_state.role = None


def logout():
    """Clear login session."""
    st.session_state.logged_in = False
    st.session_state.user_email = None
    st.session_state.role = None


# ============ OAUTH CALLBACK HANDLING ============
# Handle OAuth callback before showing login UI
if not st.session_state.logged_in:
    oauth_handler = OAuthHandler()
    user_info = oauth_handler.handle_oauth_callback()

    if user_info:
        # User authenticated via OAuth
        email = user_info.get("email")
        name = user_info.get("name", "")
        provider = user_info.get("provider", "unknown")

        if email:
            # Get or create OAuth user
            success, role, error_msg = db.get_or_create_oauth_user(
                email=email,
                name=name,
                provider=provider,
                oauth_id=email  # Use email as oauth_id for now
            )

            if success:
                st.session_state.logged_in = True
                st.session_state.user_email = email
                st.session_state.role = role
                st.success(f"Welcome, {name or email}!")
                st.rerun()
            else:
                st.error(error_msg or "Failed to authenticate with OAuth.")
        else:
            st.error("Could not retrieve email from OAuth provider.")

# ============ LOGIN / SIGNUP PAGE ============
if not st.session_state.logged_in:
    st.markdown("<div style='padding: 40px 20px;'>", unsafe_allow_html=True)

    login_col1, login_col2, login_col3 = st.columns([1, 2, 1])
    with login_col2:
        auth_tab = st.tabs(["Sign In", "Sign Up"])

        # ============ SIGN IN TAB ============
        with auth_tab[0]:
            st.markdown("<p style='text-align: center; color: #6b7280; font-size: 14px;'>Enter your credentials to sign in.</p>", unsafe_allow_html=True)
            login_email = st.text_input("Email", placeholder="Enter your email", key="login_email")
            login_password = st.text_input("Password", placeholder="Enter your password", type="password", key="login_password")

            if st.button("Sign In", use_container_width=True, key="signin_btn"):
                if login_email and login_password:
                    success, role, error_msg = db.authenticate_user(login_email, login_password)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.user_email = login_email
                        st.session_state.role = role
                        # Get user's name for greeting
                        profile = db.get_profile_by_email(login_email)
                        name = profile.get('Name', login_email) if profile else login_email
                        st.success(f"Welcome, {name}!")
                        st.rerun()
                    else:
                        st.error(error_msg)
                else:
                    st.warning("Please enter both email and password.")

            # OAuth buttons for sign in
            create_oauth_buttons(show_setup_info=False, key_prefix="signin_")

        # ============ SIGN UP TAB ============
        with auth_tab[1]:
            st.markdown("<p style='text-align: center; color: #6b7280; font-size: 14px;'>Create a new account to join Tingles.</p>", unsafe_allow_html=True)
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
                    success, err = db.add_credential(signup_email, signup_password, "user")
                    if success:
                        st.success("Account created! You can now sign in.")
                    else:
                        st.error(err)

            # OAuth buttons for sign up - show setup info
            create_oauth_buttons(show_setup_info=True, key_prefix="signup_")

    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()  # Stop execution here; don't show main app until logged in

# ============ MAIN APP (logged in) ============
# Get user profile for display
user_profile = db.get_profile_by_email(st.session_state.user_email)
user_display_name = user_profile.get('Name', st.session_state.user_email) if user_profile else st.session_state.user_email

# Determine which view to show based on role
is_founder = st.session_state.role == "founder"

# ============ PROFILE COMPLETION CHECK ============
# Check if profile is complete (required fields filled)
def is_profile_complete(profile):
    """Check if user has completed their profile with minimum required information."""
    if not profile:
        return False

    # Required fields for a complete profile
    required_fields = ['Name', 'Gender', 'Age']

    for field in required_fields:
        value = profile.get(field, '')
        if not value or str(value).strip() == '':
            return False

    return True

profile_complete = is_profile_complete(user_profile)

# For non-founder users with incomplete profiles, force them to complete profile first
if not is_founder and not profile_complete:
    # Show only profile completion - no sidebar navigation
    st.markdown("<div style='padding: 20px;'>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>Welcome to Tingles</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #6b7280; font-size: 16px;'>Before you can view curated matches, please complete your profile.</p>", unsafe_allow_html=True)
    st.markdown("---")

    # Logout button at the top
    if st.button("Logout", key="logout_incomplete"):
        logout()
        st.rerun()

    st.markdown("---")

    # Show profile creation form (we'll reuse the form from My Profile section)
    st.markdown("<h3 style='text-align: center;'>Complete Your Profile</h3>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color:#a0a0a0;'>Fill in your details below to get started with matchmaking.</p>", unsafe_allow_html=True)

    with st.form("create_profile_required"):
        cp_name = st.text_input("Full Name *", placeholder="Enter your full name", value=user_profile.get('Name', '') if user_profile else '')

        col1, col2, col3 = st.columns(3)
        with col1:
            cp_age = st.text_input("Age *", placeholder="e.g., 28", value=user_profile.get('Age', '') if user_profile else '')
        with col2:
            cp_height = st.text_input("Height", placeholder="e.g., 5'10\"", value=user_profile.get('Height', '') if user_profile else '')
        with col3:
            current_gender = user_profile.get('Gender', 'Male') if user_profile else 'Male'
            gender_options = ["Male", "Female", "Other"]
            gender_index = gender_options.index(current_gender) if current_gender in gender_options else 0
            cp_gender = st.radio("Gender *", gender_options, index=gender_index, horizontal=True)

        col4, col5 = st.columns(2)
        with col4:
            cp_profession = st.text_input("Profession", placeholder="e.g., Software Engineer", value=user_profile.get('Profession', '') if user_profile else '')
        with col5:
            cp_industry = st.text_input("Industry", placeholder="e.g., Technology", value=user_profile.get('Industry', '') if user_profile else '')

        col6, col7 = st.columns(2)
        with col6:
            cp_education = st.text_input("Education", placeholder="e.g., MBA from IIM", value=user_profile.get('Education', '') if user_profile else '')
        with col7:
            cp_religion = st.text_input("Religion", placeholder="e.g., Hindu", value=user_profile.get('Religion', '') if user_profile else '')

        col8, col9 = st.columns(2)
        with col8:
            cp_residency = st.text_input("Residency Status", placeholder="e.g., Citizen, PR, Work Visa", value=user_profile.get('Residency_Status', '') if user_profile else '')
        with col9:
            cp_location = st.text_input("Location", placeholder="e.g., Mumbai, India", value=user_profile.get('Location', '') if user_profile else '')

        cp_linkedin = st.text_input("LinkedIn URL", placeholder="https://linkedin.com/in/yourprofile", value=user_profile.get('LinkedIn', '') if user_profile else '')

        st.markdown("#### Upload Photos (up to 3)")
        st.markdown("<p style='color:#a0a0a0; font-size:14px;'>Upload up to 3 high-quality photos. Images will be optimized for best quality.</p>", unsafe_allow_html=True)

        uploaded_files = st.file_uploader(
            "Choose images",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            key="create_profile_required_images",
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

        cp_bio = st.text_area("Bio", placeholder="Tell us about yourself, your interests, and what you're looking for...", height=120, value=user_profile.get('Bio', '') if user_profile else '')

        st.markdown("<p style='color:#dc2626; font-size:14px; margin-top:10px;'>* Required fields</p>", unsafe_allow_html=True)

        if st.form_submit_button("Complete Profile & Start Matchmaking", use_container_width=True):
            if not cp_name or not cp_age or not cp_gender:
                st.error("Please fill in all required fields: Name, Age, and Gender.")
            else:
                # Process uploaded images
                final_photo_url = ""
                if uploaded_files:
                    with st.spinner("Processing images..."):
                        final_photo_url = upload_images_to_base64(uploaded_files)
                elif user_profile:
                    # Keep existing photos if no new uploads
                    final_photo_url = user_profile.get('PhotoURL', '')

                # Validate photo data length (max ~300KB for 3 images)
                if len(final_photo_url) > 300000:
                    st.error("❌ Photo data is too large (>300KB). Please use fewer or smaller images.")
                else:
                    if user_profile:
                        # Update existing profile
                        if db.update_profile_by_email(st.session_state.user_email, {
                            'Name': cp_name,
                            'Gender': cp_gender,
                            'Age': cp_age,
                            'Height': cp_height,
                            'Profession': cp_profession,
                            'Industry': cp_industry,
                            'Education': cp_education,
                            'Religion': cp_religion,
                            'Residency_Status': cp_residency,
                            'Location': cp_location,
                            'LinkedIn': cp_linkedin,
                            'PhotoURL': final_photo_url,
                            'Bio': cp_bio,
                            'Status': 'Single'
                        }):
                            st.success("Profile completed! Welcome to Tingles.")
                            # Force refresh to show completed profile
                            st.session_state.df = db.load_profiles(force_refresh=True)
                            st.rerun()
                        else:
                            st.error("Failed to update profile. Please try again.")
                    else:
                        # Create new profile
                        try:
                            existing_ids = pd.to_numeric(df["ID"], errors="coerce").dropna()
                            next_id = int(existing_ids.max()) + 1 if len(existing_ids) > 0 else 1
                        except Exception:
                            next_id = len(df) + 1

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
                            "Status": "Single"
                        }

                        if db.add_profile(new_profile):
                            st.success("Profile created! Welcome to Tingles.")
                            # Force refresh to bypass cache
                            st.session_state.df = db.load_profiles(force_refresh=True)
                            st.rerun()
                        else:
                            st.error("Failed to create profile. Please try again.")

    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()  # Stop here - don't show rest of app until profile is complete

# Top navigation bar (replaces sidebar)
greeting_name = user_profile.get('Name', '').strip() if user_profile else ''
if not greeting_name:
    greeting_name = st.session_state.user_email.split('@')[0]

# Navigation header with glassmorphic style
st.markdown(f"""
<div style='
    background: rgba(255, 255, 255, 0.05);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 20px 30px;
    margin-bottom: 30px;
'>
    <h3 style='margin: 0; color: #FFFFFF;'>Hi, {greeting_name}!</h3>
</div>
""", unsafe_allow_html=True)

# Navigation buttons
nav_col1, nav_col2, nav_col3, nav_col4 = st.columns([2, 2, 2, 1])

with nav_col1:
    if is_founder:
        show_god_mode = st.button("God Mode", use_container_width=True, key="nav_god_mode")
    else:
        show_curated = st.button("Curated For You", use_container_width=True, key="nav_curated")

with nav_col2:
    if is_founder:
        show_all_profiles = st.button("All Profiles", use_container_width=True, key="nav_all_profiles")
    else:
        show_my_profile = st.button("My Profile", use_container_width=True, key="nav_my_profile")

with nav_col4:
    if st.button("Logout", use_container_width=True, key="nav_logout"):
        logout()
        st.rerun()

st.markdown("---")

# Determine which view to show based on button clicks or session state
if 'current_view' not in st.session_state:
    st.session_state.current_view = "God Mode" if is_founder else "Curated For You"

if is_founder:
    if show_god_mode:
        st.session_state.current_view = "God Mode"
    elif show_all_profiles:
        st.session_state.current_view = "All Profiles"
    view = st.session_state.current_view
else:
    if show_curated:
        st.session_state.current_view = "Curated For You"
    elif show_my_profile:
        st.session_state.current_view = "My Profile"
    view = st.session_state.current_view

# Admin authentication (God Mode)

# Load sheet into session state; refresh on each page load to catch external changes from the sheet
# This ensures Express Interest and other updates are always visible when returning to the page
st.session_state.df = db.load_profiles()

# Ensure DataFrame exists
if st.session_state.df is None:
    st.error("Unable to load profile data. Please contact support if this issue persists.")
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
            # Split images using smart split (handles data URIs correctly)
            img_urls = split_image_urls(img_raw)

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
                if db.update_suggestion_status(st.session_state.user_email, profile_email, "Liked"):
                    st.success("Interest recorded! The matchmaker will be in touch.")
                    st.rerun()
                else:
                    st.error("Could not record interest. Please try again.")

        st.markdown("</div>", unsafe_allow_html=True)

    # ============ VIEWS ============
    if view == "Curated For You":
        st.markdown("<h1 style='text-align: center;'>Curated For You</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color:#6b7280;'>Profiles handpicked by your matchmaker.</p>", unsafe_allow_html=True)
        st.markdown("---")

        # Get suggestions for this user
        user_email = st.session_state.user_email
        curated_profiles = db.get_suggestions_for_user(user_email)

        # Filter to only show Pending suggestions
        if curated_profiles is not None and not curated_profiles.empty:
            pending = curated_profiles[
                curated_profiles['SuggestionStatus'].fillna('Pending').astype(str).str.lower() == 'pending'
            ]
        else:
            pending = pd.DataFrame()

        if pending.empty:
            st.markdown("<div style='text-align: center; padding: 40px 20px;'>", unsafe_allow_html=True)
            st.info("No new curated profiles at this time. Your matchmaker will notify you when new matches are available.")
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            cols = st.columns(3)
            for i, (_, row) in enumerate(pending.iterrows()):
                with cols[i % 3]:
                    render_profile_card(row, show_interest_button=True, card_index=i)

    elif view == "My Profile":
        st.markdown("<h1 style='text-align: center;'>My Profile</h1>", unsafe_allow_html=True)

        # Force refresh to get latest data (important after profile creation/edit)
        my_profile = db.get_profile_by_email(st.session_state.user_email, force_refresh=True)

        if my_profile is None:
            # Profile not found - show create profile form
            st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
            st.info("Welcome! Please complete your profile to get started.")
            st.markdown("<p style='color:#a0a0a0;'>Fill in your details below to complete your profile.</p>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            with st.form("create_profile"):
                cp_name = st.text_input("Full Name *", placeholder="Enter your full name")

                col1, col2, col3 = st.columns(3)
                with col1:
                    cp_age = st.text_input("Age", placeholder="e.g., 28")
                with col2:
                    cp_height = st.text_input("Height", placeholder="e.g., 5'10\"")
                with col3:
                    cp_gender = st.radio("Gender", ["Male", "Female", "Other"])

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
                st.markdown("<p style='color:#a0a0a0; font-size:14px;'>Upload up to 3 high-quality photos. Images will be optimized for best quality.</p>", unsafe_allow_html=True)

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
                        final_photo_url = ""
                        if uploaded_files:
                            with st.spinner("Processing images..."):
                                final_photo_url = upload_images_to_base64(uploaded_files)

                        # Validate photo data length (max ~300KB for 3 images)
                        if len(final_photo_url) > 300000:
                            st.error("Photo data is too large (>300KB). Please use fewer or smaller images.")
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
                                "Status": "Single"
                            }

                            if db.add_profile(new_profile):
                                st.success("Profile created successfully!")
                                # Force refresh to bypass cache
                                st.session_state.df = db.load_profiles(force_refresh=True)
                                st.rerun()
                            else:
                                st.error("Failed to create profile. Please try again.")
        else:
            col1, col2 = st.columns([1, 2])
            with col1:
                # Images - support multiple comma-separated URLs
                img_raw = my_profile.get('PhotoURL', '') or my_profile.get('ImageURL', '')
                if img_raw and str(img_raw).strip():
                    # Split images using smart split (handles data URIs correctly)
                    img_urls = split_image_urls(img_raw)

                    # Display images
                    if len(img_urls) == 1:
                        # Single image
                        img_url = resolve_image_url(img_urls[0])
                        if img_url:
                            try:
                                st.image(img_url, width=300)
                            except Exception:
                                st.markdown("<div style='height:300px;background:#2a2a2a;border-radius:12px;display:flex;align-items:center;justify-content:center;color:#666;'>Image unavailable</div>", unsafe_allow_html=True)
                        else:
                            st.markdown("<div style='height:300px;background:#2a2a2a;border-radius:12px;display:flex;align-items:center;justify-content:center;color:#666;'>No photo</div>", unsafe_allow_html=True)
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
                                        st.markdown("<div style='height:300px;background:#2a2a2a;border-radius:12px;display:flex;align-items:center;justify-content:center;color:#666;'>Image unavailable</div>", unsafe_allow_html=True)
                                else:
                                    st.markdown("<div style='height:300px;background:#2a2a2a;border-radius:12px;display:flex;align-items:center;justify-content:center;color:#666;'>Invalid URL</div>", unsafe_allow_html=True)
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
            st.markdown("<h3 style='text-align: center;'>Edit Your Profile</h3>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color:#a0a0a0;'>Update your profile information below.</p>", unsafe_allow_html=True)

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
                st.markdown("<p style='color:#a0a0a0; font-size:14px;'>Upload new photos to replace existing ones. Leave empty to keep current photos.</p>", unsafe_allow_html=True)

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

                new_bio = st.text_area("Bio", value=my_profile.get('Bio', '') or '', height=100)

                if st.form_submit_button("Save Changes", use_container_width=True):
                    # Process uploaded images or keep existing
                    if edit_uploaded_files:
                        with st.spinner("Processing images..."):
                            final_photo_url = upload_images_to_base64(edit_uploaded_files, max_images=3)
                    else:
                        # Keep existing photos if no new uploads
                        final_photo_url = my_profile.get('PhotoURL', '') or my_profile.get('ImageURL', '') or ''

                    # Validate photo data length
                    if len(final_photo_url) > 300000:
                        st.error("❌ Photo data is too large (>300KB). Please use fewer or smaller images.")
                    elif db.update_profile_by_email(st.session_state.user_email, {
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
                        st.session_state.df = db.load_profiles(force_refresh=True)
                        st.rerun()
                    else:
                        st.error("Failed to update profile. Please try again.")

    elif view == "All Profiles":
        # Founder view: see all profiles
        st.markdown("<h1 style='text-align: center;'>All Profiles</h1>", unsafe_allow_html=True)
        avail_set = {"single", "dating"}
        available = df[df["Status"].fillna("").astype(str).str.lower().isin(avail_set)]
        if available.empty:
            st.markdown("<div style='text-align: center; padding: 40px 20px;'>", unsafe_allow_html=True)
            st.info("No single or dating profiles at the moment.")
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            cols = st.columns(3)
            for i, (_, row) in enumerate(available.iterrows()):
                with cols[i % 3]:
                    render_profile_card(row, show_interest_button=False, card_index=i)

    elif view == "God Mode":
        st.markdown("<h2 style='text-align: center;'>God Mode Tools</h2>", unsafe_allow_html=True)
        if not is_founder:
            st.markdown("<div style='text-align: center; padding: 40px 20px;'>", unsafe_allow_html=True)
            st.warning("Founder access required. Please log in with a founder account.")
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            tab1, tab2, tab3, tab4 = st.tabs(["Matchmaker", "Pipeline", "Stage Updater", "Manage Profiles"])

            # ============ MATCHMAKER TOOL ============
            with tab1:
                st.markdown("<h3 style='text-align: center;'>Matchmaker Tool</h3>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center; color:#6b7280;'>Create a new suggestion by selecting a user and a candidate profile.</p>", unsafe_allow_html=True)

                if df.empty or 'Email' not in df.columns:
                    st.markdown("<div style='text-align: center; padding: 40px 20px;'>", unsafe_allow_html=True)
                    st.warning("No profiles with Email column found.")
                    st.markdown("</div>", unsafe_allow_html=True)
                else:
                    all_emails = df['Email'].dropna().tolist()
                    all_emails = [e for e in all_emails if str(e).strip()]

                    if len(all_emails) < 2:
                        st.markdown("<div style='text-align: center; padding: 40px 20px;'>", unsafe_allow_html=True)
                        st.info(f"At least 2 profiles required to create suggestions. Currently: {len(all_emails)} profile(s).")
                        st.markdown("</div>", unsafe_allow_html=True)
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
                            if db.suggestion_exists(selected_user, selected_candidate):
                                st.warning("This suggestion already exists.")
                            else:
                                if db.add_suggestion(selected_user, selected_candidate, "Pending"):
                                    st.success(f"Suggested {selected_candidate} to {selected_user}!")
                                else:
                                    st.error("Failed to add suggestion.")

            # ============ PIPELINE TRACKER ============
            with tab2:
                st.markdown("<h3 style='text-align: center;'>Pipeline Tracker</h3>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center; color:#6b7280;'>View all 'Liked' suggestions - users who expressed interest.</p>", unsafe_allow_html=True)

                suggestions_df = db.load_suggestions()
                if suggestions_df is None or suggestions_df.empty:
                    st.markdown("<div style='text-align: center; padding: 40px 20px;'>", unsafe_allow_html=True)
                    st.info("No suggestions yet.")
                    st.markdown("</div>", unsafe_allow_html=True)
                else:
                    liked = suggestions_df[suggestions_df['Status'].fillna('').astype(str).str.lower() == 'liked']

                    if liked.empty:
                        st.markdown("<div style='text-align: center; padding: 40px 20px;'>", unsafe_allow_html=True)
                        st.info("No matches awaiting introduction yet.")
                        st.markdown("</div>", unsafe_allow_html=True)
                    else:
                        display_data = []
                        for _, row in liked.iterrows():
                            user_profile = db.get_profile_by_email(row['Suggested_To_Email'])
                            candidate_profile = db.get_profile_by_email(row['Profile_Of_Email'])
                            display_data.append({
                                'User': user_profile.get('Name', row['Suggested_To_Email']) if user_profile else row['Suggested_To_Email'],
                                'User Email': row['Suggested_To_Email'],
                                'Interested In': candidate_profile.get('Name', row['Profile_Of_Email']) if candidate_profile else row['Profile_Of_Email'],
                                'Candidate Email': row['Profile_Of_Email'],
                                'Status': row['Status']
                            })

                        st.dataframe(pd.DataFrame(display_data))

                        st.markdown("---")
                        st.markdown("<p style='text-align: center; color:#6b7280;'>Next step: Contact both parties via WhatsApp to arrange an introduction.</p>", unsafe_allow_html=True)

            # ============ STAGE UPDATER ============
            with tab3:
                st.markdown("<h3 style='text-align: center;'>Stage Updater</h3>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center; color:#6b7280;'>Move matches through relationship stages.</p>", unsafe_allow_html=True)

                suggestions_df = db.load_suggestions()
                if suggestions_df is None or suggestions_df.empty:
                    st.markdown("<div style='text-align: center; padding: 40px 20px;'>", unsafe_allow_html=True)
                    st.info("No suggestions to update.")
                    st.markdown("</div>", unsafe_allow_html=True)
                else:
                    active = suggestions_df[suggestions_df['Status'].fillna('').astype(str).str.lower().isin(['liked', 'match', 'date', 'married'])]

                    if active.empty:
                        st.markdown("<div style='text-align: center; padding: 40px 20px;'>", unsafe_allow_html=True)
                        st.info("No active matches to update.")
                        st.markdown("</div>", unsafe_allow_html=True)
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

                            new_status = st.radio(
                                "Update Status",
                                stages,
                                index=current_idx,
                                horizontal=True,
                                key="new_stage"
                            )

                            if st.button("Save Status", key="save_stage_btn"):
                                if db.update_suggestion_status(row['Suggested_To_Email'], row['Profile_Of_Email'], new_status):
                                    st.success(f"Updated to {new_status}!")
                                    st.rerun()
                                else:
                                    st.error("Failed to update status.")

            # ============ MANAGE PROFILES ============
            with tab4:
                st.markdown("<h3 style='text-align: center;'>Manage Profiles</h3>", unsafe_allow_html=True)

                # Add New Profile
                st.markdown("<h4 style='text-align: center;'>Add New Profile</h4>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center; color:#a0a0a0; font-size:14px;'>This will create both a profile AND login credentials for the user.</p>", unsafe_allow_html=True)

                with st.form("new_profile_form"):
                    st.markdown("#### Login Credentials")
                    n_email = st.text_input("Email (for login) *", placeholder="e.g., john.doe@example.com")
                    n_password = st.text_input("Temporary Password *", type="password", placeholder="e.g., TempPass123")
                    n_role = "user"  # Founders only add regular users

                    st.markdown("#### Profile Information")
                    n_name = st.text_input("Name")
                    n_gender = st.radio("Gender", ["Male", "Female", "Other"], horizontal=True, key="new_gender")

                    col1, col2 = st.columns(2)
                    with col1:
                        n_age = st.text_input("Age", placeholder="e.g., 28")
                    with col2:
                        n_height = st.text_input("Height", placeholder="e.g., 5'9\"")

                    col4, col5 = st.columns(2)
                    with col4:
                        n_profession = st.text_input("Profession", placeholder="e.g., Software Engineer")
                    with col5:
                        n_industry = st.text_input("Industry", placeholder="e.g., Technology")

                    col4b, col5b = st.columns(2)
                    with col4b:
                        n_education = st.text_input("Education", placeholder="e.g., MBA from IIM")
                    with col5b:
                        n_religion = st.text_input("Religion", placeholder="e.g., Hindu, Muslim, Christian")

                    col6, col7 = st.columns(2)
                    with col6:
                        n_residency = st.text_input("Residency Status", placeholder="e.g., Citizen, PR, Work Visa")
                    with col7:
                        n_location = st.text_input("Location", placeholder="e.g., Mumbai, India")

                    n_linkedin = st.text_input("LinkedIn URL")
                    n_whatsapp = st.text_input("WhatsApp Number")
                    n_bio = st.text_area("Bio", height=80)

                    st.markdown("#### Photos (up to 3)")
                    n_uploaded_files = st.file_uploader(
                        "Choose images",
                        type=["jpg", "jpeg", "png", "webp"],
                        accept_multiple_files=True,
                        key="godmode_profile_images",
                        label_visibility="collapsed"
                    )

                    st.markdown("<p style='color:#a0a0a0; font-size:13px; margin-top:10px;'>Relationship Status: Single = actively looking, Dating = in a relationship, Married = success story</p>", unsafe_allow_html=True)
                    n_status = st.radio("Status", ["Single", "Dating", "Married"], index=0, horizontal=True, key="new_status")

                    submitted = st.form_submit_button("Add Profile & Credentials")
                    if submitted:
                        if not n_email or not n_password:
                            st.error("Email and Password are required.")
                        else:
                            # Process uploaded images
                            n_photo = ""
                            if n_uploaded_files:
                                with st.spinner("Processing images..."):
                                    n_photo = upload_images_to_base64(n_uploaded_files, max_images=3)

                            # First, create the credential
                            cred_success, cred_error = db.add_credential(n_email, n_password, n_role)
                            if not cred_success:
                                st.error(f"Failed to create credentials: {cred_error}")
                            else:
                                # Then create the profile
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
                                    "Age": n_age,
                                    "Height": n_height,
                                    "Profession": n_profession,
                                    "Industry": n_industry,
                                    "Education": n_education,
                                    "Religion": n_religion,
                                    "Residency_Status": n_residency,
                                    "Location": n_location,
                                    "LinkedIn": n_linkedin,
                                    "WhatsApp": n_whatsapp,
                                    "Bio": n_bio,
                                    "PhotoURL": n_photo,
                                    "Status": n_status
                                }
                                if db.add_profile(new_row):
                                    st.success(f"Profile and credentials created.\n\n**Email:** {n_email}\n**Password:** {n_password}\n\nShare these credentials with the user.")
                                    st.session_state.df = db.load_profiles()
                                    st.rerun()
                                else:
                                    st.error("Failed to add profile.")

                st.markdown("---")
                st.markdown("<h4 style='text-align: center;'>All Profiles</h4>", unsafe_allow_html=True)
                st.dataframe(df[['Email', 'Name', 'Gender', 'Industry', 'Status']].head(50))

# Footer note
st.markdown("<div class='footer'>Premium matchmaking — built with care.</div>", unsafe_allow_html=True)
