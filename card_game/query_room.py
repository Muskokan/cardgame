import sys, json, asyncio
sys.path.insert(0, r"c:\Users\chefj\.gemini\antigravity\scratch")

ROOM_CODE = "SVDD"
BOT_PLAYER_ID = "bot_1"
URI = f"ws://localhost:8001/ws/{ROOM_CODE}/{BOT_PLAYER_ID}"

async def dump_state():
    try:
        import websockets
        async with websockets.connect(URI) as ws:
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"ERROR: {e}")

asyncio.run(dump_state())
