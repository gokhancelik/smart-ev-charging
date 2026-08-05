"""Unit tests for the binary-sensor platform's state parsing."""

from __future__ import annotations

import pytest

from custom_components.smart_ev_charging.binary_sensor import _parse_on_states


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, []),
        ("", []),
        ("Charging", ["charging"]),
        ("Charging,Completed", ["charging", "completed"]),
        ("Charging, Completed,  Idle", ["charging", "completed", "idle"]),
        (["Charging", "Completed"], ["charging", "completed"]),
        (["Charging"], ["charging"]),
        ("a,b c", ["a", "b c"]),
    ],
)
def test_parse_on_states(raw, expected):
    assert _parse_on_states(raw) == expected
