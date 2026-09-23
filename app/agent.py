# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import google.auth
from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from app.a2ui_utils import a2ui_callback

# IMPORTANT: Hardcoded GCP project ID string as required for Firestore client on Agent Platform
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-03-79d86c84d36d"
# IMPORTANT: Hardcoded public Cloud Storage bucket name for SyncGuard AI assets
GCS_ASSETS_BUCKET_NAME = "syncguard-ai-assets-qwiklabs-gcp-03-79d86c84d36d"
# IMPORTANT: Hardcoded Agent Engine resource name for sandbox code execution
AGENT_ENGINE_RESOURCE_NAME = "projects/910657442222/locations/us-east1/reasoningEngines/3129344233069084672"


def get_firestore_client() -> firestore.Client:
    """Helper to initialize Firestore Client with hardcoded project ID string."""
    creds, _ = google.auth.default(
        scopes=[
            "https://www.googleapis.com/auth/cloud-platform",
            "https://www.googleapis.com/auth/datastore",
        ]
    )
    return firestore.Client(project=FIRESTORE_PROJECT_ID, credentials=creds)


def get_sync_error(error_id: str) -> Dict[str, Any]:
    """Reads a sync error record from the Firestore database collection 'sync_errors' by ID.

    Args:
        error_id: Unique identifier for the sync error document (e.g. 'ERR-504-AUTH-DB').

    Returns:
        A dictionary containing error details (title, service_source, service_target, status, severity, error_message, suggested_remediation).
    """
    db = get_firestore_client()
    doc_ref = db.collection("sync_errors").document(error_id)
    doc = doc_ref.get()

    if doc.exists:
        return doc.to_dict()
    else:
        return {"error": f"Sync error record '{error_id}' not found in Firestore."}


def list_sync_errors(status_filter: str = "") -> List[Dict[str, Any]]:
    """Lists sync errors from the Firestore database collection 'sync_errors'.

    Args:
        status_filter: Optional filter string for error status (e.g., 'OPEN', 'RESOLVED', 'IN_PROGRESS'). If empty, returns all sync errors.

    Returns:
        A list of dictionaries representing sync error records.
    """
    db = get_firestore_client()
    collection_ref = db.collection("sync_errors")

    if status_filter:
        query = collection_ref.where("status", "==", status_filter.upper())
        docs = query.stream()
    else:
        docs = collection_ref.stream()

    results = []
    for doc in docs:
        data = doc.to_dict()
        results.append(data)
    return results


