import os, googlemaps
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()
gmaps = googlemaps.Client(key=os.getenv("Google_API_KEY"))


def geocode_newton(address: str):
    q = f"{address}, Newton, MA"
    res = gmaps.geocode(q, components={"administrative_area": "MA", "country": "US"})
    if not res:
        return None
    r = res[0]
    loc = r["geometry"]["location"]
    fa, pid = r["formatted_address"], r.get("place_id")
    url = (
        f"https://www.google.com/maps/search/?api=1&query={quote_plus(fa)}&query_place_id={pid}"
        if pid
        else None
    )
    return loc["lat"], loc["lng"], fa, url


if __name__ == "__main__":
    lat, lng, fa, url = geocode_newton("192 evelyn rd ")
    print(lat, lng)
    print(fa)
    print(url)


