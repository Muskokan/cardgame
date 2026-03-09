import requests
import json
import time
import os
from datetime import datetime

# Define file paths
DATABASE_DIR = r"C:\Users\chefj\.gemini\antigravity\scratch\card_database"
JSON_FILE = os.path.join(DATABASE_DIR, "inventory_prices.json")
TXT_FILE = os.path.join(DATABASE_DIR, "inventory_prices.txt")

# The list of sets you want to track (e.g. 'dsk' for Duskmourn)
SETS_TO_TRACK = ["dsk"]

def fetch_set_data(set_code):
    """Fetch all cards for a specific set from Scryfall."""
    url = f"https://api.scryfall.com/cards/search?q=set:{set_code}"
    cards = []
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching data for set: {set_code.upper()}...")
    
    while url:
        response = requests.get(url)
        
        # Handle rate limiting or errors
        if response.status_code != 200:
            print(f"Error fetching data: HTTP {response.status_code}")
            time.sleep(1)
            continue
            
        data = response.json()
        cards.extend(data['data'])
        url = data.get('next_page')
        time.sleep(0.1)  # Respect Scryfall's rate limit (10 requests per second)
        
    return cards

def update_prices():
    """Fetch new data and build the updated text file."""
    all_cards = []
    for set_code in SETS_TO_TRACK:
        all_cards.extend(fetch_set_data(set_code))
        
    # Save the raw JSON data as a backup
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(all_cards, f, indent=2)

    # Build the updated text file
    with open(TXT_FILE, "w", encoding="utf-8") as out:
        out.write(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        out.write("Card Name\tSet Code\tSet Number\tSKU\tRarity\tPrice (USD)\n")
        
        for card in all_cards:
            name = card.get("name", "Unknown")
            set_code = card.get("set", "unknown").upper()
            collector_number = str(card.get("collector_number", ""))
            rarity = card.get("rarity", "common").capitalize()
            
            # Generate SKU
            sku = f"{set_code}{collector_number.zfill(3)}" if collector_number.isdigit() else f"{set_code}{collector_number}"
            
            # Extract price
            prices = card.get("prices", {})
            price = prices.get("usd") or prices.get("usd_foil")
            
            price_str = f"${price}" if price else "N/A"
                
            out.write(f"{name}\t{set_code}\t{collector_number}\t{sku}\t{rarity}\t{price_str}\n")
            
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Prices updated successfully! Saved to {TXT_FILE}")

def run_scheduler(interval_hours=24):
    """Run the update process repeatedly at the specified interval."""
    print(f"Starting MTG Price Updater. Interval: {interval_hours} hours.")
    print("Press Ctrl+C to stop.")
    
    try:
        while True:
            update_prices()
            # Wait for the next interval (hours to seconds)
            sleep_time = interval_hours * 3600
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Sleeping for {interval_hours} hours...")
            time.sleep(sleep_time)
            
    except KeyboardInterrupt:
        print("\nUpdater stopped by user.")

if __name__ == "__main__":
    # You can change 'interval_hours' to determine how often it checks for new prices.
    # Scryfall usually updates prices once daily.
    run_scheduler(interval_hours=24)
