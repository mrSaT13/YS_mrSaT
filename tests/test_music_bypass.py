"""Test Music Plus bypass - standalone (no HA dependency)."""
import sys
import io
import asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

async def test_bypass():
    import aiohttp
    import hashlib
    import hmac
    import base64
    from datetime import datetime

    DESKTOP_SECRET_KEY = "kzqU4XhfCaY6B6JTHODeq5"
    DESKTOP_CODECS = "flac,aac,he-aac,mp3,flac-mp4,aac-mp4,he-aac-mp4"

    def sign_hmac(secret_key, *args):
        msg = "".join(str(i) for i in args).replace(",", "").encode()
        h = hmac.new(secret_key.encode(), msg, hashlib.sha256).digest()
        return base64.b64encode(h).decode()[:-1]

    # Step 1: Search
    print("=== Step 1: Search ===")
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://api.music.yandex.net/search",
            params={"text": "Marilyn Manson The Beautiful People", "type": "track", "page": 0}
        ) as r:
            raw = await r.json()
            tracks = raw.get("result", {}).get("tracks", {}).get("results", [])
            if tracks:
                track = tracks[0]
                track_id = track['id']
                title = track['title']
                artist = track['artists'][0]['name']
                print(f"[OK] Found: {title} by {artist} (id={track_id})")
            else:
                print("[FAIL] No tracks found")
                return

    # Step 2: Try to get download URL (will fail without auth, but let's see the response)
    print(f"\n=== Step 2: get-file-info for track {track_id} ===")
    timestamp = int(datetime.now().timestamp())
    sign_data = f"{timestamp}{track_id}lossless{DESKTOP_CODECS}encraw"
    signature = sign_hmac(DESKTOP_SECRET_KEY, sign_data)

    params = {
        "ts": timestamp,
        "trackId": track_id,
        "quality": "lossless",
        "codecs": DESKTOP_CODECS,
        "transports": "encraw",
        "sign": signature,
    }
    headers = {
        "X-Yandex-Music-Client": "YandexMusicDesktopAppWindows/5.28.1",
        "X-Yandex-Music-Frontend": "new",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://api.music.yandex.net/get-file-info",
            params=params,
            headers=headers,
        ) as r:
            raw = await r.json()
            print(f"Status: {r.status}")
            if r.status == 200:
                info = raw.get("result", {}).get("downloadInfo", {})
                if info:
                    print(f"[OK] Download info: trackId={info.get('trackId')}, codec={info.get('codec')}, bitrate={info.get('bitrate_in_kbps')}")
                    url = info.get("direct_url", "")
                    if url:
                        print(f"  URL: {url[:120]}...")

                        # Step 3: Test URL
                        print(f"\n=== Step 3: Test URL ===")
                        async with session.head(url, allow_redirects=True) as resp:
                            print(f"Status: {resp.status}")
                            print(f"Content-Type: {resp.headers.get('Content-Type')}")
                            print(f"Content-Length: {resp.headers.get('Content-Length')}")
                            if resp.status == 200:
                                print("[OK] URL works!")
                            else:
                                print(f"[WARN] URL returned {resp.status}")
                else:
                    print(f"[INFO] No downloadInfo in response")
                    print(f"  Response: {str(raw)[:300]}")
            else:
                print(f"[INFO] HTTP {r.status}")
                print(f"  Response: {str(raw)[:300]}")

    # Step 4: Try with Android approach
    print(f"\n=== Step 4: Android approach ===")
    timestamp = int(datetime.now().timestamp())
    android_codecs = "flac,aac,he-aac,mp3"
    params_android = {
        "ts": timestamp,
        "trackId": track_id,
        "quality": "lossless",
        "codecs": android_codecs,
        "transports": "raw",
    }
    params_android["sign"] = sign_hmac("p93jhgh689SBReK6ghtw62", *params_android.values())
    headers_android = {"X-Yandex-Music-Client": "YandexMusicAndroid/24023621"}

    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://api.music.yandex.net/get-file-info",
            params=params_android,
            headers=headers_android,
        ) as r:
            raw = await r.json()
            print(f"Status: {r.status}")
            if r.status == 200:
                info = raw.get("result", {}).get("downloadInfo", {})
                if info:
                    print(f"[OK] Download info: trackId={info.get('trackId')}, codec={info.get('codec')}")
                    url = info.get("direct_url", "")
                    if url:
                        print(f"  URL: {url[:120]}...")
            else:
                print(f"  Response: {str(raw)[:200]}")

    print("\n=== Summary ===")
    print("1. Search works without auth")
    print("2. get-file-info requires auth token (x_token)")
    print("3. With valid x_token, the Desktop approach + retries should bypass ads")
    print("\nTo test with full auth, run:")
    print("  python tests/test_music_bypass.py <x_token>")

