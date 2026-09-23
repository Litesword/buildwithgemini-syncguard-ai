import datetime
import google.auth
from google.cloud import firestore

# IMPORTANT: Hardcoded GCP Project ID string for Firestore client
PROJECT_ID = "qwiklabs-gcp-03-79d86c84d36d"

def seed_database():
    print(f"Connecting to Firestore for project '{PROJECT_ID}'...")
    creds, _ = google.auth.default(
        scopes=[
            "https://www.googleapis.com/auth/cloud-platform",
            "https://www.googleapis.com/auth/datastore",
        ]
    )
    db = firestore.Client(project=PROJECT_ID, credentials=creds)

    collection_ref = db.collection("sync_errors")

    seeded_errors = [
        {
            "error_id": "ERR-504-AUTH-DB",
            "title": "504 Gateway Timeout between Auth Service and User DB",
            "service_source": "AuthService",
            "service_target": "UserDB",
            "severity": "CRITICAL",
            "status": "OPEN",
            "error_message": "Connection pool exhausted after 30000ms waiting for available socket during peak authentication surge.",
            "suggested_remediation": "1. Scale user-db connection pool max_connections from 50 to 150.\n2. Flush stale idle connection sockets in Auth Service.\n3. Verify database read-replica lag.",
            "created_at": "2026-09-23T10:00:00Z",
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        {
            "error_id": "ERR-401-OAUTH-TOKEN",
            "title": "401 Unauthorized - OAuth Token Exchange Failure",
            "service_source": "PaymentGateway",
            "service_target": "IdentityProvider",
            "severity": "HIGH",
            "status": "OPEN",
            "error_message": "Token signing key mismatch or expired client credentials during external webhook sync.",
            "suggested_remediation": "1. Rotate OAuth client secret in Secret Manager.\n2. Re-sync key vault cached signing keys.\n3. Restart PaymentGateway pod replicas.",
            "created_at": "2026-09-23T08:15:00Z",
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        {
            "error_id": "ERR-409-RACE-COND",
            "title": "409 Conflict - Concurrent Inventory Sync Deadlock",
            "service_source": "OrderProcessor",
            "service_target": "InventoryService",
            "severity": "MEDIUM",
            "status": "RESOLVED",
            "error_message": "Row lock timeout occurred when updating SKU-9921 inventory stock concurrently across multi-region nodes.",
            "suggested_remediation": "1. Enabled optimistic locking with retry backoff.\n2. Partitioned inventory updates by region bucket.",
            "created_at": "2026-09-22T14:20:00Z",
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
    ]

    for error_data in seeded_errors:
        doc_ref = collection_ref.document(error_data["error_id"])
        doc_ref.set(error_data)
        print(f"Seeded error item: {error_data['error_id']} -> {error_data['title']}")

    print("Firestore database seeding completed successfully!")

if __name__ == "__main__":
    seed_database()
