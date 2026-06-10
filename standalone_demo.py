"""
SecureNet SOC — Standalone Demo Gateway

A self-contained version of the API Gateway that includes ALL backend
logic (extractor, ML engine, LLM analyzer, firewall) in a single process.
Uses in-memory data structures instead of Redis/PostgreSQL.

This is perfect for demos and testing on Windows without Docker/Redis/PostgreSQL.

Run:  .venv\\Scripts\\python standalone_demo.py
Open: http://localhost:8000
"""

import os
import sys
import time
import json
import random
import asyncio
import hashlib
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from collections import deque
from typing import Optional

import uvicorn
import numpy as np
import pandas as pd
import joblib
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ml_engine.feature_engineering import FEATURE_COLUMNS, extractor_to_model_features

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-15s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("standalone")

SERVICE_START_TIME = time.time()
MODEL_PATH = os.path.join(os.path.dirname(__file__), "ml_engine", "models", "model.joblib")
METADATA_PATH = os.path.join(os.path.dirname(__file__), "ml_engine", "models", "model_metadata.json")

# ===================================================================
# In-Memory State (replaces Redis + PostgreSQL)
# ===================================================================

class InMemoryState:
    """Replaces Redis and PostgreSQL for standalone demo mode."""

    def __init__(self):
        self.blocked_ips: set = set()
        self.recent_alerts: deque = deque(maxlen=100)
        self.live_metrics: dict = {
            "packets_per_sec": 0,
            "bytes_per_sec": 0,
            "active_connections": 0,
        }
        self.connection_stats: dict = {}  # ip -> list of (timestamp, size)
        self.alert_cooldowns: dict = {}  # ip -> last_alert_time
        self.total_packets_processed: int = 0
        self.total_predictions: int = 0
        self.malicious_count: int = 0

    def add_packet(self, src_ip: str, size: int):
        """Record a packet for feature computation."""
        now = time.time()
        if src_ip not in self.connection_stats:
            self.connection_stats[src_ip] = []
        self.connection_stats[src_ip].append((now, size))
        # Keep only last 60 seconds
        cutoff = now - 60
        self.connection_stats[src_ip] = [
            (t, s) for t, s in self.connection_stats[src_ip] if t > cutoff
        ]
        self.total_packets_processed += 1

    def get_features(self, src_ip: str, window_seconds: int = 30) -> dict:
        """Compute traffic features for an IP."""
        now = time.time()
        cutoff = now - window_seconds
        entries = [
            (t, s) for t, s in self.connection_stats.get(src_ip, []) if t > cutoff
        ]

        if not entries:
            return {
                "packet_count": 0, "total_bytes": 0,
                "packets_per_sec": 0.0, "bytes_per_sec": 0.0,
                "avg_packet_size": 0.0, "flow_duration": 0.0,
                "fwd_pkt_len_mean": 0.0, "fwd_pkt_len_std": 0.0,
                "bwd_pkt_len_mean": 0.0, "flow_iat_mean": 0.0,
                "flow_iat_std": 0.0, "small_packet_ratio": 0.0,
            }

        timestamps = [t for t, _ in entries]
        sizes = [s for _, s in entries]
        packet_count = len(sizes)
        total_bytes = sum(sizes)
        avg_size = total_bytes / packet_count

        # Inter-arrival times
        iats = []
        if len(timestamps) > 1:
            sorted_ts = sorted(timestamps)
            iats = [sorted_ts[i+1] - sorted_ts[i] for i in range(len(sorted_ts) - 1)]

        iat_mean = sum(iats) / len(iats) if iats else 0.0
        iat_std = (sum((x - iat_mean)**2 for x in iats) / len(iats))**0.5 if iats else 0.0
        size_std = (sum((s - avg_size)**2 for s in sizes) / len(sizes))**0.5
        flow_duration = (max(timestamps) - min(timestamps)) if len(timestamps) > 1 else 0.0
        small_count = sum(1 for s in sizes if s < 100)
        small_ratio = small_count / packet_count

        return {
            "packet_count": packet_count,
            "total_bytes": total_bytes,
            "packets_per_sec": round(packet_count / window_seconds, 2),
            "bytes_per_sec": round(total_bytes / window_seconds, 2),
            "avg_packet_size": round(avg_size, 2),
            "flow_duration": round(flow_duration, 4),
            "fwd_pkt_len_mean": round(avg_size, 2),
            "fwd_pkt_len_std": round(size_std, 2),
            "bwd_pkt_len_mean": 0.0,
            "flow_iat_mean": round(iat_mean, 6),
            "flow_iat_std": round(iat_std, 6),
            "small_packet_ratio": round(small_ratio, 4),
        }

    def should_alert(self, ip: str, cooldown: int = 60) -> bool:
        now = time.time()
        last = self.alert_cooldowns.get(ip, 0)
        if now - last > cooldown:
            self.alert_cooldowns[ip] = now
            return True
        return False

    def update_live_metrics(self):
        """Recompute live metrics from active connections."""
        now = time.time()
        total_pps = 0.0
        total_bps = 0.0
        active = 0
        for ip, entries in list(self.connection_stats.items()):
            recent = [(t, s) for t, s in entries if t > now - 30]
            if recent:
                pps = len(recent) / 30.0
                bps = sum(s for _, s in recent) / 30.0
                total_pps += pps
                total_bps += bps
                active += 1
        self.live_metrics = {
            "packets_per_sec": round(total_pps, 2),
            "bytes_per_sec": round(total_bps, 2),
            "active_connections": active,
        }