async def test_with_token(x_token: str):
    import aiohttp
    import hashlib
    import hmac
    import base64
    from datetime import datetime

    DESKTOP_SECRET_KEY = "kzqU4XhfCaY6B6JTHODeq5"
    DESKTOP_CODECS = "flac,aac,he-aac,mp3,flac-mp4,aac-mp4,he-aac-mp4"

    def sign_hmac(secret_key, *args):
        msg = "".join(str(i) for i in args).replace(",", "").encode()
        h = hmac.new(secret_key.encode(), msg, hashlib.sha256).digest()
        return base64.b64encode(h).decode()[:-1]

    print(f"=== Testing with x_token: {x_token[:10]}... ===")

    async with aiohttp.ClientSession() as session:
        # Auth check
        print("\n--- Auth check ---")
        async with session.get(
            "https://api.music.yandex.net/account/about",
            headers={"Authorization": f"OAuth {x_token}"}
        ) as r:
            raw = await r.json()
            if r.status == 200:
                print(f"[OK] Logged in: {raw.get('result', {}).get('login')} (uid={raw.get('result', {}).get('uid')})")
            else:
                print(f"[FAIL] Auth failed: {r.status} {str(raw)[:200]}")
                return

        # Search
        print("\n--- Search ---")
        async with session.get(
            "https://api.music.yandex.net/search",
            params={"text": "Marilyn Manson The Beautiful People", "type": "track", "page": 0},
            headers={"Authorization": f"OAuth {x_token}"}
        ) as r:
            raw = await r.json()
            tracks = raw.get("result", {}).get("tracks", {}).get("results", [])
            if tracks:
                track = tracks[0]
                track_id = track['id']
                title = track['title']
                artist = track['artists'][0]['name']
                print(f"[OK] Found: {title} by {artist} (id={track_id})")
            else:
                print("[FAIL] No tracks found")
                return

        # Get download URL with Desktop approach (with retries)
        print(f"\n--- Download URL (Desktop approach with retries) ---")
        for attempt in range(5):
            timestamp = int(datetime.now().timestamp())
            sign_data = f"{timestamp}{track_id}lossless{DESKTOP_CODECS}encraw"
            signature = sign_hmac(DESKTOP_SECRET_KEY, sign_data)

            params = {
                "ts": timestamp,
                "trackId": track_id,
                "quality": "lossless",
                "codecs": DESKTOP_CODECS,
                "transports": "encraw",
                "sign": signature,
            }
            headers = {
                "X-Yandex-Music-Client": "YandexMusicDesktopAppWindows/5.28.1",
                "X-Yandex-Music-Frontend": "new",
                "Authorization": f"OAuth {x_token}",
            }

            async with session.get(
                "https://api.music.yandex.net/get-file-info",
                params=params,
                headers=headers,
            ) as r:
                raw = await r.json()
                if r.status == 200:
                    info = raw.get("result", {}).get("downloadInfo", {})
                    response_track_id = str(info.get("trackId", ""))
                    if response_track_id == str(track_id):
                        print(f"[OK] TrackId matches! (attempt {attempt + 1})")
                        print(f"  Codec: {info.get('codec')}, Bitrate: {info.get('bitrate_in_kbps')}kbps")
                        url = info.get("direct_url", "")
                        if url:
                            print(f"  URL: {url[:120]}...")

                            # Test URL
                            print(f"\n--- URL validation ---")
                            async with session.head(url, allow_redirects=True) as resp:
                                print(f"Status: {resp.status}")
                                ct = resp.headers.get('Content-Type', '')
                                cl = resp.headers.get('Content-Length', '0')
                                print(f"Content-Type: {ct}")
                                print(f"Size: {int(cl)//1024}KB")
                                if resp.status == 200 and 'audio' in ct:
                                    print("[OK] URL works! Real audio file!")
                                elif resp.status == 200:
                                    print("[WARN] URL returned 200 but not audio")
                                else:
                                    print(f"[FAIL] URL returned {resp.status}")
                        break
                    else:
                        print(f"  TrackId mismatch: requested={track_id}, got={response_track_id} (ad?) - retry {attempt+1}")
                        await asyncio.sleep(0.15)
                else:
                    print(f"  HTTP {r.status}: {str(raw)[:200]}")
                    break
        else:
            print("[FAIL] Could not get matching track URL after retries")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(test_with_token(sys.argv[1]))
    else:
        asyncio.run(test_bypass())
