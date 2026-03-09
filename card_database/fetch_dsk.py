import requests
import json
import time

def get_dsk_cards():
    url = "https://api.scryfall.com/cards/search?q=set:dsk"
    cards = []
    while url:
        print(f"Fetching {url}")
        response = requests.get(url)
        data = response.json()
        cards.extend(data['data'])
        url = data.get('next_page')
        time.sleep(0.1)  # Scryfall rate limit

    with open("dsk_cards.json", "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2)

    print(f"Total cards fetched: {len(cards)}")

if __name__ == "__main__":
    get_dsk_cards()
