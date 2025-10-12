"""
Test why "188 Florence Street" geocoding is failing
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import location_services

# Test the exact address that's failing
test_address = "188 Florence Street"

print("=" * 80)
print(f"Testing Geocoding: {test_address}")
print("=" * 80)

print(f"\n1. Testing geocode_newton() directly...")
result = location_services.geocode_newton(test_address)

if result:
    lat, lng, formatted_addr, url = result
    print(f"   ✅ SUCCESS!")
    print(f"   - Latitude: {lat}")
    print(f"   - Longitude: {lng}")
    print(f"   - Formatted Address: {formatted_addr}")
    print(f"   - Maps URL: {url}")
else:
    print(f"   ❌ FAILED - geocode_newton returned None")

    # Debug: Try without the strict Newton filtering
    print(f"\n2. Testing Google Maps API directly (without Newton filtering)...")
    import googlemaps
    import os
    from dotenv import load_dotenv

    load_dotenv()
    gmaps = googlemaps.Client(key=os.getenv("Google_API_KEY"))

    # Try without components filtering
    print(f"   Query: '{test_address}, Newton, MA'")
    raw_result = gmaps.geocode(f"{test_address}, Newton, MA")

    if raw_result:
        print(f"   ✅ Google returned {len(raw_result)} result(s)")
        for i, r in enumerate(raw_result[:3], 1):  # Show first 3
            loc = r["geometry"]["location"]
            fa = r["formatted_address"]
            print(f"\n   Result {i}:")
            print(f"     - Address: {fa}")
            print(f"     - Coords: ({loc['lat']}, {loc['lng']})")
            print(f"     - Types: {r.get('types', [])}")

            # Check if in Newton bounds
            bounds = {
                "southwest": {"lat": 42.2869, "lng": -71.2687},
                "northeast": {"lat": 42.3688, "lng": -71.1575},
            }
            in_bounds = (
                bounds["southwest"]["lat"] <= loc["lat"] <= bounds["northeast"]["lat"]
                and bounds["southwest"]["lng"]
                <= loc["lng"]
                <= bounds["northeast"]["lng"]
            )
            print(f"     - In Newton bounds: {in_bounds}")
            print(f"     - Has 'Newton' in address: {'Newton' in fa}")
    else:
        print(f"   ❌ Google returned no results")

    # Try with just "Florence Street, Newton, MA"
    print(f"\n3. Testing without house number: 'Florence Street, Newton, MA'")
    raw_result2 = gmaps.geocode("Florence Street, Newton, MA")
    if raw_result2:
        print(f"   ✅ Google returned {len(raw_result2)} result(s)")
        r = raw_result2[0]
        print(f"     - Address: {r['formatted_address']}")
        print(
            f"     - Coords: ({r['geometry']['location']['lat']}, {r['geometry']['location']['lng']})"
        )
    else:
        print(f"   ❌ Google returned no results")

print("\n" + "=" * 80)