state = InMemoryState()

# ===================================================================
# Load ML Model
# ===================================================================

model = None
model_metadata = {}
MODEL_VERSION = "unknown"

try:
    if os.path.exists(MODEL_PATH):
        model = joblib.load(MODEL_PATH)
        if os.path.exists(METADATA_PATH):
            with open(METADATA_PATH) as f:
                model_metadata = json.load(f)
            MODEL_VERSION = model_metadata.get("version", "unknown")
        logger.info(f"ML model loaded (v{MODEL_VERSION})")
    else:
        logger.error(f"No model found at {MODEL_PATH}")
        logger.error("Run: .venv\\Scripts\\python ml_engine\\create_demo_model.py")
except Exception as e:
    logger.error(f"Failed to load model: {e}")


# ===================================================================
# Heuristic Fallback (when no LLM key)
# ===================================================================

def heuristic_analysis(features: dict, payload_data: str = None) -> dict:
    """Advanced Mock LLM Threat Classification with MITRE & CVE Mapping."""
    pps = float(features.get("packets_per_sec", 0))
    avg_size = float(features.get("avg_packet_size", 0))

    # Detect Layer 7 Attacks from Payload
    if payload_data:
        payload_data_upper = payload_data.upper()
        if "UNION SELECT" in payload_data_upper or "OR '1'='1" in payload_data_upper:
            return {
                "attack_type": "SQL Injection (SQLi)",
                "severity": "critical",
                "explanation": f"Malicious SQL payload detected in HTTP request: `{payload_data}`. This indicates an active attempt to bypass authentication or extract unauthorized data from the database.",
                "recommendation": "1. Block source IP immediately.\\n2. Validate input sanitization on all endpoints.\\n3. Review database logs for unauthorized queries.",
                "mitre_tactic": "TA0001 - Initial Access",
                "mitre_technique": "T1190 - Exploit Public-Facing Application",
                "cve": "CVE-2023-38408 (Potential)"
            }
        elif "<SCRIPT>" in payload_data_upper or "DOCUMENT.COOKIE" in payload_data_upper:
            return {
                "attack_type": "Cross-Site Scripting (XSS)",
                "severity": "high",
                "explanation": f"Suspicious JavaScript injection payload detected: `{payload_data}`. The attacker is attempting to execute arbitrary code on client browsers to steal session cookies.",
                "recommendation": "1. Implement Content Security Policy (CSP).\\n2. Encode user inputs on the frontend.\\n3. Use HttpOnly flags on session cookies.",
                "mitre_tactic": "TA0001 - Initial Access",
                "mitre_technique": "T1189 - Drive-by Compromise",
                "cve": "CVE-2021-22941 (Potential)"
            }
        elif "C2_BEACON" in payload_data_upper:
            return {
                "attack_type": "Ransomware C2 Beacon",
                "severity": "critical",
                "explanation": f"Outbound traffic matches known Ransomware Command & Control (C2) beaconing signatures: `{payload_data}`. This strongly indicates a compromised internal host.",
                "recommendation": "1. Isolate the affected host from the network immediately.\\n2. Initiate incident response protocol for ransomware.\\n3. Analyze host memory for malicious processes.",
                "mitre_tactic": "TA0011 - Command and Control",
                "mitre_technique": "T1071 - Application Layer Protocol",
                "cve": "Multiple Ransomware Families"
            }

    # Fallback to Layer 4 volumetric heuristics
    if avg_size > 1000 and pps > 30:
        return {
            "attack_type": "DDoS Volumetric Flood",
            "severity": "critical",
            "explanation": f"Extremely high bandwidth detected ({pps:.0f} pkt/s, avg {avg_size:.0f} bytes). Pattern consistent with volumetric DDoS attack aimed at service disruption.",
            "recommendation": "1. Enable strict rate limiting.\\n2. Route traffic through cloud scrubbing center (e.g. Cloudflare).\\n3. Block source subnet if localized.",
            "mitre_tactic": "TA0040 - Impact",
            "mitre_technique": "T1498 - Network Denial of Service",
            "cve": "N/A"
        }
    elif avg_size < 100 and pps > 50:
        return {
            "attack_type": "Port Scan / SYN Flood",
            "severity": "high",
            "explanation": f"High rate of tiny packets ({pps:.0f} pkt/s, avg {avg_size:.0f} bytes). Consistent with TCP SYN scanning for open ports or SYN flood.",
            "recommendation": "1. Block source IP.\\n2. Verify firewall rules drop unsolicited inbound SYN packets.",
            "mitre_tactic": "TA0043 - Reconnaissance",
            "mitre_technique": "T1595 - Active Scanning",
            "cve": "N/A"
        }
    elif 200 < avg_size < 600 and pps > 10:
        return {
            "attack_type": "Brute Force Attack",
            "severity": "medium",
            "explanation": f"Moderate traffic with login-sized packets ({pps:.0f} pkt/s). Likely credential brute force or password spraying attempt.",
            "recommendation": "1. Enforce account lockout policies.\\n2. Implement Multi-Factor Authentication (MFA).\\n3. Block source IP.",
            "mitre_tactic": "TA0006 - Credential Access",
            "mitre_technique": "T1110 - Brute Force",
            "cve": "N/A"
        }
    elif pps > 20:
        return {
            "attack_type": "Anomalous High-Rate Traffic",
            "severity": "high",
            "explanation": f"Unusual traffic rate detected ({pps:.0f} pkt/s). Does not match known benign patterns. Possible zero-day or non-standard attack.",
            "recommendation": "Block source IP and escalate for manual investigation by SOC Level 2 Analyst.",
            "mitre_tactic": "Unknown",
            "mitre_technique": "Unknown",
            "cve": "Unknown"
        }
    else:
        return {
            "attack_type": "Suspicious Traffic Pattern",
            "severity": "medium",
            "explanation": f"Traffic flagged as suspicious by ML model ({pps:.0f} pkt/s, avg {avg_size:.0f} bytes).",
            "recommendation": "Monitor source IP and consider temporary rate limiting.",
            "mitre_tactic": "Unknown",
            "mitre_technique": "Unknown",
            "cve": "Unknown"
        }


