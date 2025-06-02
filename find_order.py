import sys
import asyncio
import http.client
import json
import re
import urllib.parse

prefix_start = 1200
prefix_end = 1500
concurrency = 15
base_host = "track.bpost.cloud"
base_path = "/track/items"

found_event = asyncio.Event()

def get_int_input(prompt, default):
    user_input = input(f"{prompt} (default: {default}): ").strip()
    if not user_input:
        return default
    try:
        return int(user_input)
    except ValueError:
        print("Invalid input, uses default values")
        return default

# Now Hebrew input prompts example:

is_global = input("Is this a global journey order? (yes/no): ").strip().lower()
if is_global in ("כן", "y", "yes"):
    print("Sorry, Global journey orders are not supported.")
    input()
    sys.exit(0)

order_id = input("Enter the order ID (can be seen at https://my.tomorrowland.com/orders): ").strip()
postcode = input("Enter the postcode: (of the main buyer) ").strip()

def extract_barcode(response_json: dict) -> str | None:
    try:
        items = response_json.get("items", [])
        if items:
            url = items[0].get("webformUrl", {}).get("en", "")
            match = re.search(r"barcode=([A-Z0-9]+)", url)
            return match.group(1) if match else None
    except Exception:
        pass
    return None

def sync_http_get(params: dict) -> tuple[int, str]:
    query_string = urllib.parse.urlencode(params)
    path = base_path + "?" + query_string

    conn = http.client.HTTPSConnection(base_host, timeout=10)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        body = response.read().decode()
        return response.status, body
    except Exception as e:
        return 0, str(e)
    finally:
        conn.close()

async def is_interesting_response(prefix: int, status: int, body: str):
    if status != 200:
        return False
    try:
        json_data = json.loads(body)
        if json_data.get("error") == "NO_DATA_FOUND":
            return False
        barcode = extract_barcode(json_data)
        if barcode:
            print(
                f"\n[VALID] Order ID: {prefix}-{order_id}\n"
                f"        Barcode: {barcode}\n"
                f"        Tracking URL: https://track.bpost.cloud/btr/web/#/search?itemCode={barcode}&lang=en&postalCode={postcode}\n"
            )
            return True
    except Exception:
        pass
    return False

async def try_prefix(prefix: int):
    if found_event.is_set():
        return
    item_id = f"{prefix}-{order_id}"
    params = {
        "itemIdentifier": item_id,
        "postalCode": postcode
    }
    loop = asyncio.get_running_loop()
    status, body = await loop.run_in_executor(None, sync_http_get, params)
    if status == 0:
        print(f"[error] {item_id}: {body}")
        return
    if await is_interesting_response(prefix, status, body):
        found_event.set()
    else:
        print(f"[no data] {item_id}")

async def main():
    for chunk_start in range(prefix_start, prefix_end, concurrency):
        tasks = [
            try_prefix(prefix)
            for prefix in range(chunk_start, min(chunk_start + concurrency, prefix_end))
        ]
        await asyncio.gather(*tasks)
        if found_event.is_set():
            break

if __name__ == "__main__":
    asyncio.run(main())    