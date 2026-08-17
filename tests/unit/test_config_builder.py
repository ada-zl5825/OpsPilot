import pytest

from opspilot.holmes.config_builder import PINNED_HOLMES_IMAGE, build_holmes_runtime_config
from opspilot.settings import Settings


def test_pinned_image_accepted() -> None:
    config = build_holmes_runtime_config(Settings())
    assert config["image"] == PINNED_HOLMES_IMAGE


def test_unpinned_image_rejected() -> None:
    with pytest.raises(ValueError, match="pinned"):
        build_holmes_runtime_config(Settings(holmes_image="robustadev/holmes:latest"))