# ===================================================================
# Core Pipeline: extract → predict → analyze → block
# ===================================================================

def run_pipeline(src_ip: str, size: int, protocol: str = "TCP", payload_data: str = None) -> Optional[dict]:
    """
    Process a single packet through the full IDS pipeline.
    Returns alert dict if malicious, None if benign.
    """
    if model is None:
        return None

    if src_ip in state.blocked_ips:
        return None

    # 1. Record packet and compute features
    state.add_packet(src_ip, size)
    features = state.get_features(src_ip, window_seconds=30)

    # 2. Run ML prediction
    try:
        features_df = extractor_to_model_features(features)
        prediction = model.predict(features_df)[0]

        confidence = 0.0
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(features_df)[0]
            confidence = float(max(proba))

        status = "benign" if prediction == 0 else "malicious"
        state.total_predictions += 1

    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        return None

    # 3. Handle malicious
    if status == "malicious" and state.should_alert(src_ip, cooldown=30):
        state.malicious_count += 1

        # Run threat analysis (Advanced Mock LLM)
        analysis = heuristic_analysis(features, payload_data)

        # Block the IP
        state.blocked_ips.add(src_ip)

        # Create alert record
        # Mock Geo-Location
        countries = ["US", "CN", "RU", "BR", "DE", "IN", "GB", "KR"]
        country = random.choice(countries)

        alert = {
            "timestamp": datetime.now().isoformat(),
            "alert_id": hashlib.md5(f"{src_ip}-{time.time()}".encode()).hexdigest()[:12],
            "src_ip": src_ip,
            "country": country,
            "attack_type": analysis["attack_type"],
            "severity": analysis["severity"],
            "explanation": analysis["explanation"],
            "recommendation": analysis["recommendation"],
            "mitre_tactic": analysis.get("mitre_tactic"),
            "mitre_technique": analysis.get("mitre_technique"),
            "cve": analysis.get("cve"),
            "confidence": round(confidence, 4),
            "_source": "AI_ANALYZER_V2",
        }
        state.recent_alerts.appendleft(alert)
        
        # Write to audit log
        try:
            with open("audit_log.json", "a") as f:
                f.write(json.dumps(alert) + "\\n")
        except Exception as e:
            logger.error(f"Audit log failed: {e}")

        logger.warning(
            f"ALERT: {analysis['attack_type']} from {src_ip} "
            f"(severity={analysis['severity']}, confidence={confidence:.2%})"
        )
        return alert

    return None


