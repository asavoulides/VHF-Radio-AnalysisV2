import googlemaps
from datetime import datetime
from dotenv import load_dotenv
import os

# Load API key from .env file
load_dotenv()
Google_API_KEY = os.getenv("Google_API_KEY")

# Initialize client
gmaps = googlemaps.Client(key=Google_API_KEY)

# Geocode an address
address = "Newton, MA"
geocode_result = gmaps.geocode(address)

if geocode_result:
    result = geocode_result[0]  # Take the first match

    # Extract formatted address
    formatted_address = result.get("formatted_address")

    # Extract place_id
    place_id = result.get("place_id")

    # Build Google Maps URL
    maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"

    print("Full Address:", formatted_address)
    print("Google Maps URL:", maps_url)
else:
    print("No results found.")
