from __future__ import annotations

from opspilot.remediation.service import ControlPlane

_plane: ControlPlane | None = None


def get_plane() -> ControlPlane:
    global _plane
    if _plane is None:
        _plane = ControlPlane()
    return _plane


def set_plane(plane: ControlPlane | None) -> None:
    global _plane
    _plane = plane
