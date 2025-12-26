import asyncio
import aiohttp
import json
from config import GPRO_API_TOKEN, GPRO_LANG

async def debug_api():
    url = f"https://gpro.net/{GPRO_LANG}/backend/api/v2/Calendar"
    headers = {
        "Authorization": f"Bearer {GPRO_API_TOKEN}",
        "User-Agent": "GPRO-QualiBot/1.0"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            print(f"✅ Status: {resp.status}")
            text = await resp.text()
            print(f"\n📄 Response Preview (1000 chars):")
            print(repr(text[:1000]))
            
            try:
                data = json.loads(text)
                print(f"\n🔍 Top-level keys: {list(data.keys())}")
                print(f"🔍 Data types: {type(data)}")
                
                # Show first race if exists
                races = data.get('races', [])
                if races:
                    print(f"✅ Races found: {len(races)}")
                    print(f"First race keys: {list(races[0].keys())}")
                else:
                    print("❌ No 'races' key - checking alternatives...")
                    for key in data.keys():
                        if isinstance(data[key], list):
                            print(f"  List '{key}': {len(data[key])} items")
                            
            except json.JSONDecodeError:
                print("❌ Not valid JSON")

asyncio.run(debug_api())
