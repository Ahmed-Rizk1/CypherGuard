"""
Tests for shared/validators.py — Pydantic model validation.
"""

import pytest
from shared.validators import PacketData, BlockRequest, PredictionFeatures, AlertData


class TestPacketData:
    """Tests for raw packet validation."""

    def test_valid_packet(self):
        p = PacketData(
            timestamp=1700000000.0,
            src_ip="192.168.1.100",
            dst_ip="10.0.0.1",
            protocol="TCP",
            size=1500,
        )
        assert p.src_ip == "192.168.1.100"
        assert p.protocol == "TCP"

    def test_invalid_src_ip(self):
        with pytest.raises(ValueError, match="Invalid IP"):
            PacketData(
                timestamp=1700000000.0,
                src_ip="not-an-ip",
                dst_ip="10.0.0.1",
                protocol="TCP",
                size=100,
            )

    def test_injection_attempt_in_ip(self):
        """Verify that shell injection via IP field is rejected."""
        with pytest.raises(ValueError):
            PacketData(
                timestamp=1700000000.0,
                src_ip="1.2.3.4; rm -rf /",
                dst_ip="10.0.0.1",
                protocol="TCP",
                size=100,
            )

    def test_invalid_protocol(self):
        with pytest.raises(ValueError):
            PacketData(
                timestamp=1700000000.0,
                src_ip="1.2.3.4",
                dst_ip="10.0.0.1",
                protocol="INVALID",
                size=100,
            )

    def test_zero_size_rejected(self):
        with pytest.raises(ValueError):
            PacketData(
                timestamp=1700000000.0,
                src_ip="1.2.3.4",
                dst_ip="10.0.0.1",
                protocol="TCP",
                size=0,
            )

    def test_negative_timestamp_rejected(self):
        with pytest.raises(ValueError):
            PacketData(
                timestamp=-1.0,
                src_ip="1.2.3.4",
                dst_ip="10.0.0.1",
                protocol="TCP",
                size=100,
            )

    def test_oversized_packet_rejected(self):
        with pytest.raises(ValueError):
            PacketData(
                timestamp=1700000000.0,
                src_ip="1.2.3.4",
                dst_ip="10.0.0.1",
                protocol="TCP",
                size=70000,
            )

    def test_ipv6_accepted(self):
        p = PacketData(
            timestamp=1700000000.0,
            src_ip="::1",
            dst_ip="fe80::1",
            protocol="TCP",
            size=100,
        )
        assert p.src_ip == "::1"


class TestBlockRequest:
    """Tests for firewall block request validation."""

    def test_valid_block(self):
        b = BlockRequest(src_ip="203.0.113.50")
        assert b.src_ip == "203.0.113.50"
        assert b.reason == "automated"

    def test_loopback_rejected(self):
        with pytest.raises(ValueError, match="loopback"):
            BlockRequest(src_ip="127.0.0.1")

    def test_link_local_rejected(self):
        with pytest.raises(ValueError, match="link-local"):
            BlockRequest(src_ip="169.254.1.1")

    def test_injection_rejected(self):
        with pytest.raises(ValueError):
            BlockRequest(src_ip="1.2.3.4 & whoami")

    def test_reason_max_length(self):
        # Should work with 500 chars
        b = BlockRequest(src_ip="1.2.3.4", reason="x" * 500)
        assert len(b.reason) == 500

        # Should fail with 501 chars
        with pytest.raises(ValueError):
            BlockRequest(src_ip="1.2.3.4", reason="x" * 501)


class TestAlertData:
    """Tests for alert data validation."""

    def test_valid_alert(self):
        a = AlertData(
            src_ip="10.0.0.5",
            packets_per_sec=5000.0,
            bytes_per_sec=500000.0,
            avg_packet_size=100.0,
            prediction_confidence=0.95,
        )
        assert a.prediction_confidence == 0.95

    def test_confidence_out_of_range(self):
        with pytest.raises(ValueError):
            AlertData(
                src_ip="10.0.0.5",
                packets_per_sec=100.0,
                bytes_per_sec=10000.0,
                prediction_confidence=1.5,
            )

    def test_negative_pps_rejected(self):
        with pytest.raises(ValueError):
            AlertData(
                src_ip="10.0.0.5",
                packets_per_sec=-100.0,
                bytes_per_sec=10000.0,
            )
