import asyncio
import httpx
import sys
import re

# Default configuration values
default_prefix_start = 1200
default_prefix_end = 1500
default_concurrency = 25
base_url = "https://track.bpost.cloud/track/items"

# Global signal to stop when a valid result is found
found_event = asyncio.Event()

def get_int_input(prompt, default):
    user_input = input(f"{prompt} (default: {default}): ").strip()
    if not user_input:
        return default
    try:
        return int(user_input)
    except ValueError:
        print("Invalid input, using default.")
        return default

# Ask if global journey order
is_global = input("Is this a global journey order? (yes/no): ").strip().lower()
if is_global in ("yes", "y"):
    print("Sorry, Global journey orders are not supported.")
    sys.exit(0)

# Prompt for user inputs
order_id = input("Enter the order ID: ").strip()
postcode = input("Enter the postcode: ").strip()
prefix_start = get_int_input("Enter prefix start", default_prefix_start)
prefix_end = get_int_input("Enter prefix end", default_prefix_end)
concurrency = get_int_input("Enter concurrency level", default_concurrency)

# Extract barcode from JSON
def extract_barcode(response_json: dict) -> str:
    try:
        items = response_json.get("items", [])
        if items:
            url = items[0].get("webformUrl", {}).get("en", "")
            match = re.search(r"barcode=([A-Z0-9]+)", url)
            return match.group(1) if match else None
    except Exception:
        pass
    return None

# Check if the response is interesting
async def is_interesting_response(prefix: int, response: httpx.Response):
    try:
        json_data = response.json()
        if json_data.get("error") == "NO_DATA_FOUND":
            return False
        barcode = extract_barcode(json_data)
        if barcode:
            print(
                f"\n[VALID] Order ID: {prefix}-{order_id}\n"
                f"        Postcode: {postcode}\n"
                f"        Barcode: {barcode}\n"
                f"        Tracking URL: https://track.bpost.cloud/btr/web/#/search?itemCode={barcode}&lang=en&postalCode={postcode}\n"
            )
            return True
    except Exception:
        pass
    return False

# Attempt request
async def try_prefix(client: httpx.AsyncClient, prefix: int):
    if found_event.is_set():
        return
    item_id = f"{prefix}-{order_id}"
    params = {
        "itemIdentifier": item_id,
        "postalCode": postcode
    }
    try:
        response = await client.get(base_url, params=params, timeout=10)
        if await is_interesting_response(prefix, response):
            found_event.set()
        else:
            print(f"[NO DATA] {item_id}")
    except httpx.RequestError as e:
        print(f"[ERROR] {item_id}: {e}")

# Main runner
async def main():
    async with httpx.AsyncClient() as client:
        for chunk_start in range(prefix_start, prefix_end, concurrency):
            tasks = [
                try_prefix(client, prefix)
                for prefix in range(chunk_start, min(chunk_start + concurrency, prefix_end))
            ]
            await asyncio.gather(*tasks)
            if found_event.is_set():
                break

# Entry point
if __name__ == "__main__":
    asyncio.run(main())
