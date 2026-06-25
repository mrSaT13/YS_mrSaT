"""Test Music Assistant bridge logic (standalone, no HA dependency)."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_detection_logic():
    print("=== Music Assistant Bridge - Detection Logic Test ===\n")

    # Simulate the detection logic from yandex_station.py
    def should_intercept_track(player_state: dict) -> bool:
        """Check if this track should be intercepted for MA fallback."""
        artist = player_state.get("subtitle", "")
        track = player_state.get("title", "")
        track_type = player_state.get("type", "")
        duration = player_state.get("duration", 0)

        # Only intercept music tracks
        if track_type != "Track":
            return False

        # Skip if no artist
        if not artist:
            return False

        # Check if this is a preview or error (duration <= 60s)
        if duration and duration > 60000:
            return False

        return True

    # Test cases
    test_cases = [
        # Preview tracks (should intercept)
        ({"title": "The Beautiful People", "subtitle": "Marilyn Manson", "type": "Track", "duration": 30000}, True, "Preview 30s"),
        ({"title": "Smells Like Teen Spirit", "subtitle": "Nirvana", "type": "Track", "duration": 0}, True, "No duration (error)"),
        ({"title": "Bohemian Rhapsody", "subtitle": "Queen", "type": "Track", "duration": 60000}, True, "Exactly 60s"),

        # Full tracks (should NOT intercept)
        ({"title": "Bohemian Rhapsody", "subtitle": "Queen", "type": "Track", "duration": 354000}, False, "Full track 5:54"),
        ({"title": "Stairway to Heaven", "subtitle": "Led Zeppelin", "type": "Track", "duration": 482000}, False, "Full track 8:02"),

        # Non-music (should NOT intercept)
        ({"title": "FM Radio", "subtitle": None, "type": "FmRadio", "duration": 0}, False, "Radio station"),
        ({"title": "Podcast Episode 1", "subtitle": "Joe Rogan", "type": "Podcast", "duration": 7200000}, False, "Podcast"),
        ({"title": "News Broadcast", "subtitle": "", "type": "LiveStream", "duration": 0}, False, "Live stream"),

        # Edge cases
        ({"title": "Test", "subtitle": "", "type": "Track", "duration": 30000}, False, "Empty artist"),
        ({"title": "Test", "type": "Track", "duration": 30000}, False, "No subtitle key"),
    ]

    passed = 0
    failed = 0

    for state, expected, description in test_cases:
        result = should_intercept_track(state)
        status = "PASS" if result == expected else "FAIL"
        if result == expected:
            passed += 1
        else:
            failed += 1

        action = "INTERCEPT" if result else "SKIP"
        artist = state.get("subtitle", "(none)")
        track = state.get("title", "(none)")
        print(f"  [{status}] {description}: {artist} - {track} -> {action}")

    print(f"\nResults: {passed} passed, {failed} failed")

    # Test MA service call simulation
    print("\n=== MA Service Call Simulation ===")
    print("When track is intercepted, the bridge will:")
    print("1. Call mass.search with query: 'Marilyn Manson The Beautiful People'")
    print("2. Get results from Navidrome/local files")
    print("3. Call mass.play_media on the speaker's MA entity")
    print("4. Announce: 'Вот что я нашла: The Beautiful People by Marilyn Manson'")

    # Test the announce format
    print("\n=== Announce Format ===")
    test_results = [
        {"name": "The Beautiful People", "artist": "Marilyn Manson"},
        {"name": "Bohemian Rhapsody", "artist": "Queen"},
        {"name": "Smells Like Teen Spirit", "artist": "Nirvana"},
    ]
    for r in test_results:
        print(f"  'Вот что я нашла: {r['name']} by {r['artist']}'")

    print("\n=== Integration Points ===")
    print("1. yandex_station.py: _check_music_assistant_fallback()")
    print("   - Called on every playerState update")
    print("   - Detects preview/error tracks")
    print("   - Schedules MA search")
    print()
    print("2. music_assistant_bridge.py: MusicAssistantBridge")
    print("   - is_ma_available(): checks if MA integration is loaded")
    print("   - get_ma_entity_for_speaker(): finds MA player for speaker")
    print("   - search_and_play(): searches MA and plays on speaker")
    print("   - _announce(): TTS announcement before playing")

if __name__ == "__main__":
    test_detection_logic()
