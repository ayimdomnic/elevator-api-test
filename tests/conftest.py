import warnings
import pytest

def pytest_configure():
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=pytest.PytestUnknownMarkWarning)