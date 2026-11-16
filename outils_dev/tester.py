"""La suite de tests du dépôt : python outils_dev\tester.py [arguments de pytest]. Sans fenêtre visible (conftest). Code de retour = celui de
pytest. Outil de développement : jamais livré."""
import os
import subprocess
import sys
from pathlib import Path

DEPOT = Path(__file__).resolve().parents[1]


def suite(*args: str) -> int:
    return subprocess.run([sys.executable, "-m", "pytest", "-q", *args], cwd=DEPOT, env={**os.environ, "PYTHONIOENCODING": "utf-8"}).returncode


if __name__ == "__main__":
    sys.exit(suite(*sys.argv[1:]))
