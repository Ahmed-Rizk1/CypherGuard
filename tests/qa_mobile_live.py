import requests
import asyncio
import json
import uuid

BASE_URL = "http://16.171.61.103:8005"
EMAIL = "mobiledev@securenet.local"
PASSWORD = "MobileDev123!"

token = None
refresh_token = None
results = []

def log(test_name, method, endpoint, expected, actual, passed, msg=""):
    results.append({
        "Test": test_name,
        "Method": method,
        "Endpoint": endpoint,
        "Status": "PASS" if passed else "FAIL",
        "Info": f"Expected {expected}, got {actual}. {msg}"
    })
    print(f"[{'PASS' if passed else 'FAIL'}] {test_name}: {method} {endpoint} -> {actual}")

def run_tests():
    global token, refresh_token
    
    print("Starting QA Tests...")
    
    # 1. Auth - Valid Login
    res = requests.post(f"{BASE_URL}/v1/mobile/auth", json={"email": EMAIL, "password": PASSWORD})
    if res.status_code == 200:
        data = res.json().get("data", {})
        token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        log("Valid Login", "POST", "/v1/mobile/auth", 200, res.status_code, True, res.text)
    else:
        log("Valid Login", "POST", "/v1/mobile/auth", 200, res.status_code, False, res.text)
        
    # 2. Auth - Invalid Login
    res = requests.post(f"{BASE_URL}/v1/mobile/auth", json={"email": EMAIL, "password": "wrongpassword"})
    log("Invalid Login", "POST", "/v1/mobile/auth", 401, res.status_code, res.status_code == 401, res.text)
    
    # 3. Auth - Missing Field
    res = requests.post(f"{BASE_URL}/v1/mobile/auth", json={"email": EMAIL})
    log("Missing Field Login", "POST", "/v1/mobile/auth", 422, res.status_code, res.status_code == 422, res.text)

    headers = {"Authorization": f"Bearer {token}"}
    
    # 4. Get Current User
    res = requests.get(f"{BASE_URL}/v1/mobile/users/me", headers=headers)
    log("Get Current User", "GET", "/v1/mobile/users/me", 200, res.status_code, res.status_code == 200, res.text)

    # 5. Get Current User - Unauthorized
    res = requests.get(f"{BASE_URL}/v1/mobile/users/me", headers={"Authorization": "Bearer invalid"})
    log("Unauthorized Access", "GET", "/v1/mobile/users/me", 401, res.status_code, res.status_code == 401, res.text)
    
    # 6. Dashboard Summary
    res = requests.get(f"{BASE_URL}/v1/mobile/dashboard/summary", headers=headers)
    log("Dashboard Summary", "GET", "/v1/mobile/dashboard/summary", 200, res.status_code, res.status_code == 200, res.text)

    # 7. List Alerts
    res = requests.get(f"{BASE_URL}/v1/mobile/alerts?limit=5", headers=headers)
    log("List Alerts", "GET", "/v1/mobile/alerts", 200, res.status_code, res.status_code == 200, res.text)
    alerts = res.json().get("items", []) if res.status_code == 200 else []
    
    alert_id = str(uuid.uuid4())
    if alerts:
        alert_id = alerts[0]["id"]

    # 8. Get Alert Detail (Valid or 404 if not found)
    res = requests.get(f"{BASE_URL}/v1/mobile/alerts/{alert_id}", headers=headers)
    log("Get Alert Details", "GET", f"/v1/mobile/alerts/{{id}}", "200/404", res.status_code, res.status_code in [200, 404], res.text)

    # 9. Update Alert Status
    res = requests.put(f"{BASE_URL}/v1/mobile/alerts/{alert_id}/status", json={"status": "resolved"}, headers=headers)
    log("Update Alert Status", "PUT", f"/v1/mobile/alerts/{{id}}/status", "200/404", res.status_code, res.status_code in [200, 404], res.text)
    
    # 10. List Decisions
    res = requests.get(f"{BASE_URL}/v1/mobile/decisions", headers=headers)
    log("List Decisions", "GET", "/v1/mobile/decisions", 200, res.status_code, res.status_code == 200, res.text)

    # 11. Submit Decision
    res = requests.post(f"{BASE_URL}/v1/mobile/decision", json={
        "alert_id": alert_id,
        "action": "APPROVE"
    }, headers=headers)
    log("Submit Decision", "POST", "/v1/mobile/decision", "200/404/400/409", res.status_code, res.status_code in [200, 400, 404, 409], res.text)

    # 12. List Firewall Rules
    res = requests.get(f"{BASE_URL}/v1/mobile/firewall", headers=headers)
    log("List Firewall Rules", "GET", "/v1/mobile/firewall", 200, res.status_code, res.status_code == 200, res.text)

    # 13. Block IP
    res = requests.post(f"{BASE_URL}/v1/mobile/firewall/block", json={
        "ip_address": "1.2.3.4",
        "reason": "QA Test"
    }, headers=headers)
    log("Block IP", "POST", "/v1/mobile/firewall/block", "201/400/409", res.status_code, res.status_code in [201, 400, 409], res.text)

    # 14. Unblock IP
    res = requests.delete(f"{BASE_URL}/v1/mobile/firewall/block/1.2.3.4", headers=headers)
    log("Unblock IP", "DELETE", "/v1/mobile/firewall/block/{ip}", "200/400/404", res.status_code, res.status_code in [200, 400, 404], res.text)

    # 15. Register Device
    res = requests.post(f"{BASE_URL}/v1/mobile/devices/register", json={
        "fcm_token": "dummy_token_123",
        "device_name": "QA Phone",
        "platform": "android"
    }, headers=headers)
    log("Register FCM Device", "POST", "/v1/mobile/devices/register", 200, res.status_code, res.status_code == 200, res.text)

    # 16. Refresh Token
    res = requests.post(f"{BASE_URL}/v1/mobile/auth/refresh", json={
        "refresh_token": refresh_token
    })
    log("Refresh Token", "POST", "/v1/mobile/auth/refresh", 200, res.status_code, res.status_code == 200, res.text)
    
    if res.status_code == 200:
        data = res.json().get("data", {})
        token = data.get("access_token")
        headers = {"Authorization": f"Bearer {token}"}

    # 18. Change Password (restore to original)
    res = requests.post(f"{BASE_URL}/v1/mobile/users/me/password", json={
        "current_password": PASSWORD,
        "new_password": "MobileDev123!"
    }, headers=headers)
    log("Change Password", "POST", "/v1/mobile/users/me/password", 200, res.status_code, res.status_code == 200, res.text)

    # 19. Logout
    res = requests.post(f"{BASE_URL}/v1/mobile/auth/logout", headers=headers)
    log("Logout", "POST", "/v1/mobile/auth/logout", 200, res.status_code, res.status_code == 200, res.text)

    print("\n=== QA REPORT ===")
    passed_count = sum(1 for r in results if r['Status'] == 'PASS')
    failed_count = sum(1 for r in results if r['Status'] == 'FAIL')
    for r in results:
        print(f"[{r['Status']}] {r['Method']} {r['Endpoint']} - {r['Test']} - {r['Info']}")
    print(f"\nTotal: {len(results)} | Passed: {passed_count} | Failed: {failed_count}")

if __name__ == "__main__":
    run_tests()
