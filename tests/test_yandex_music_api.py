"""Test yandex-music API with auth token."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_with_token(x_token: str):
    from yandex_music import Client
    
    print("--- Auth with x_token ---")
    try:
        client = Client(token=x_token).init()
        me = client.account
        print(f"[OK] Logged in as: {me.login} (uid={me.uid})")
        print(f"  Has Plus: {me.plus}")
    except Exception as e:
        print(f"[FAIL] Auth failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Search
    print("\n--- Search ---")
    try:
        results = client.search("Marilyn Manson The Beautiful People")
        if results and results.tracks and results.tracks.results:
            best = results.tracks.results[0]
            track_id = best.id
            print(f"[OK] Found: {best.title} by {[a.name for a in best.artists]} (id={track_id})")
        else:
            print("[FAIL] No results")
            return
    except Exception as e:
        print(f"[FAIL] Search failed: {e}")
        return
    
    # Download info
    print("\n--- Download info ---")
    try:
        download_info = client.tracks_download_info([track_id])
        if download_info:
            print(f"[OK] {len(download_info)} variants available")
            for info in download_info[:5]:
                url = info.direct_url[:100] if info.direct_url else "NO URL"
                print(f"  - {info.codec} {info.bitrate_in_kbps}kbps (size={info.file_size}): {url}...")
        else:
            print("[WARN] No download info")
    except Exception as e:
        print(f"[FAIL] Download info failed: {e}")

    # Test: does URL actually work?
    print("\n--- URL validation ---")
    if download_info:
        import urllib.request
        best_info = max(download_info, key=lambda x: x.bitrate_in_kbps)
        url = best_info.direct_url
        if url:
            try:
                req = urllib.request.Request(url, method='HEAD')
                resp = urllib.request.urlopen(req, timeout=10)
                print(f"[OK] URL works! Status={resp.status}, Content-Type={resp.headers.get('Content-Type')}, Size={resp.headers.get('Content-Length')}")
            except urllib.error.HTTPError as e:
                print(f"[FAIL] URL returned HTTP {e.code}")
                # Check if it's an ad redirect
                if e.code in (301, 302):
                    print(f"  Redirect to: {e.headers.get('Location', 'unknown')[:100]}")
            except Exception as e:
                print(f"[FAIL] URL check failed: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        test_with_token(sys.argv[1])
    else:
        print("Usage: python test_yandex_music_api.py <x_token>")
        print("\nTrying without token...")
        from yandex_music import Client
        client = Client()
        results = client.search("Marilyn Manson")
        if results and results.tracks:
            print(f"Search works without token: {len(results.tracks.results)} tracks found")
            for t in results.tracks.results[:3]:
                print(f"  - {t.title} by {[a.name for a in t.artists]} (id={t.id})")
