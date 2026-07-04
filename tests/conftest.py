import pytest
from ontopilot.runtime import OntologyRuntime


@pytest.fixture
def runtime(tmp_path):
    return OntologyRuntime.from_config("config", str(tmp_path / "test.db"))
