"""Unit tests for native biometric guard and prompt formatting."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from wise_mcp.biometric_guard import (
    BiometricHardwareUnavailable,
    BiometricVerificationDenied,
    clear_biometric_cache,
    format_write_prompt,
    get_biometric_cache_timestamp,
    verify_macos,
    verify_user_presence,
    verify_windows,
)


def test_format_write_prompt() -> None:
    # create_quote
    p1 = format_write_prompt(
        "create_quote",
        {"source_amount": 1000.0, "source_currency": "EUR", "target_currency": "ZAR"},
    )
    assert "1,000.00 EUR -> ZAR" in p1

    p1_target = format_write_prompt(
        "create_quote",
        {"target_amount": 20000.0, "source_currency": "EUR", "target_currency": "ZAR"},
    )
    assert "20,000.00 ZAR from EUR" in p1_target

    # create_recipient
    p2 = format_write_prompt(
        "create_recipient",
        {"account_holder_name": "Apeira (Pty) Ltd", "currency": "ZAR", "type": "south_africa"},
    )
    assert "Apeira (Pty) Ltd" in p2
    assert "ZAR" in p2

    # stage_transfer
    p3 = format_write_prompt(
        "stage_transfer",
        {"quote_uuid": "quote-99", "target_account_id": 5551, "reference": "INV-101"},
    )
    assert "quote-99" in p3
    assert "5551" in p3
    assert "INV-101" in p3

    # cancel_transfer
    p3_cancel = format_write_prompt(
        "cancel_transfer",
        {"transfer_id": 9991},
    )
    assert "CANCELLING Transfer #9991" in p3_cancel

    # fund_transfer
    p4 = format_write_prompt(
        "fund_transfer",
        {"transfer_id": 777, "balance_id": 101},
    )
    assert "Transfer #777" in p4
    assert "balance 101" in p4

    # fallback
    p5 = format_write_prompt("unknown_action", {})
    assert "unknown_action" in p5


def test_verify_macos_swift_success() -> None:
    with patch("shutil.which", return_value="/usr/bin/swift"), patch(
        "subprocess.run"
    ) as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert verify_macos("Approve payment?") is True


def test_verify_macos_swift_denied() -> None:
    with patch("shutil.which", return_value="/usr/bin/swift"), patch(
        "subprocess.run"
    ) as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        with pytest.raises(BiometricVerificationDenied):
            verify_macos("Approve payment?")


def test_verify_macos_fallback_osascript() -> None:
    with patch("shutil.which", return_value="/usr/bin/swift"), patch(
        "subprocess.run"
    ) as mock_run:
        # swift fails policy evaluation (code 2), falls back to osascript dialog (code 0)
        mock_run.side_effect = [
            MagicMock(returncode=2),
            MagicMock(returncode=0),
        ]
        assert verify_macos("Approve payment?") is True


def test_verify_windows_success() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="VerificationSucceeded\n", stderr=""
        )
        assert verify_windows("Approve payment?") is True


def test_verify_windows_denied() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Canceled\n", stderr="")
        with pytest.raises(BiometricVerificationDenied):
            verify_windows("Approve payment?")


def test_verify_user_presence_unsupported_platform() -> None:
    clear_biometric_cache()
    with patch("sys.platform", "linux"):
        with pytest.raises(BiometricHardwareUnavailable):
            verify_user_presence("Test prompt")


def test_verify_user_presence_ttl_caching() -> None:
    clear_biometric_cache()
    assert get_biometric_cache_timestamp() is None

    call_count = 0

    def mock_verify_macos(prompt: str, timeout_seconds: int = 60) -> bool:
        nonlocal call_count
        call_count += 1
        return True

    with patch("sys.platform", "darwin"), patch(
        "wise_mcp.biometric_guard.verify_macos", side_effect=mock_verify_macos
    ):
        # First call with ttl=300 -> prompts OS and populates cache
        res1 = verify_user_presence("Approve #1", ttl_seconds=300)
        assert res1 is True
        assert call_count == 1
        assert get_biometric_cache_timestamp() is not None

        # Second call within TTL -> returns True immediately without OS prompt
        res2 = verify_user_presence("Approve #2", ttl_seconds=300)
        assert res2 is True
        assert call_count == 1  # Unchanged!

        # Third call with ttl=0 -> bypasses cache, prompts OS, and clears cache
        res3 = verify_user_presence("Approve #3 (fund)", ttl_seconds=0)
        assert res3 is True
        assert call_count == 2
        assert get_biometric_cache_timestamp() is None

        # Fourth call after cache cleared -> prompts OS again
        res4 = verify_user_presence("Approve #4", ttl_seconds=300)
        assert res4 is True
        assert call_count == 3
        assert get_biometric_cache_timestamp() is not None

        # Clear cache manually
        clear_biometric_cache()
        assert get_biometric_cache_timestamp() is None