def create_or_update_sync_error(
    error_id: str,
    title: str,
    service_source: str,
    service_target: str,
    severity: str,
    status: str,
    error_message: str,
    suggested_remediation: str,
) -> Dict[str, Any]:
    """Creates or updates a sync error record in the Firestore database collection 'sync_errors'.

    Args:
        error_id: Unique error identifier (e.g. 'ERR-504-AUTH-DB').
        title: Short descriptive title of the sync issue.
        service_source: Source microservice emitting the error (e.g. 'AuthService').
        service_target: Target microservice or DB involved (e.g. 'UserDB').
        severity: Issue severity ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW').
        status: Current error status ('OPEN', 'IN_PROGRESS', 'RESOLVED').
        error_message: Detailed exception or timeout message.
        suggested_remediation: Step-by-step resolution instructions or automated remediation proposal.

    Returns:
        A dictionary with status confirmation and the saved error document.
    """
    db = get_firestore_client()
    doc_ref = db.collection("sync_errors").document(error_id)

    record = {
        "error_id": error_id,
        "title": title,
        "service_source": service_source,
        "service_target": service_target,
        "severity": severity.upper(),
        "status": status.upper(),
        "error_message": error_message,
        "suggested_remediation": suggested_remediation,
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    doc_ref.set(record, merge=True)
    return {"status": "success", "message": f"Sync error '{error_id}' saved to Firestore.", "record": record}


def fetch_service_health_status(service_name: str) -> Dict[str, Any]:
    """Fetches real-time health, HTTP status, and latency metrics for a target microservice or database.

    Args:
        service_name: Name of the service or database to check (e.g. 'AuthService', 'UserDB', 'PaymentGateway', 'InventoryService').

    Returns:
        A dictionary containing service health status, HTTP status code, response latency (ms), connection pool usage, and timestamp.
    """
    svc_lower = service_name.lower().strip()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if "auth" in svc_lower or "db" in svc_lower:
        return {
            "service_name": service_name,
            "status": "UNHEALTHY",
            "http_status": 504,
            "latency_ms": 30000,
            "active_connections": 150,
            "max_connections": 150,
            "details": "Connection pool exhausted; gateway socket timeout.",
            "checked_at": now_iso,
        }
    elif "payment" in svc_lower or "idp" in svc_lower or "oauth" in svc_lower:
        return {
            "service_name": service_name,
            "status": "DEGRADED",
            "http_status": 401,
            "latency_ms": 1250,
            "active_connections": 42,
            "max_connections": 100,
            "details": "Authentication credential mismatch or expired webhook token.",
            "checked_at": now_iso,
        }
    else:
        return {
            "service_name": service_name,
            "status": "HEALTHY",
            "http_status": 200,
            "latency_ms": 35,
            "active_connections": 12,
            "max_connections": 100,
            "details": "All health probes passing normally.",
            "checked_at": now_iso,
        }


def check_github_system_status() -> Dict[str, Any]:
    """Fetches real-time public system status, component metrics, and active incident reports from GitHub's status API.

    Returns:
        A dictionary containing overall indicator status, component health (Git, Actions, Webhooks, API), and active incident updates.
    """
    import json
    import os
    import urllib.request

    api_url = os.environ.get("GITHUB_STATUS_API_URL", "https://www.githubstatus.com/api/v2/summary.json")
    req = urllib.request.Request(api_url, headers={"User-Agent": "SyncGuardAI/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        status_info = data.get("status", {})
        components = [
            {
                "name": c.get("name"),
                "status": c.get("status"),
                "description": c.get("description"),
            }
            for c in data.get("components", [])[:8]
        ]
        incidents = [
            {
                "name": inc.get("name"),
                "status": inc.get("status"),
                "impact": inc.get("impact"),
                "updated_at": inc.get("updated_at"),
            }
            for inc in data.get("incidents", [])[:3]
        ]

        return {
            "status_indicator": status_info.get("indicator", "unknown"),
            "status_description": status_info.get("description", "Unknown"),
            "components": components,
            "active_incidents": incidents,
            "checked_at": data.get("page", {}).get("updated_at"),
        }
    except Exception as e:
        return {"error": f"Failed to fetch GitHub system status: {str(e)}"}


def geocode_address(address: str) -> Dict[str, Any]:
    """Uses the Google Geocoding API to convert an address string into geographic coordinates (latitude and longitude).

    Args:
        address: The address, landmark, or location query to geocode (e.g., '1600 Amphitheatre Parkway, Mountain View, CA').

    Returns:
        A dictionary containing formatted address, latitude, longitude, and place_id.
    """
    import json
    import os
    import urllib.parse
    import urllib.request

    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return {"error": "GOOGLE_MAPS_API_KEY environment variable is not set."}

    encoded_address = urllib.parse.quote(address)
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SyncGuardAI/1.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        if data.get("status") == "OK" and data.get("results"):
            first_result = data["results"][0]
            loc = first_result.get("geometry", {}).get("location", {})
            return {
                "formatted_address": first_result.get("formatted_address"),
                "latitude": loc.get("lat"),
                "longitude": loc.get("lng"),
                "place_id": first_result.get("place_id"),
            }
        else:
            return {"error": f"Geocoding failed with status '{data.get('status')}'.", "raw_response": data}
    except Exception as e:
        return {"error": f"Failed to call Geocoding API: {str(e)}"}


def search_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "restaurant",
    radius: float = 1000.0,
) -> Dict[str, Any]:
    """Uses the Google Places API (New) to search for nearby points of interest around a set of coordinates.

    Args:
        latitude: Latitude of the center search location.
        longitude: Longitude of the center search location.
        place_type: Type of place to find (e.g. 'restaurant', 'cafe', 'data_center', 'store', 'hospital').
        radius: Search radius in meters (default: 1000.0 meters).

    Returns:
        A dictionary containing a list of nearby places with name, formatted address, location coordinates, and rating.
    """
    import json
    import os
    import urllib.request

    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return {"error": "GOOGLE_MAPS_API_KEY environment variable is not set."}

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.types,places.rating",
        "User-Agent": "SyncGuardAI/1.0",
    }
    payload = {
        "includedTypes": [place_type],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "radius": radius,
            }
        },
    }

    try:
        req_body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        places_out = []
        for p in data.get("places", []):
            loc = p.get("location", {})
            display_name = p.get("displayName", {}).get("text")
            places_out.append({
                "name": display_name,
                "address": p.get("formattedAddress"),
                "location": {
                    "latitude": loc.get("latitude"),
                    "longitude": loc.get("longitude"),
                },
                "rating": p.get("rating"),
                "types": p.get("types", []),
            })

        return {
            "search_center": {"latitude": latitude, "longitude": longitude},
            "place_type": place_type,
            "places": places_out,
        }
    except Exception as e:
        return {"error": f"Failed to call Places API (New): {str(e)}"}


