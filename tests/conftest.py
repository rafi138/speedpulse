import os

# Must be set before any test imports PySide6: keeps GUI tests headless on CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTEST_QT_API", "pyside6")
