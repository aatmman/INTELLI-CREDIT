"""
Dependency Check — Run at startup to verify all required packages.

Usage:
    python check_dependencies.py          # Check only
    python check_dependencies.py --install  # Auto-install missing

Called automatically from main.py on startup.
"""

import importlib
import subprocess
import sys
from typing import List, Tuple


# (import_name, pip_package_name, required_for)
REQUIRED_PACKAGES: List[Tuple[str, str, str]] = [
    # Core
    ("fastapi", "fastapi", "API server"),
    ("uvicorn", "uvicorn[standard]", "API server"),
    ("pydantic", "pydantic", "API server"),
    ("pydantic_settings", "pydantic-settings", "Config"),

    # Database
    ("supabase", "supabase", "Database"),
    ("postgrest", "postgrest", "Database"),

    # AI / ML
    ("sklearn", "scikit-learn", "ML scoring"),
    ("xgboost", "xgboost", "ML scoring"),
    ("numpy", "numpy", "ML scoring"),
    ("pandas", "pandas", "ML scoring"),
    ("joblib", "joblib", "ML scoring"),

    # LangGraph + LLM
    ("langgraph", "langgraph", "Agent graph"),
    ("langchain", "langchain", "Agent graph"),
    ("groq", "groq", "LLM service"),

    # Web Research
    ("tavily", "tavily-python", "Research nodes"),

    # Document Parsing
    ("fitz", "PyMuPDF", "Document parsing"),
    ("docling", "docling", "Document parsing (primary)"),
    ("easyocr", "easyocr", "Document parsing (OCR fallback)"),

    # Document Generation
    ("docx", "python-docx", "CAM/Sanction letter"),
    ("reportlab", "reportlab", "PDF generation"),

    # HTTP
    ("httpx", "httpx", "HTTP client"),
    ("aiohttp", "aiohttp", "Async HTTP"),

    # Utilities
    ("dotenv", "python-dotenv", "Environment config"),
    ("orjson", "orjson", "Fast JSON"),
]


def check_dependencies(auto_install: bool = False) -> bool:
    """
    Check all required packages are importable.

    Returns True if all OK, False if any missing.
    If auto_install=True, attempts pip install for missing packages.
    """
    missing: List[Tuple[str, str, str]] = []
    installed: List[str] = []

    for import_name, pip_name, purpose in REQUIRED_PACKAGES:
        try:
            importlib.import_module(import_name)
            installed.append(import_name)
        except ImportError:
            missing.append((import_name, pip_name, purpose))

    if not missing:
        print(f"✓ All {len(installed)} dependencies OK")
        return True

    print(f"\n{'='*60}")
    print(f"  ⚠ MISSING DEPENDENCIES ({len(missing)} package(s))")
    print(f"{'='*60}")
    for import_name, pip_name, purpose in missing:
        print(f"  ✗ {import_name} ({pip_name}) — needed for: {purpose}")

    if auto_install:
        print(f"\n→ Auto-installing {len(missing)} package(s)...")
        pip_packages = [pip_name for _, pip_name, _ in missing]
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install"] + pip_packages,
                stdout=subprocess.DEVNULL,
            )
            print(f"✓ Installed {len(pip_packages)} package(s)")

            # Verify again
            still_missing = []
            for import_name, pip_name, purpose in missing:
                try:
                    importlib.import_module(import_name)
                except ImportError:
                    still_missing.append((import_name, pip_name, purpose))

            if still_missing:
                print(f"\n✗ {len(still_missing)} package(s) STILL missing after install:")
                for import_name, pip_name, purpose in still_missing:
                    print(f"  ✗ {import_name} ({pip_name})")
                return False

            print(f"✓ All dependencies now OK")
            return True
        except subprocess.CalledProcessError as exc:
            print(f"✗ pip install failed: {exc}")
            return False
    else:
        print(f"\nTo install: pip install -r requirements.txt")
        print(f"Or run:     python check_dependencies.py --install")
        return False


if __name__ == "__main__":
    auto = "--install" in sys.argv
    ok = check_dependencies(auto_install=auto)
    sys.exit(0 if ok else 1)
