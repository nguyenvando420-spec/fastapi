import requests
import json

BASE_URL = "http://localhost:8000"

def verify():
    import time
    suffix = int(time.time())
    # 1. Create System
    sys_name = f"verify_sys_{suffix}"
    sys_payload = {"name": sys_name, "description": "Verification system"}
    resp = requests.post(f"{BASE_URL}/api/v1/admin/systems", json=sys_payload)
    if resp.status_code != 201:
        print(f"System creation failed: {resp.text}")
        return
    system = resp.json()
    sys_id = system["id"]
    print(f"Created System: {system['name']} ({sys_id})")

    # 2. Create Domain
    dom_name = f"verify_dom_{suffix}"
    dom_payload = {
        "name": dom_name,
        "version": "v1",
        "system_id": sys_id,
        "description": "Verification domain"
    }
    resp = requests.post(f"{BASE_URL}/api/v1/admin/domains", json=dom_payload)
    if resp.status_code != 201:
        print(f"Domain creation failed: {resp.text}")
        return
    domain = resp.json()
    print(f"Created Domain: {domain['name']}")

    # 3. Tokenize lần 1
    tok_payload = {
        "system_name": sys_name,
        "domain_name": dom_name,
        "data": ["Apple", "Banana", "Cherry"]
    }
    print("\n--- Tokenize lần 1 ---")
    resp = requests.post(f"{BASE_URL}/api/v1/tokens/tokenize", json=tok_payload)
    if resp.status_code != 201:
        print(f"Tokenization 1 failed: {resp.text}")
        return
    print("Lần 1 thành công!")

    # 4. Tokenize lần 2 (Cùng dữ liệu => Test Idempotency)
    print("\n--- Tokenize lần 2 (Trùng dữ liệu) ---")
    resp = requests.post(f"{BASE_URL}/api/v1/tokens/tokenize", json=tok_payload)
    if resp.status_code != 201:
        print(f"Tokenization 2 failed: {resp.text}")
        return
    results = resp.json()
    print("Lần 2 thành công (Đã xử lý duplicate key)!")
    # 5. De-tokenize mapping
    print("\n--- De-tokenize mapping ---")
    tokens = list(results['results'].values())
    detok_payload = {
        "system_name": sys_name,
        "domain_name": dom_name,
        "tokens": tokens
    }
    resp = requests.post(f"{BASE_URL}/api/v1/tokens/detokenize", json=detok_payload)
    if resp.status_code != 200:
        print(f"De-tokenization failed: {resp.text}")
        return
    detok_results = resp.json()
    print("De-tokenization thành công!")
    print("Mapping Results (Token -> Data):")
    print(json.dumps(detok_results['results'], indent=4))

if __name__ == "__main__":
    verify()
