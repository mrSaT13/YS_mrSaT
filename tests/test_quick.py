"""Quick test - get-file-info with full response dump."""
import sys
import io
import asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

async def test(x_token: str):
    import aiohttp
    import hashlib
    import hmac
    import base64
    from datetime import datetime

    DESKTOP_SECRET_KEY = "kzqU4XhfCaY6B6JTHODeq5"
    DESKTOP_CODECS = "flac,aac,he-aac,mp3,flac-mp4,aac-mp4,he-aac-mp4"
    track_id = 33267  # Marilyn Manson - The Beautiful People

    def sign_hmac(secret_key, *args):
        msg = "".join(str(i) for i in args).replace(",", "").encode()
        h = hmac.new(secret_key.encode(), msg, hashlib.sha256).digest()
        return base64.b64encode(h).decode()[:-1]

    async with aiohttp.ClientSession() as session:
        # Desktop approach
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

        print("=== Desktop approach (full response) ===")
        async with session.get(
            "https://api.music.yandex.net/get-file-info",
            params=params,
            headers=headers,
        ) as r:
            raw = await r.json()
            print(f"Status: {r.status}")

            import json
            # Pretty print the full response (hide direct_url for brevity if too long)
            result = raw.get("result", {})
            download_info = result.get("downloadInfo", {})

            print(f"\nFull result keys: {list(result.keys())}")
            print(f"Download info keys: {list(download_info.keys())}")
            print(f"\ndownloadInfo full:")
            for k, v in download_info.items():
                if k == "direct_url" and v:
                    print(f"  {k}: {v[:80]}... (length={len(v)})")
                else:
                    print(f"  {k}: {v}")

            # If we have a direct_url, test it
            url = download_info.get("direct_url", "")
            if url:
                print(f"\n=== Testing URL ===")
                async with session.head(url, allow_redirects=True) as resp:
                    print(f"Status: {resp.status}")
                    ct = resp.headers.get('Content-Type', '')
                    cl = resp.headers.get('Content-Length', '0')
                    print(f"Content-Type: {ct}")
                    print(f"Size: {int(cl)//1024}KB")
                    if resp.status == 200:
                        print("[OK] URL is accessible!")
                        if 'audio' in ct:
                            print("[OK] It's an audio file!")
                        else:
                            print(f"[WARN] Content-Type is not audio: {ct}")
                    else:
                        print(f"[FAIL] HTTP {resp.status}")
            else:
                print("\n[WARN] No direct_url in response")
                # Try nq quality
                print("\n=== Trying nq quality ===")
                timestamp2 = int(datetime.now().timestamp())
                sign_data2 = f"{timestamp2}{track_id}nq{DESKTOP_CODECS}encraw"
                signature2 = sign_hmac(DESKTOP_SECRET_KEY, sign_data2)
                params["ts"] = timestamp2
                params["quality"] = "nq"
                params["sign"] = signature2

                async with session.get(
                    "https://api.music.yandex.net/get-file-info",
                    params=params,
                    headers=headers,
                ) as r2:
                    raw2 = await r2.json()
                    di2 = raw2.get("result", {}).get("downloadInfo", {})
                    url2 = di2.get("direct_url", "")
                    if url2:
                        print(f"[OK] nq URL: {url2[:80]}...")
                        async with session.head(url2, allow_redirects=True) as resp2:
                            print(f"Status: {resp2.status}, Size: {resp2.headers.get('Content-Length', '?')}")
                    else:
                        print(f"nq also no URL. Keys: {list(di2.keys())}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(test(sys.argv[1]))
    else:
        print("Usage: python test_quick.py <x_token>")
