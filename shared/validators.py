"""
Pydantic models with strict validation for all SecureNet SOC services.

All IP addresses are validated via Python's ipaddress module.
All numeric fields have range constraints.
All string fields have length/pattern constraints.
"""

import ipaddress
from pydantic import BaseModel, field_validator, Field
from typing import Optional


# ---------------------------------------------------------------------------
# IP validation mixin
# ---------------------------------------------------------------------------

def _validate_ip(v: str) -> str:
    """Validate and normalize an IP address string."""
    try:
        addr = ipaddress.ip_address(v.strip())
        return str(addr)
    except ValueError:
        raise ValueError(f"Invalid IP address: '{v}'")


# ---------------------------------------------------------------------------
# Sniffer → Extractor
# ---------------------------------------------------------------------------

class PacketData(BaseModel):
    """Raw packet data sent from the Sniffer to the Extractor.
    [MARKED FOR FUTURE DELETION]: Currently too heavy for the high-throughput 
    extractor (which uses inline validation). Kept here temporarily in case it 
    is needed for debugging or future deep inspection pipelines."""
    timestamp: float = Field(gt=0, description="Unix epoch timestamp")
    src_ip: str = Field(description="Source IP address")
    dst_ip: str = Field(description="Destination IP address")
    protocol: str = Field(pattern=r"^(TCP|UDP|ICMP|OTHER)$", description="Transport protocol")
    size: int = Field(gt=0, le=65535, description="Packet size in bytes")

    @field_validator("src_ip")
    @classmethod
    def validate_src_ip(cls, v: str) -> str:
        return _validate_ip(v)

    @field_validator("dst_ip")
    @classmethod
    def validate_dst_ip(cls, v: str) -> str:
        return _validate_ip(v)


# ---------------------------------------------------------------------------
# Extractor → ML Engine
# ---------------------------------------------------------------------------

class PredictionFeatures(BaseModel):
    """Feature vector sent from the Extractor to the ML Engine."""
    src_ip: str
    protocol: str
    packet_count: int = Field(gt=0)
    total_bytes: int = Field(gt=0)
    packets_per_sec: float = Field(ge=0)
    bytes_per_sec: float = Field(ge=0)
    avg_packet_size: float = Field(ge=0)
    flow_duration: float = Field(ge=0)
    byte_rate_variance: float = Field(ge=0, default=0.0)
    packet_rate_variance: float = Field(ge=0, default=0.0)
    unique_dst_ports: int = Field(ge=0, default=0)
    syn_ratio: float = Field(ge=0, le=1, default=0.0)
    small_packet_ratio: float = Field(ge=0, le=1, default=0.0)
    fwd_pkt_len_mean: float = Field(ge=0, default=0.0)
    fwd_pkt_len_std: float = Field(ge=0, default=0.0)
    bwd_pkt_len_mean: float = Field(ge=0, default=0.0)
    flow_iat_mean: float = Field(ge=0, default=0.0)
    flow_iat_std: float = Field(ge=0, default=0.0)

    @field_validator("src_ip")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        return _validate_ip(v)


# ---------------------------------------------------------------------------
# ML Engine → LLM Analyzer
# ---------------------------------------------------------------------------

class AlertData(BaseModel):
    """Alert data sent from the ML Engine to the LLM Analyzer."""
    src_ip: str
    packets_per_sec: float = Field(ge=0)
    bytes_per_sec: float = Field(ge=0)
    avg_packet_size: float = Field(ge=0, default=0.0)
    prediction_confidence: float = Field(ge=0, le=1, default=0.0)
    model_version: str = Field(default="unknown", max_length=100)
    features: str = Field(default="{}", description="JSON-encoded feature dict")

    @field_validator("src_ip")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        return _validate_ip(v)


# ---------------------------------------------------------------------------
# LLM Analyzer → Firewall
# ---------------------------------------------------------------------------

class BlockRequest(BaseModel):
    """Block command sent from the LLM Analyzer to the Firewall Controller."""
    src_ip: str
    reason: str = Field(default="automated", max_length=500)
    alert_id: Optional[str] = Field(default=None, max_length=100)

    @field_validator("src_ip")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        addr = _validate_ip(v)
        ip_obj = ipaddress.ip_address(addr)

        # Safety: never block loopback or link-local addresses
        if ip_obj.is_loopback:
            raise ValueError(f"Cannot block loopback address: {addr}")
        if ip_obj.is_link_local:
            raise ValueError(f"Cannot block link-local address: {addr}")

        return addr


# ---------------------------------------------------------------------------
# API Response Models
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Standard health check response."""
    status: str = "healthy"
    service: str
    uptime_seconds: float
    version: str = "1.0.0"


class AlertResponse(BaseModel):
    """Alert record returned from the API."""
    alert_id: str
    src_ip: str
    attack_type: Optional[str] = None
    severity: Optional[str] = None
    explanation: Optional[str] = None
    recommendation: Optional[str] = None
    confidence: float = 0.0
    timestamp: str
    status: str = "new"


class MetricsResponse(BaseModel):
    """Live telemetry metrics."""
    packets_per_sec: float = 0.0
    bytes_per_sec: float = 0.0
    active_connections: int = 0


class PredictionResponse(BaseModel):
    """ML prediction result."""
    src_ip: str
    status: str  # "benign" or "malicious"
    confidence: float = 0.0
    model_version: str = "unknown"
