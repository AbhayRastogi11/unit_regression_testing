import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone, timedelta
import time
import os
import re
import logging
from token_store import get_access_token

# ===================== LOGGING CONFIG =====================


LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.environ.get("PIPELINE_LOG_FILE", "weather_pipeline.log")
 
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)
logger.info("Email_Extraction module imported, logging configured.")

# Pre-compute IST offset for +05:30
IST_OFFSET = timezone(timedelta(hours=5, minutes=30))


# ===================== RANGE CONFIG =====================

EVENT_TIME_BEFORE_MINUTES = int(os.environ.get("EVENT_TIME_BEFORE_MINUTES", "0"))
EVENT_TIME_AFTER_MINUTES  = int(os.environ.get("EVENT_TIME_AFTER_MINUTES", "300"))


# ===================== ENV LOADER =====================

def load_env(env_file=".env"):
    """
    Basic loader that reads KEY=VALUE pairs from .env
    and sets them in os.environ only if they are not already set.
    This avoids overriding environment variables from other systems (like schedulers).
    """
    if not os.path.exists(env_file):
        logger.info(".env file not found at %s, skipping explicit load.", env_file)
        return

    logger.info("Loading environment variables from %s", env_file)
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines or commented lines
                if not line or line.startswith("#"):
                    continue

                # Parse KEY=VALUE
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Allow wrapping value in quotes; remove outer quotes if present
                if ((value.startswith('"') and value.endswith('"')) or
                    (value.startswith("'") and value.endswith("'"))):
                    value = value[1:-1]

                value = value.strip().strip('"\'')
                if key not in os.environ:
                    os.environ[key] = value
                    logger.debug("Loaded env var: %s", key)

    except Exception as e:
        logger.error("Error loading .env file: %s", e)

# Load .env early
load_env()

ENV = os.environ.get("ENV", "").lower()
IS_LOCAL_ENV = (ENV == "local")
logger.info("ENV=%s | IS_LOCAL_ENV=%s", ENV, IS_LOCAL_ENV)

# ===================== CONFIG =====================

USER_EMAIL = os.environ.get("USER_EMAIL")      # mailbox you are operating on

if not USER_EMAIL:
    logger.critical("USER_EMAIL is not set. Please set it in .env or code.")
    raise RuntimeError("USER_EMAIL is not set. Please set it in .env or code.")

logger.info("Configured USER_EMAIL=%s", USER_EMAIL)

def build_headers():
    """For normal Graph GETs (body, messages etc.)"""
    access_token = get_access_token()
    return {
        "Authorization": f"Bearer {access_token}",
        "Prefer": 'outlook.body-content-type="html"'
    }

# Base URL for Microsoft Graph
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

def build_archive_headers():
    """Headers for JSON POST calls (like move → Archive, reply, etc.)"""
    access_token = get_access_token()
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


OUTPUT_DIR = "email_extracts"

# Only create directory upfront if ENV=local (global mode won't save files)
if IS_LOCAL_ENV and not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
    logger.info("Created local output directory: %s", OUTPUT_DIR)


# ===================== UTILS =====================

def sanitize_filename(filename: str) -> str:
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
    logger.debug("Sanitized filename '%s' -> '%s'", filename, safe_name)
    return safe_name

def convert_to_ist_format(utc_datetime_str: str) -> str:
    try:
        utc_dt = datetime.fromisoformat(utc_datetime_str.replace('Z', '+00:00'))
        ist_dt = utc_dt.astimezone(IST_OFFSET)
        formatted = ist_dt.strftime("%Y-%m-%dT%H:%M:%SZ+05:30")
        logger.debug("Converted UTC '%s' -> IST formatted '%s'", utc_datetime_str, formatted)
        return formatted
    except Exception as e:
        logger.error("Failed to convert UTC '%s' to IST: %s", utc_datetime_str, e)
        return utc_datetime_str

def parse_html_value(soup, label):
    """
    Utility to parse <td>Value</td> by label in the HTML table.
    Adjust this as needed based on your actual HTML structure.
    """
    try:
        lbl_td = soup.find("td", string=re.compile(label, re.IGNORECASE))
        if not lbl_td:
            logger.debug("Label '%s' not found in HTML.", label)
            return ""
        # Usually the next 'td' will contain the value
        val_td = lbl_td.find_next("td")
        val_text = (val_td.get_text(strip=True) if val_td else "")
        logger.debug("Parsed label '%s' -> '%s'", label, val_text)
        return val_text
    except Exception as e:
        logger.error("Error parsing label '%s' from HTML: %s", label, e)
        return ""


# ===================== TIME FILTERING =====================