# ===================================================================
# WebSocket Manager
# ===================================================================

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info(f"Dashboard connected ({len(self.active)} active)")

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)
        logger.info(f"Dashboard disconnected ({len(self.active)} active)")

    async def broadcast(self, message: dict):
        disconnected = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)


ws_manager = ConnectionManager()


# ===================================================================
# Background: push telemetry to dashboards
# ===================================================================

async def telemetry_push_loop():
    """Push live metrics and alerts to all WebSocket clients every second."""
    last_alert_count = 0

    while True:
        try:
            if ws_manager.active:
                state.update_live_metrics()

                # Push metrics
                await ws_manager.broadcast({
                    "type": "metrics",
                    "data": state.live_metrics,
                })

                # Push blocked IPs
                await ws_manager.broadcast({
                    "type": "blocked_ips",
                    "data": list(state.blocked_ips),
                })

                # Push alerts if changed
                current_count = len(state.recent_alerts)
                if current_count != last_alert_count:
                    await ws_manager.broadcast({
                        "type": "alert_list",
                        "data": list(state.recent_alerts),
                    })
                    last_alert_count = current_count

        except Exception as e:
            logger.error(f"Telemetry push error: {e}")

        await asyncio.sleep(1)


# ===================================================================
# FastAPI App
# ===================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    push_task = asyncio.create_task(telemetry_push_loop())
    logger.info("Standalone SOC Gateway started")
    logger.info(f"Dashboard: http://localhost:8000")
    yield
    push_task.cancel()


