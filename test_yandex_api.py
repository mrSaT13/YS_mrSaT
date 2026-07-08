"""Yandex Music API explorer — test what's possible."""
import asyncio
import aiohttp
import json
import sys

BASE = "https://api.music.yandex.net"
HEADERS = {"X-Yandex-Music-Client": "YandexMusicDesktop/5.0"}


async def explore(token: str):
    headers = {**HEADERS, "Authorization": f"OAuth {token}"}
    
    async with aiohttp.ClientSession(headers=headers) as s:
        # 1. Who am I?
        print("=== Account ===")
        async with s.get(f"{BASE}/me") as r:
            data = await r.json()
            print(json.dumps(data, indent=2, ensure_ascii=False)[:500])
        
        # 2. Search artist
        print("\n=== Search: Limp Bizkit (artist) ===")
        async with s.get(f"{BASE}/search", params={"text": "Limp Bizkit", "type": "artist", "page": 0, "nococruct": "no"}) as r:
            data = await r.json()
            artists = data.get("result", {}).get("artists", {}).get("results", [])
            for a in artists[:3]:
                print(f"  {a['name']} (id={a['id']}, albums={a.get('albumsCount',0)}, tracks={a.get('tracksCount',0)})")
        
        # 3. Search track
        print("\n=== Search: Limp Bizkit (track) ===")
        async with s.get(f"{BASE}/search", params={"text": "Limp Bizkit", "type": "track", "page": 0}) as r:
            data = await r.json()
            tracks = data.get("result", {}).get("tracks", {}).get("results", [])
            for t in tracks[:5]:
                artists_str = ", ".join(a["name"] for a in t.get("artists", []))
                print(f"  {artists_str} — {t['title']} (id={t['id']}, duration={t.get('durationMs',0)//1000}s)")
        
        # 4. Get artist info
        if artists:
            artist_id = artists[0]["id"]
            print(f"\n=== Artist {artists[0]['name']} (id={artist_id}) ===")
            async with s.get(f"{BASE}/artists/{artist_id}/brief-info") as r:
                data = await r.json()
                result = data.get("result", {})
                print(f"  Name: {result.get('name')}")
                print(f"  Albums: {result.get('albums', [{}])[0].get('id') if result.get('albums') else 'N/A'}")
                print(f"  Popular tracks: {len(result.get('popularTracks', []))}")
                for t in result.get("popularTracks", [])[:5]:
                    print(f"    {t.get('title', '?')} (id={t.get('id')})")
        
        # 5. Get artist tracks
        if artists:
            print(f"\n=== Tracks by {artists[0]['name']} ===")
            async with s.get(f"{BASE}/artists/{artist_id}/tracks", params={"page-size": 10}) as r:
                data = await r.json()
                tracks = data.get("result", {}).get("tracks", [])
                for t in tracks[:10]:
                    print(f"  {t.get('title', '?')} (id={t.get('id')})")
        
        # 6. Get track info (preview)
        if tracks:
            track_id = tracks[0].get("id")
            if track_id:
                print(f"\n=== Track info (id={track_id}) ===")
                async with s.get(f"{BASE}/tracks/{track_id}") as r:
                    data = await r.json()
                    result = data.get("result", [{}])[0] if data.get("result") else {}
                    print(f"  Title: {result.get('title')}")
                    print(f"  Duration: {result.get('durationMs',0)//1000}s")
                    print(f"  hasRightholds: {result.get('hasRightholds')}")
                    print(f"  isAvailable: {result.get('isAvailable')}")
                    print(f"  isPremium: {result.get('isPremium')}")
                    download_info = result.get("downloadInfo", [])
                    print(f"  Download info: {len(download_info)} entries")
                    for d in download_info[:3]:
                        print(f"    codec={d.get('codec')}, bitrate={d.get('bitrateInKbps')}")
        
        # 7. Get file info (preview URLs)
        if tracks:
            track_id = tracks[0].get("id")
            if track_id:
                print(f"\n=== File info (id={track_id}) ===")
                async with s.get(f"{BASE}/tracks/{track_id}/download-info") as r:
                    data = await r.json()
                    result = data.get("result", [])
                    for d in result[:3]:
                        print(f"  codec={d.get('codec')}, bitrate={d.get('bitrateInKbps')}, url={d.get('downloadInfoUrl', '')[:80]}")
        
        # 8. Landing / charts
        print("\n=== Landing (charts) ===")
        async with s.get(f"{BASE}/landing3", params={"blocks": "chart"}) as r:
            data = await r.json()
            charts = data.get("result", {}).get("chart", [])
            for c in charts[:3]:
                print(f"  {c.get('title', '?')} (id={c.get('id')})")
        
        # 9. User playlists
        print("\n=== User playlists ===")
        async with s.get(f"{BASE}/users/likes/playlists") as r:
            data = await r.json()
            result = data.get("result", [])
            for p in result[:5]:
                print(f"  {p.get('title', '?')} (uid={p.get('uid')}, kind={p.get('kind')})")
        
        # 10. Search genre
        print("\n=== Search: рок (artist) ===")
        async with s.get(f"{BASE}/search", params={"text": "рок", "type": "artist", "page": 0}) as r:
            data = await r.json()
            artists = data.get("result", {}).get("artists", {}).get("results", [])
            for a in artists[:5]:
                print(f"  {a['name']} (id={a['id']})")
        
        # 11. Get stations (radio)
        print("\n=== Stations (radio) ===")
        async with s.get(f"{BASE}/editorial/stations") as r:
            data = await r.json()
            stations = data.get("result", {}).get("stations", [])
            for st in stations[:5]:
                name = st.get("name", "?")
                station_id = st.get("id", "?")
                print(f"  {name} (id={station_id})")
        
        # 12. Test premium detection
        if tracks:
            track_id = tracks[0].get("id")
            if track_id:
                print(f"\n=== Premium detection (id={track_id}) ===")
                async with s.get(f"{BASE}/tracks/{track_id}") as r:
                    data = await r.json()
                    result = data.get("result", [{}])[0] if data.get("result") else {}
                    is_premium = result.get("isPremium")
                    has_rightholds = result.get("hasRightholds")
                    download_info = result.get("downloadInfo", [])
                    print(f"  isPremium: {is_premium}")
                    print(f"  hasRightholds: {has_rightholds}")
                    print(f"  downloadInfo count: {len(download_info)}")
                    
                    # Determine if track is premium-only
                    is_premium_only = is_premium or has_rightholds or not download_info
                    print(f"  Premium-only: {is_premium_only}")
        
        print("\n=== DONE ===")


if __name__ == "__main__":
    token = input("Вставь X-Token: ").strip()
    if not token:
        print("Токен пустой!")
        sys.exit(1)
    asyncio.run(explore(token))
