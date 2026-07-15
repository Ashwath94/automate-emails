import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Bulk Email Sender", layout="wide")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def get_secret(key: str, default: str = "") -> str:
    try:
        if key in st.secrets:
            return st.secrets[key]
    except FileNotFoundError:
        pass
    return os.getenv(key, default)


def check_passcode() -> bool:
    required = get_secret("APP_PASSCODE")
    if not required:
        return True
    if st.session_state.get("authed"):
        return True
    st.title("Bulk Email Sender")
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

st.title("Bulk Email Sender")

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

from_email = st.text_input("From (Gmail address)", value=get_secret("GMAIL_ADDRESS"))
app_password = st.text_input(
    "Gmail App Password",
    value=get_secret("GMAIL_APP_PASSWORD"),
    type="password",
    help="16-character App Password from myaccount.google.com/apppasswords (requires 2FA enabled).",
)

valid_recipients = [e for e in st.session_state.recipients if EMAIL_RE.match(e)]

send_disabled = not (from_email and app_password and valid_recipients and subject and body_template)
if st.button("Send Email", type="primary", disabled=send_disabled):
    progress = st.progress(0, text="Connecting to Gmail...")
    sent, failed = [], []
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(from_email, app_password)
            for i, e in enumerate(valid_recipients):
                name = st.session_state.names.get(e, first_name_from_email(e))
                full_body = f"Hi {name},\n\n{body_template}"
                msg = MIMEMultipart()
                msg["From"] = from_email
                msg["To"] = e
                msg["Subject"] = subject
                msg.attach(MIMEText(full_body, "plain"))
                try:
                    server.sendmail(from_email, e, msg.as_string())
                    sent.append(e)
                except Exception as ex:
                    failed.append((e, str(ex)))
                progress.progress((i + 1) / len(valid_recipients), text=f"Sent to {e}")
    except smtplib.SMTPAuthenticationError:
        st.error(
            "Authentication failed. Make sure 2FA is enabled on the Gmail account "
            "and you're using an App Password, not your regular password."
        )
    except Exception as ex:
        st.error(f"Failed to connect/send: {ex}")
    else:
        if sent:
            st.success(f"Sent successfully to {len(sent)} recipient(s).")
        if failed:
            st.error(f"Failed for {len(failed)} recipient(s):")
            for e, err in failed:
                st.text(f"{e}: {err}")
