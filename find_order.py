import sys
import asyncio
import http.client
import json
import re
import urllib.parse

# For Windows console to support UTF-8 properly (optional)
if sys.platform == "win32":
    import os
    os.system('chcp 65001')

# Default config and other code as before...

prefix_start = 1200
prefix_end = 1500
concurrency = 15
base_host = "track.bpost.cloud"
base_path = "/track/items"

found_event = asyncio.Event()

def get_int_input(prompt, default):
    user_input = input(f"{prompt} (ברירת מחדל: {default}): ").strip()
    if not user_input:
        return default
    try:
        return int(user_input)
    except ValueError:
        print("קלט לא תקין - משתמש בערכים ברירת מחדל.")
        return default

# Now Hebrew input prompts example:

is_global = input("האם זה חבילה של הגלובל ג'רני? (כן/לא): ").strip().lower()
if is_global in ("כן", "y", "yes"):
    print("מצטערים, גלובל ג'רני לא נתמך.")
    sys.exit(0)

order_id = input("הכנס מספר הזמנה (מופיע ב https://my.tomorrowland.com/orders): ").strip()
postcode = input("הכנס מיקוד של הקונה הראשי: ").strip()

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
        if json_data.get("error") == "לא נמצא":
            return False
        barcode = extract_barcode(json_data)
        if barcode:
            print(
                f"\n[החבילה נמצאה!] מספר הזמנה: {prefix}-{order_id}\n"
                f"         ברקוד: {barcode}\n"
                f"         כתובת מעקב: https://track.bpost.cloud/btr/web/#/search?itemCode={barcode}&lang=en&postalCode={postcode}\n"
                f"         יש לשמור את הקישור כדי לעקוב על ההזמנה בעתיד\n"
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
        print(f"[שגיאה] {item_id}: {body}")
        return
    if await is_interesting_response(prefix, status, body):
        found_event.set()
    else:
        print(f"[אין נתונים] {item_id}")

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
