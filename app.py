import base64
import json
import os
import re
from email.mime.text import MIMEText

import streamlit as st
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
LOCAL_ACCOUNTS_FILE = "accounts.local.json"

st.set_page_config(page_title="Email Sender", layout="wide")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def get_secret(key: str, default: str = "") -> str:
    try:
        if key in st.secrets:
            return st.secrets[key]
    except FileNotFoundError:
        pass
    return os.getenv(key, default)


def get_gmail_accounts() -> list[dict]:
    try:
        if "gmail_accounts" in st.secrets:
            return [dict(a) for a in st.secrets["gmail_accounts"]]
    except FileNotFoundError:
        pass
    if os.path.exists(LOCAL_ACCOUNTS_FILE):
        with open(LOCAL_ACCOUNTS_FILE) as f:
            return json.load(f)
    return []


def send_via_gmail_api(account: dict, to_addr: str, subject: str, body: str) -> None:
    creds = Credentials(
        None,
        refresh_token=account["refresh_token"],
        client_id=account["client_id"],
        client_secret=account["client_secret"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=[GMAIL_SEND_SCOPE],
    )
    creds.refresh(Request())
    service = build("gmail", "v1", credentials=creds)

    msg = MIMEText(body)
    msg["To"] = to_addr
    msg["From"] = account["email"]
    msg["Subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


def check_passcode() -> bool:
    required = get_secret("APP_PASSCODE")
    if not required:
        return True
    if st.session_state.get("authed"):
        return True
    st.title("Email Sender")
    code = st.text_input("Enter passcode", type="password")
    if st.button("Unlock"):
        if code == required:
            st.session_state.authed = True
            st.rerun()
        else:
            st.error("Incorrect passcode.")
    return False


if not check_passcode():
    st.stop()


def first_name_from_email(email: str) -> str:
    local = email.split("@")[0]
    local = re.split(r"[._+\-0-9]", local)[0]
    return local.capitalize() if local else email


def parse_emails(raw: str) -> list[str]:
    parts = [p.strip() for p in raw.replace("\n", ",").split(",")]
    return [p for p in parts if p]


if "recipients" not in st.session_state:
    st.session_state.recipients = []
if "names" not in st.session_state:
    st.session_state.names = {}

st.title("Email Sender")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Email content")
    subject = st.text_input("Subject")
    body_template = st.text_area(
        "Body (use {name} for the recipient's first name; 'Hi {name},' is prepended automatically)",
        height=250,
        placeholder="Hope you're doing well...\n\nBest,\nAshwath",
    )

with col2:
    st.subheader("2. Recipients")
    raw_input = st.text_area(
        "Paste comma-separated emails",
        height=100,
        placeholder="john.doe@example.com, jane@company.com",
    )

    add_col, clear_col = st.columns([1, 1])
    if add_col.button("Add recipients", use_container_width=True):
        new_emails = parse_emails(raw_input)
        existing = set(st.session_state.recipients)
        for e in new_emails:
            if e not in existing:
                st.session_state.recipients.append(e)
                st.session_state.names[e] = first_name_from_email(e)
                existing.add(e)
    if clear_col.button("Clear all", use_container_width=True):
        st.session_state.recipients = []
        st.session_state.names = {}

    if st.session_state.recipients:
        st.markdown("**Recipients (click x to remove):**")
        pill_css = """
        <style>
        .pill-container { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
        .pill {
            display: inline-flex; align-items: center; gap: 6px;
            background: #eef2ff; border: 1px solid #c7d2fe; border-radius: 999px;
            padding: 4px 10px; font-size: 0.85rem; color: #1e1b4b !important;
        }
        .pill.invalid { background: #fee2e2; border-color: #fca5a5; color: #7f1d1d !important; }
        </style>
        """
        st.markdown(pill_css, unsafe_allow_html=True)

        pills_html = '<div class="pill-container">'
        for e in st.session_state.recipients:
            valid = bool(EMAIL_RE.match(e))
            cls = "pill" if valid else "pill invalid"
            pills_html += f'<span class="{cls}">{e}</span>'
        pills_html += "</div>"
        st.markdown(pills_html, unsafe_allow_html=True)

        remove_target = st.selectbox(
            "Remove a recipient", ["-- select --"] + st.session_state.recipients
        )
        if remove_target != "-- select --":
            if st.button(f"Remove {remove_target}"):
                st.session_state.recipients.remove(remove_target)
                st.session_state.names.pop(remove_target, None)
                st.rerun()

        invalid = [e for e in st.session_state.recipients if not EMAIL_RE.match(e)]
        if invalid:
            st.error(f"{len(invalid)} invalid email(s): {', '.join(invalid)}")

        st.markdown("**Edit the name used in each greeting:**")
        with st.container(height=250):
            header_l, header_r = st.columns([1, 1])
            header_l.markdown("*Email*")
            header_r.markdown("*Name*")
            for e in st.session_state.recipients:
                name_col_l, name_col_r = st.columns([1, 1])
                name_col_l.text(e)
                st.session_state.names[e] = name_col_r.text_input(
                    "Name",
                    value=st.session_state.names.get(e, first_name_from_email(e)),
                    key=f"name_{e}",
                    label_visibility="collapsed",
                )
    else:
        st.info("No recipients added yet.")

st.divider()
st.subheader(f"3. Preview ({len(st.session_state.recipients)} emails)")

if st.session_state.recipients and body_template:
    with st.container(height=350):
        for e in st.session_state.recipients:
            valid = bool(EMAIL_RE.match(e))
            name = st.session_state.names.get(e, first_name_from_email(e))
            full_body = f"Hi {name},\n\n{body_template}"
            with st.expander(f"{'✅' if valid else '⚠️ invalid'}  {e}", expanded=False):
                st.text(f"Subject: {subject}")
                st.text(full_body)
else:
    st.info("Add recipients and body content to see previews.")

st.divider()
st.subheader("4. Send")

accounts = get_gmail_accounts()

if not accounts:
    st.warning(
        "No Gmail accounts configured. Add one or more entries under "
        "`gmail_accounts` in secrets (see .streamlit/secrets.toml.example)."
    )
else:
    account_emails = [a["email"] for a in accounts]
    selected_email = st.selectbox("Send from", account_emails)
    selected_account = next(a for a in accounts if a["email"] == selected_email)

    valid_recipients = [e for e in st.session_state.recipients if EMAIL_RE.match(e)]

    send_disabled = not (valid_recipients and subject and body_template)
    if st.button("Send Email", type="primary", disabled=send_disabled):
        progress = st.progress(0, text="Sending...")
        sent, failed = [], []
        for i, e in enumerate(valid_recipients):
            name = st.session_state.names.get(e, first_name_from_email(e))
            full_body = f"Hi {name},\n\n{body_template}"
            try:
                send_via_gmail_api(selected_account, e, subject, full_body)
                sent.append(e)
            except HttpError as ex:
                failed.append((e, str(ex)))
            except Exception as ex:
                failed.append((e, str(ex)))
            progress.progress((i + 1) / len(valid_recipients), text=f"Sent to {e}")

        if sent:
            st.success(f"Sent successfully to {len(sent)} recipient(s) from {selected_email}.")
        if failed:
            st.error(f"Failed for {len(failed)} recipient(s):")
            for e, err in failed:
                st.text(f"{e}: {err}")
