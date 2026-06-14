# CypherGuard Quick Testing Guide

This guide will show you how to run and test the CypherGuard SOC real-time pipeline and verify the live graphs.

## 1. Start the Environment

Make sure all Docker containers are running and healthy. From the `CypherGuard` root directory, run:

```bash
# Start all containers in background
docker compose up -d

# Verify all services are Up (healthy)
docker ps
```

*Note: If you encounter any proxy connection issues (502 Bad Gateway) on the WebSockets, restart the frontend Nginx proxy container:*
```bash
docker compose restart frontend
```

---

## 2. Access the Dashboard

1. Open your browser and navigate to: **`http://localhost`**
2. If prompted, log in with these operator credentials:
   - **Operator ID:** `admin@securenet.local`
   - **Passkey:** `adminpassword123`
3. Click **Initialize Session** and navigate to the **Telemetry** page.

---

## 3. Simulate an Attack and Verify Live Charts

Because live metrics are computed over a sliding time-window, the **Network Packet Velocity** and **Bandwidth Consumption** charts will show `0` under idle conditions. 

To trigger live traffic spikes, run the attack simulator inside the gateway container:

```bash
docker compose exec gateway python simulator/attack.py
```

- When prompted, select **`1`** for **DDoS** (or `2` for **Port Scan**, `3` for **Brute Force**).
- The traffic simulator has been configured to flood the pipeline for **120 seconds** so you have plenty of time to view the dashboard.
- **Verification:** Look at your browser on the **Telemetry** page. You will immediately see:
  - **Active Connections** increase.
  - The **Network Packet Velocity** graph spike (representing packets/sec).
  - The **Bandwidth Consumption** graph spike (representing bytes/sec).
  - Newly generated alerts appear in the **Threat Log** / **Live Alerts** widget.
