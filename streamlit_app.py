"""Default entrypoint for Streamlit Community Cloud.

Streamlit Cloud looks for `streamlit_app.py` at the repo root by default. This
thin wrapper runs the real app in `src/medflow/app.py`, so the deployment works
whether or not the "Main file path" was customized.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.medflow.app import main  # noqa: E402

main()
