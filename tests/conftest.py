from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


# Most widget tests only need deterministic layout/rendering, not a native
# Windows top-level surface. Forcing offscreen avoids Windows COM tail noise
# during pytest shutdown while preserving grab()/render()-based assertions.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
