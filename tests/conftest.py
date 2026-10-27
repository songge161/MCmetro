from pathlib import Path

import pytest

from minijapan.config import load_config


@pytest.fixture
def sample_path() -> Path:
    return Path(__file__).parents[1] / "data" / "samples" / "tokyo_demo.yaml"


@pytest.fixture
def sample_config(sample_path):
    return load_config(sample_path)