app = FastAPI(
    title="SecureNet SOC — Standalone Demo",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000", "http://localhost:80", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- WebSocket ---

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Send initial state
        await websocket.send_json({
            "type": "blocked_ips",
            "data": list(state.blocked_ips),
        })
        await websocket.send_json({
            "type": "alert_list",
            "data": list(state.recent_alerts),
        })

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat"})

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)


# --- REST APIs ---

class PacketPayload(BaseModel):
    src_ip: str
    dst_ip: str = "192.168.1.1"
    protocol: str = "TCP"
    size: int = 100
    timestamp: float = 0
    payload_data: Optional[str] = None


@app.post("/extract")
async def extract_packet(payload: PacketPayload):
    """
    Ingest a packet through the full pipeline.
    This is the endpoint the simulator sends to.
    """
    alert = run_pipeline(payload.src_ip, payload.size, payload.protocol, payload.payload_data)
    return {
        "status": "alert" if alert else "processed",
        "alert": alert,
    }


@app.get("/api/alerts")
async def get_alerts(limit: int = Query(default=50, le=200, ge=1)):
    alerts = list(state.recent_alerts)[:limit]
    return {"alerts": alerts, "count": len(alerts)}


@app.get("/api/firewall/status")
async def get_firewall_status():
    blocked = list(state.blocked_ips)
    return {"blocked_ips": blocked, "count": len(blocked)}


@app.delete("/api/firewall/blocklist/{ip}")
async def unblock_ip(ip: str):
    """Remove an IP from the blocklist (manual unblock)."""
    if ip in state.blocked_ips:
        state.blocked_ips.remove(ip)
        return {"status": "success", "message": f"IP {ip} unblocked"}
    return {"status": "not_found", "message": f"IP {ip} is not in the blocklist"}


@app.get("/api/metrics")
async def get_metrics():
    state.update_live_metrics()
    return state.live_metrics


@app.get("/api/logs")
async def get_logs():
    return {"logs": list(state.recent_alerts)}


@app.get("/health")
async def health():
    return {
        "status": "healthy" if model is not None else "degraded",
        "service": "standalone_gateway",
        "uptime_seconds": round(time.time() - SERVICE_START_TIME, 1),
        "model_loaded": model is not None,
        "model_version": MODEL_VERSION,
        "stats": {
            "total_packets": state.total_packets_processed,
            "total_predictions": state.total_predictions,
            "malicious_detected": state.malicious_count,
            "blocked_ips": len(state.blocked_ips),
        },
    }


# --- Individual service health endpoints (for dashboard compatibility) ---

@app.get("/api/services/health")
async def services_health():
    """Aggregated health for all 'virtual' services."""
    uptime = round(time.time() - SERVICE_START_TIME, 1)
    return {
        "services": [
            {"name": "gateway", "status": "healthy", "port": 8000, "uptime": uptime},
            {"name": "extractor", "status": "healthy", "port": 8001, "uptime": uptime},
            {"name": "ml_engine", "status": "healthy" if model else "degraded", "port": 8002, "uptime": uptime},
            {"name": "llm_analyzer", "status": "healthy", "port": 8003, "uptime": uptime},
            {"name": "firewall", "status": "healthy", "port": 8004, "uptime": uptime},
        ]
    }


# ===================================================================
# Entry Point
# ===================================================================

if __name__ == "__main__":
    print()
    print("=" * 60)
    print("  SecureNet SOC — Standalone Demo Mode")
    print("=" * 60)
    print()
    print(f"  ML Model: {'Loaded (v' + MODEL_VERSION + ')' if model else 'NOT FOUND'}")
    print(f"  Mode:     In-memory (no Redis/PostgreSQL needed)")
    print()
    print("  Starting on http://localhost:8000")
    print("  Dashboard will be at http://localhost:5173")
    print()
    print("  To simulate an attack:")
    print("    .venv\\Scripts\\python simulator\\attack.py")
    print()
    print("=" * 60)
    print()

    uvicorn.run(app, host="0.0.0.0", port=8000)
