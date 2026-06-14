import time
import requests
import threading
import random
import sys
import redis
import json
import os
import uuid
import asyncio
from dotenv import load_dotenv

load_dotenv()

MODE = os.getenv("MODE", "redis").lower()  # options: "redis", "http"
LOAD_TEST_MODE = os.getenv("LOAD_TEST_MODE", "false").lower() == "true"
MAX_QPS = int(os.getenv("MAX_QPS", "5000"))
TENANT_ID = os.getenv("TENANT_ID", "00000000-0000-0000-0000-000000000001")

def get_redis_client():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return redis.Redis.from_url(redis_url, decode_responses=True)

def worker_http(target_url, payload, duration, delay=0.0):
    """
    Worker thread to send packets via HTTP (Legacy).
    """
    end_time = time.time() + duration
    while time.time() < end_time:
        try:
            payload["timestamp"] = str(time.time())
            requests.post(target_url, json=payload, timeout=0.5)
        except requests.exceptions.RequestException:
            pass
        if delay > 0:
            time.sleep(delay)

def worker_redis(redis_client, stream_name, payload, duration, delay=0.0):
    """
    Worker thread to publish packets directly to Redis.
    """
    end_time = time.time() + duration
    while time.time() < end_time:
        try:
            payload["timestamp"] = str(time.time())
            payload["trace_id"] = str(uuid.uuid4())
            # Convert values to strings as required by Redis Streams
            str_payload = {k: str(v) for k, v in payload.items()}
            redis_client.xadd(stream_name, str_payload)
        except redis.RedisError:
            pass
        if delay > 0:
            time.sleep(delay)

async def async_load_worker(redis_client, stream_name, payload, qps_per_worker, duration):
    """Async worker for load testing with precise QPS limiting."""
    end_time = time.time() + duration
    delay = 1.0 / qps_per_worker if qps_per_worker > 0 else 0
    
    while time.time() < end_time:
        try:
            payload["timestamp"] = str(time.time())
            payload["trace_id"] = str(uuid.uuid4())
            str_payload = {k: str(v) for k, v in payload.items()}
            redis_client.xadd(stream_name, str_payload)
        except redis.RedisError:
            pass
        await asyncio.sleep(delay)

async def run_load_test(attack_type, random_ip):
    print(f"\n[Simulator] 🚀 LOAD TEST MODE ACTIVE 🚀")
    print(f"[Simulator] Target QPS: {MAX_QPS}")
    
    import redis.asyncio as aioredis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_client = aioredis.from_url(redis_url, decode_responses=True)
    
    target = "stream:raw_packets"
    num_workers = 100
    qps_per_worker = MAX_QPS / num_workers
    duration = 20 # fixed 20s for load test
    
    payload = {"timestamp": "0", "src_ip": random_ip, "dst_ip": "192.168.1.1", "protocol": "TCP", "size": "1000", "trace_id": "", "tenant_id": TENANT_ID}
    
    print(f"[Simulator] Spawning {num_workers} async workers...")
    tasks = [
        async_load_worker(redis_client, target, dict(payload), qps_per_worker, duration)
        for _ in range(num_workers)
    ]
    
    await asyncio.gather(*tasks)
    await redis_client.close()
    print("[Simulator] Load test complete.")

def simulate_attack(attack_type):
    print(f"\n[Simulator] Launching {attack_type.upper()} attack (MODE: {MODE})...")
    
    redis_client = None
    if MODE == "redis":
        redis_client = get_redis_client()
        target = "stream:raw_packets"
        worker_func = worker_redis
        args_prefix = (redis_client, target)
    else:
        target = "http://localhost:8000/extract" 
        worker_func = worker_http
        args_prefix = (target,)
    
    # Generate a random mock IP address for the attacker
    random_ip = f"{random.randint(11, 200)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
    print(f"[Simulator] Assigned Attacker IP: {random_ip}")
    
    if LOAD_TEST_MODE:
        asyncio.run(run_load_test(attack_type, random_ip))
        return
    
    threads = []
    
    if attack_type == "ddos":
        # DDoS Simulation: Max threads, massive packet size (1500 bytes MTU)
        payload = {"timestamp": "0", "src_ip": random_ip, "dst_ip": "192.168.1.1", "protocol": "TCP", "size": "1500", "tenant_id": TENANT_ID}
        print(f"[Simulator] Flooding network for 120 seconds from {random_ip}")
        for _ in range(50):
            t = threading.Thread(target=worker_func, args=(*args_prefix, dict(payload), 120, 0))
            t.start()
            threads.append(t)
            
    elif attack_type == "portscan":
        # Port Scan Simulation: High frequency of tiny TCP SYN packets (40 bytes)
        payload = {"timestamp": "0", "src_ip": random_ip, "dst_ip": "192.168.1.1", "protocol": "TCP", "size": "40", "tenant_id": TENANT_ID}
        print(f"[Simulator] Firing thousands of tiny SYN packets for 120 seconds from {random_ip}")
        for _ in range(40):
            t = threading.Thread(target=worker_func, args=(*args_prefix, dict(payload), 120, 0))
            t.start()
            threads.append(t)
            
    elif attack_type == "bruteforce":
        # Brute Force Simulation: Moderate frequency, average payload size (e.g. repeated login attempts)
        payload = {"timestamp": "0", "src_ip": random_ip, "dst_ip": "192.168.1.1", "protocol": "TCP", "size": "350", "tenant_id": TENANT_ID}
        print(f"[Simulator] Rapidly guessing passwords for 120 seconds from {random_ip}")
        for _ in range(25):
            t = threading.Thread(target=worker_func, args=(*args_prefix, dict(payload), 120, 0.05))
            t.start()
            threads.append(t)
            
    for t in threads:
        t.join()
        
    print("[Simulator] Attack complete.")

if __name__ == "__main__":
    print("========================================")
    print("      MALICIOUS ATTACK SIMULATOR")
    print("========================================")
    print("1: DDoS (High Packets, Huge Bandwidth)")
    print("2: Port Scan (Very High Packets, Tiny Bandwidth)")
    print("3: Brute Force (Moderate Packets, Moderate Bandwidth)")
    print("========================================")
    
    choice = input("Select an attack type (1/2/3) or hit Enter for Random: ").strip()
    
    attack_map = {"1": "ddos", "2": "portscan", "3": "bruteforce"}
    
    if choice in attack_map:
        attack_type = attack_map[choice]
    else:
        attack_type = random.choice(["ddos", "portscan", "bruteforce"])
        print(f"Randomly selected: {attack_type.upper()}")
        
    simulate_attack(attack_type)
