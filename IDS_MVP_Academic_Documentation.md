# 📄 Academic Project Documentation: SecureNet SOC
**AI-Powered Intrusion Detection System W/ Generative Threat Intelligence**
*Minimum Viable Product (MVP) Evaluation Document*

---

## 1. Executive Summary
**SecureNet SOC** is an advanced, end-to-end network Intrusion Detection System (IDS). Unlike traditional static firewalls, this MVP demonstrates a modern, scalable **Microservices Architecture** that combines three distinct technological pillars:
1. Low-level Network Packet Processing
2. Traditional Machine Learning (Classification)
3. Generative Artificial Intelligence (Automated Threat Intelligence & Explanation)

The objective of this MVP is to prove the viability of a real-time, automated Security Operations Center (SOC) capable of not only detecting anomalies but also explaining them in human-readable terms using LLMs, before automatically mitigating the threat via a simulated firewall.

---

## 2. MVP Objectives
* **Real-time Pipeline Demonstration:** Prove that network traffic can be captured, analyzed, classified, and mitigated with sub-second latency.
* **Microservices Decoupling:** Demonstrate a modern architectural pattern where components run entirely independently, isolated by REST APIs.
* **Stateful Feature Engineering:** Transition raw stateless network packets into stateful behavioral metrics (e.g., packets/sec, bytes/sec) on the fly.
* **AI-Driven Threat Context:** Eliminate "black box" machine learning models by integrating Generative AI to provide clear, actionable insights and categorizations for detected anomalies.
* **Real-time Telemetry Visualization:** Produce a highly responsive frontend for SOC analysts to monitor active network bandwidth and packet velocity.

---

## 3. System Architecture & Components
The application is strictly divided into decoupled microservices. If one service fails, the others remain operational.

### A. The Sniffer (`port: Internal`)
Utilizes Python's `scapy` library to hook into the Network Interface Card (NIC). It captures raw packets, extracting crucial metadata (Source IP, Destination IP, Protocol, Size). 

### B. The Feature Extractor (`port: 8001`)
A `FastAPI` service acting as the stateful accumulator. It tracks active IP connections in-memory and computes rolling averages of network velocity. This transforms static packets into dynamic behavioral features required by the Machine Learning model.

### C. The ML Engine (`port: 8002`)
Houses a `scikit-learn` predictive model. It receives the calculated metrics via an API POST request and performs instantaneous inference to classify the traffic as **Benign** or **Malicious**.

### D. The LLM Analyzer (`port: 8003`)
The primary innovation of this MVP. Upon receiving a "Malicious" alert from the ML Engine, this service leverages **GPT-4o-mini** (via OpenRouter) to evaluate the numeric metrics. It automatically categorizes the attack vector (e.g., *DDoS, Port Scan, Brute Force*), assigns a severity rating, and writes a human-readable threat explanation to a central log file.

### E. The Firewall Controller (`port: 8004`)
The mitigation endpoint. Upon recommendation from the LLM Analyzer, this controller permanently adds the offending IP address to an active blacklist, cutting off future traffic routes.

### F. The SOC Dashboard (Frontend)
A Single Page Application (SPA) built using **React** and **Vite**. It acts as the command center, executing highly efficient polling to the backend APIs to render a live, animated 60-second rolling telemetry chart and a stream of AI threat logs.

---

## 4. End-to-End Data Flow Pipeline
1. **Packet Injection:** Raw traffic hits the network (or is simulated via the `attack.py` stress-tester).
2. **Sniffing:** Packets are captured and forwarded over HTTP to the Extractor.
3. **Engineering:** The Extractor aggregates the size and packet count into temporal rates (`bytes/sec`, `packets/sec`) and triggers a background task to the ML Engine.
4. **Classification:** ML Engine runs inference. If anomaly detected = True, trigger LLM API.
5. **Contextualization:** Generative AI analyzes the traffic footprint and generates a JSON incident report.
6. **Mitigation:** The LLM API forwards a block instruction to the Firewall API.
7. **Visualization:** The React frontend simultaneously queries the Extractor for live traffic rates and the LLM for logs, animating the results on the SOC dashboard.

---

## 5. Technology Stack
* **Languages:** Python 3.11, JavaScript (React)
* **Backend Framework:** FastAPI, Uvicorn, Pydantic
* **Machine Learning:** Scikit-Learn, Pandas
* **Generative AI Integration:** OpenAI SDK, OpenRouter (GPT-4o-mini)
* **Network Processing:** Scapy
* **Frontend Automation:** Vite, Recharts, Axios

---

## 6. Future Work & Scalability Enhancements
While this MVP successfully validates the architectural concept, it can be extended into an enterprise-grade solution through the following planned additions:
* **OS-Level Firewall Integration:** Upgrading the Firewall Controller to directly execute system-level network routing bans (e.g., configuring `iptables` on Linux, or Windows Defender Advanced Firewall rules via `netsh`).
* **Message Brokering:** Replacing direct HTTP REST calls between the microservices with an asynchronous message broker (such as Apache Kafka or RabbitMQ) to handle massive spikes in network traffic logs without dropping packets.
* **Persistent Distributed Storage:** Migrating the Extractor's in-memory active-IP tracking and the Firewall's blacklist to a high-speed, persistent data store like **Redis**.
* **Containerization & Orchestration:** Packaging all 6 microservices into individual Docker containers and managing their deployment, scaling, and up-time via Kubernetes clusters.
* **Deep Packet Inspection (DPI):** Extending the Sniffer phase to analyze payload contents (if unencrypted) alongside behavioral headers to catch advanced persistent threats (APTs).

---

## 7. Conclusion
This MVP successfully validates a highly complex, container-ready Microservices pipeline. By augmenting traditional Machine Learning detection algorithms with Generative AI, this architecture drastically reduces the cognitive load on human cybersecurity analysts, offering an automated, intelligent, and highly responsive Intrusion Detection System ready for academic evaluation and future production scaling.