def is_within_time_range(event_time_utc_str: str) -> bool:
    """
    Check if the event_time_utc_str (like "2025-01-10T10:40:00Z")
    is within [now - BEFORE, now + AFTER] in UTC.

    EVENT_TIME_BEFORE_MINUTES and EVENT_TIME_AFTER_MINUTES define the window.
    """
    try:
        now_utc = datetime.now(timezone.utc)
        lower_bound = now_utc - timedelta(minutes=EVENT_TIME_BEFORE_MINUTES)
        upper_bound = now_utc + timedelta(minutes=EVENT_TIME_AFTER_MINUTES)

        event_time = datetime.fromisoformat(event_time_utc_str.replace("Z", "+00:00"))

        within_range = lower_bound <= event_time <= upper_bound
        logger.debug(
            "Event time '%s' | Window: [%s, %s] | within_range=%s",
            event_time_utc_str, lower_bound, upper_bound, within_range
        )
        return within_range
    except Exception as e:
        logger.error("Failed to evaluate time range for '%s': %s", event_time_utc_str, e)
        return False


# ===================== GRAPH HELPERS =====================

def graph_get(url: str) -> dict:
    """Generic helper to GET from Microsoft Graph with the current access token."""
    try:
        logger.debug("GET: %s", url)
        resp = requests.get(url, headers=build_headers())
        if resp.status_code != 200:
            logger.error("GET %s failed with status %d: %s", url, resp.status_code, resp.text)
            return {}
        data = resp.json()
        logger.debug("GET %s succeeded, keys: %s", url, list(data.keys()))
        return data
    except Exception as e:
        logger.error("Exception during GET %s: %s", url, e)
        return {}


def fetch_messages(user_mailbox: str, top: int = 10, subject_filter: str = None):
    """
    Fetch messages for a given user mailbox. Optionally filter by subject.
    """
    # Build the base messages endpoint
    base_url = f"{GRAPH_BASE}/users/{user_mailbox}/mailFolders/Inbox/messages"

    # We want top N messages, and we want the newest first.
    params = [
        "$top=" + str(top),
        "$orderby=receivedDateTime desc"
    ]

    # If you want to filter by subject, Graph filter example:
    # $filter=startswith(subject,'A Sample')
    if subject_filter:
        filter_param = "$filter=" + f"contains(subject,'{subject_filter}')"
        params.append(filter_param)

    query_string = "&".join(params)
    url = f"{base_url}?{query_string}"
    logger.info("Fetching messages from: %s", url)

    try:
        resp = requests.get(url, headers=build_headers())
        if resp.status_code != 200:
            logger.error("Failed to fetch messages: %s", resp.text)
            return []
        messages = resp.json().get("value", [])
        logger.info("Fetched %d messages", len(messages))
        return messages
    except Exception as e:
        logger.error("Exception while fetching messages: %s", e)
        return []


def fetch_next_page(next_link: str):
    """Fetch the next page of messages given a @odata.nextLink."""
    logger.info("Fetching next page: %s", next_link)
    try:
        resp = requests.get(next_link, headers=build_headers())
        if resp.status_code != 200:
            logger.error("Failed to fetch next page: %s", resp.text)
            return []
        data = resp.json()
        messages = data.get("value", [])
        logger.info("Fetched %d messages from next page", len(messages))
        return messages, data.get("@odata.nextLink")
    except Exception as e:
        logger.error("Exception while fetching next page: %s", e)
        return [], None


def get_message_body(user_mailbox: str, message_id: str) -> str:
    """
    Fetch the HTML body for a specific message from Microsoft Graph.
    """
    url = f"{GRAPH_BASE}/users/{user_mailbox}/messages/{message_id}?$select=body"
    try:
        logger.info("Fetching message body for message_id=%s", message_id)
        resp = requests.get(url, headers=build_headers())
        if resp.status_code != 200:
            logger.error(
                "Error fetching body for message %s: status=%d, response=%s",
                message_id, resp.status_code, resp.text
            )
            return ""
        data = resp.json()
        body = data.get("body", {}).get("content", "")
        logger.debug("Fetched body length=%d for message_id=%s", len(body), message_id)
        return body
    except Exception as e:
        logger.error("Exception while fetching message body for %s: %s", message_id, e)
        return ""


def move_message_to_archive(user_mailbox: str, message_id: str) -> bool:
    """
    Example of moving a message to 'Archive' folder.
    Adjust folder name / ID as needed or skip if not required.
    """
    url = f"{GRAPH_BASE}/users/{user_mailbox}/messages/{message_id}/move"
    # This body example moves to a folder named "Archive".
    # Alternatively, you can specify folderId explicitly.
    body = {
        "destinationId": "Archive"
    }
    try:
        logger.info("Moving message %s to Archive...", message_id)
        resp = requests.post(url, headers=build_archive_headers(), json=body)
        if resp.status_code not in (200, 201):
            logger.error(
                "Failed to move message %s to Archive: status=%d, response=%s",
                message_id, resp.status_code, resp.text
            )
            return False
        logger.info("Successfully moved message %s to Archive.", message_id)
        return True
    except Exception as e:
        logger.error("Exception while moving message %s to Archive: %s", message_id, e)
        return False


