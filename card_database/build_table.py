import json

def build_table():
    with open("C:\\Users\\chefj\\.gemini\\antigravity\\scratch\\card_database\\dsk_cards.json", "r", encoding="utf-8") as f:
        cards = json.load(f)

    with open("C:\\Users\\chefj\\.gemini\\antigravity\\scratch\\card_database\\duskmourn_prices.txt", "w", encoding="utf-8") as out:
        out.write("Card Name\tSet Code\tSet Number\tSKU\tRarity\tPrice (USD)\n")
        
        for card in cards:
            name = card.get("name", "Unknown")
            set_code = card.get("set", "dsk").upper()
            collector_number = card.get("collector_number", "")
            rarity = card.get("rarity", "common").capitalize()
            
            # Generate SKU using Set Info (e.g., DSK001, DSK255)
            sku = f"{set_code}{collector_number.zfill(3)}" if collector_number.isdigit() else f"{set_code}{collector_number}"
            
            prices = card.get("prices", {})
            price = prices.get("usd")
            if not price:
                price = prices.get("usd_foil")
            
            if price:
                price_str = f"${price}"
            else:
                price_str = "N/A"
                
            out.write(f"{name}\t{set_code}\t{collector_number}\t{sku}\t{rarity}\t{price_str}\n")

if __name__ == "__main__":
    build_table()
