import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "mediassist_data"

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = "mediassist_docs"

DENSE_MODEL_NAME = "BAAI/bge-small-en-v1.5"
DENSE_DIM = 384
SPARSE_MODEL_NAME = "Qdrant/bm25"
CHUNK_MAX_TOKENS = 512

# Maps each document collection to its files and permitted roles.
# access_roles is stored as metadata on every chunk and used as the
# Qdrant retrieval filter — the sole enforcement point for RBAC.
COLLECTION_CONFIG: dict = {
    "general": {
        "files": [
            "general/staff_handbook.pdf",
            "general/leave_policy.pdf",
            "general/code_of_conduct.pdf",
            "general/general_faqs.pdf",
        ],
        "access_roles": ["doctor", "nurse", "billing_executive", "technician", "admin"],
    },
    "clinical": {
        "files": [
            "clinical/treatment_protocols.pdf",
            "clinical/drug_formulary.pdf",
            "clinical/diagnostic_reference.pdf",
        ],
        "access_roles": ["doctor", "admin"],
    },
    "nursing": {
        "files": [
            "nursing/icu_nursing_procedures.pdf",
            "nursing/infection_control.pdf",
        ],
        "access_roles": ["nurse", "doctor", "admin"],
    },
    "billing": {
        "files": [
            "billing/billing_codes.pdf",
            "billing/claim_submission_guide.md",
        ],
        "access_roles": ["billing_executive", "admin"],
    },
    "equipment": {
        "files": [
            "equipment/equipment_manual.pdf",
        ],
        "access_roles": ["technician", "admin"],
    },
}