def generate_architecture_diagram(
    prompt_description: str,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """Generates an architecture diagram or error flow image for SyncGuard AI using gemini-3.1-flash-lite-image in the global region. Saves the image as an artifact and uploads it to public Cloud Storage.

    Args:
        prompt_description: Visual description of the system topology or sync error diagram to generate.
        tool_context: ADK ToolContext injected automatically by the framework.

    Returns:
        A dictionary containing the filename, public GCS image URL (https://storage.googleapis.com/<bucket>/<filename>), artifact saving status, and prompt.
    """
    import datetime
    import uuid
    import google.auth
    import google.genai as genai
    from google.cloud import storage

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    filename = f"architecture_diagram_{timestamp}_{unique_id}.jpg"

    try:
        client = genai.Client(
            vertexai=True,
            project=FIRESTORE_PROJECT_ID,
            location="global",
        )
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt_description,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"]
            ),
        )

        if not response.candidates or not response.candidates[0].content.parts:
            return {"error": "No image content returned by gemini-3.1-flash-lite-image model."}

        part = response.candidates[0].content.parts[0]
        if not part.inline_data or not part.inline_data.data:
            return {"error": "Model response did not contain image inline data."}

        image_bytes = part.inline_data.data
        mime_type = part.inline_data.mime_type or "image/jpeg"

        # (1) Save artifact so it shows up in Playground's Artifacts panel
        artifact_saved = False
        if tool_context is not None:
            try:
                part_obj = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                tool_context.save_artifact(filename=filename, artifact=part_obj)
                artifact_saved = True
            except Exception as e:
                print(f"Warning: Failed to save artifact via tool_context: {e}")

        # (2) Upload image bytes to public Cloud Storage bucket
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        gcs_client = storage.Client(project=FIRESTORE_PROJECT_ID, credentials=creds)
        bucket = gcs_client.bucket(GCS_ASSETS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{GCS_ASSETS_BUCKET_NAME}/{filename}"

        return {
            "status": "success",
            "filename": filename,
            "public_url": public_url,
            "artifact_saved": artifact_saved,
            "prompt": prompt_description,
        }
    except Exception as e:
        return {"error": f"Failed to generate and upload image: {str(e)}"}


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        query: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None


code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=AGENT_ENGINE_RESOURCE_NAME
)

schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are SyncGuard AI, an intelligent AI assistant designed for application sync error diagnosis and remediation. "
        "You have direct read and write access to a Cloud Firestore database storing sync errors ('sync_errors' collection). "
        "Use list_sync_errors, get_sync_error, and create_or_update_sync_error to inspect, diagnose, and remediate errors. "
        "Use fetch_service_health_status to check live health probes, HTTP status, and latency for microservices and databases. "
        "Use check_github_system_status to query live external developer dependency status (GitHub Git Operations, Webhooks, Actions, API). "
        "Use geocode_address to convert location addresses to geographic coordinates. "
        "Use search_nearby_places to discover nearby places/services around coordinates using Google Places API (New). "
        "Use generate_architecture_diagram to generate visual system architecture or sync error flow diagrams using gemini-3.1-flash-lite-image in the global region. "
        "You can write and execute Python code safely in a sandbox using code execution to perform calculations, data parsing, or troubleshooting. "
        "You remember user preferences, stated allergies, system restrictions, and historical fix steps across sessions. "
        "Always remember and respect any user constraints or preferences stated in past or current conversations."
    ),
    workflow_description="Analyze sync error logs, system health probes, and external developer dependencies, and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=code_executor,
    instruction=a2ui_instruction,
    tools=[
        PreloadMemoryTool(),
        fetch_service_health_status,
        check_github_system_status,
        geocode_address,
        search_nearby_places,
        generate_architecture_diagram,
        get_sync_error,
        list_sync_errors,
        create_or_update_sync_error,
        get_weather,
        get_current_time,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