def send_acknowledgment_email(user_mailbox: str, original_message: dict, reply_body_html: str):
    """
    Optional helper: send some reply/acknowledgement to the sender using Graph.
    """
    try:
        message_id = original_message.get("id")
        if not message_id:
            logger.error("Original message has no 'id'; cannot reply.")
            return False

        url = f"{GRAPH_BASE}/users/{user_mailbox}/messages/{message_id}/reply"
        payload = {
            "message": {
                "body": {
                    "contentType": "HTML",
                    "content": reply_body_html,
                }
            }
        }
        logger.info("Sending acknowledgment reply for message %s", message_id)
        resp = requests.post(url, headers=build_archive_headers(), json=payload)
        if resp.status_code not in (202, 200):
            logger.error(
                "Failed to send reply for message %s: status=%d, response=%s",
                message_id, resp.status_code, resp.text
            )
            return False

        logger.info("Reply sent successfully for message %s", message_id)
        return True
    except Exception as e:
        logger.error("Exception while sending acknowledgment: %s", e)
        return False


def extract_weather_info_from_html(html_content: str) -> dict:
    """
    Parse the HTML content and extract relevant fields.
    Adjust the parsing logic as per actual HTML.
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # Example fields; adapt them to match actual HTML structure:
        flight_number = parse_html_value(soup, "Flight Number")
        departure_airport = parse_html_value(soup, "Departure Airport")
        arrival_airport = parse_html_value(soup, "Arrival Airport")
        departure_time_utc = parse_html_value(soup, "Departure Time (UTC)")
        arrival_time_utc = parse_html_value(soup, "Arrival Time (UTC)")
        route = parse_html_value(soup, "Route")
        aircraft_type = parse_html_value(soup, "Aircraft Type")

        # For demonstration, plus more data as needed
        extracted = {
            "flight_number": flight_number,
            "departure_airport": departure_airport,
            "arrival_airport": arrival_airport,
            "departure_time_utc": departure_time_utc,
            "arrival_time_utc": arrival_time_utc,
            "route": route,
            "aircraft_type": aircraft_type,
        }

        logger.debug("Extracted info from HTML: %s", extracted)
        return extracted
    except Exception as e:
        logger.error("Error parsing HTML content: %s", e)
        return {}


def filter_and_extract_event_data(message: dict) -> dict:
    """
    Given a Graph message object, parse and filter based on an event time in the HTML.
    """
    try:
        message_id = message.get("id")
        if not message_id:
            logger.error("Message has no 'id', skipping.")
            return {}

        subject = message.get("subject", "")
        logger.info("Processing message id=%s subject=%s", message_id, subject)

        body_html = get_message_body(USER_EMAIL, message_id)
        if not body_html:
            return {}

        extracted = extract_weather_info_from_html(body_html)

        # Example that departure_time_utc is the key we check in our time range:
        departure_time_utc = extracted.get("departure_time_utc")
        if departure_time_utc and is_within_time_range(departure_time_utc):
            logger.info(
                "Message %s is within time range (departure_time_utc=%s), including in final data.",
                message_id,
                departure_time_utc,
            )
            extracted["message_id"] = message_id
            extracted["subject"] = subject
            return extracted
        else:
            logger.info(
                "Message %s is out of time range or missing departure_time_utc, skipping.",
                message_id,
            )
            return {}
    except Exception as e:
        logger.error("Error in filter_and_extract_event_data: %s", e)
        return {}


def process_all_messages(user_mailbox: str, top: int = 10, subject_filter: str = None):
    """
    Main function: fetch messages, parse, filter by time window, and return the final structured data.
    """
    logger.info("Starting process_all_messages for mailbox=%s", user_mailbox)
    all_events = []

    messages = fetch_messages(user_mailbox, top=top, subject_filter=subject_filter)
    for msg in messages:
        event = filter_and_extract_event_data(msg)
        if event:
            all_events.append(event)

    logger.info("Total events in window: %d", len(all_events))
    return all_events


def save_events_to_file(events: list, filename: str):
    """
    Save extracted events to a JSON file (only used in local mode).
    """
    try:
        filepath = os.path.join(OUTPUT_DIR, sanitize_filename(filename))
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2, ensure_ascii=False)
        logger.info("Saved %d events to %s", len(events), filepath)
    except Exception as e:
        logger.error("Error saving events to file '%s': %s", filename, e)


def main():
    """
    Entry point when running this file directly.
    Typically in production, you'd call process_all_messages() from another module.
    """
    logger.info("Email_Extraction main started.")
    subject_filter = os.environ.get("SUBJECT_FILTER")
    top = int(os.environ.get("TOP_MESSAGES", "10"))

    events = process_all_messages(USER_EMAIL, top=top, subject_filter=subject_filter)

    if IS_LOCAL_ENV:
        save_events_to_file(events, "events_output.json")
    else:
        logger.info("Global (non-local) mode, not saving events to file.")
        logger.info("Extracted events: %s", json.dumps(events, indent=2, ensure_ascii=False))

    logger.info("Email_Extraction main completed.")


if __name__ == "__main__":
    main()
