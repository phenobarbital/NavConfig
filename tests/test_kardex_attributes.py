"""Attribute access preserves values without returning from a finally block."""

from typing import Any

import pytest

from navconfig.kardex import Kardex


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("true", "true"),
        ("42", "42"),
        ("text", "text"),
        (True, True),
        (42, 42),
        ('NAVCONFIG_JSONDATA:{"enabled": true}', {"enabled": True}),
    ],
)
def test_attribute_access_preserves_deserialized_values(
    monkeypatch: pytest.MonkeyPatch, value: Any, expected: Any
) -> None:
    monkeypatch.delenv("NAVCONFIG_ATTRIBUTE_TEST", raising=False)
    config = object.__new__(Kardex)
    config._mapping_ = {"NAVCONFIG_ATTRIBUTE_TEST": value}

    result = config.NAVCONFIG_ATTRIBUTE_TEST

    assert result == expected
    assert type(result) is type(expected)
