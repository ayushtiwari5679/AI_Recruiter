import json
import uuid

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def create_interview(candidate_email, start_iso, end_iso, candidate_name="Candidate"):
    with open("token.json", "r") as f:
        token = json.load(f)

    creds = Credentials.from_authorized_user_info(token, SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

        with open("token.json", "w") as f:
            f.write(creds.to_json())

    service = build(
        "calendar",
        "v3",
        credentials=creds,
        cache_discovery=False,
    )

    event = {
        "summary": f"Interview - {candidate_name}",
        "description": "Interview scheduled automatically by myNachiketa Candidate Screening.",
        "start": {"dateTime": start_iso},
        "end": {"dateTime": end_iso},
        "attendees": [{"email": candidate_email}],
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }

    result = (
        service.events()
        .insert(
            calendarId="primary",
            body=event,
            conferenceDataVersion=1,
            sendUpdates="all",
        )
        .execute()
    )

    return {
        "created": True,
        "event_id": result["id"],
        "event_link": result["htmlLink"],
        "meet_link": result.get("hangoutLink"),
        "start": start_iso,
        "end": end_iso,
    }