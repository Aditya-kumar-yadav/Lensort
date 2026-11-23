"""
Offline Reverse Geocoding Module.
Provides 100% offline reverse-geocoding without API keys, external servers, or rate limits.
Uses a curated dataset of global cities, tourist destinations, and major hubs.
"""

import math
from typing import Optional, Tuple, NamedTuple

class GeoLocation(NamedTuple):
    city: str
    country: str
    region: str = ""

# Curated dataset: (lat, lon, city, country, region)
# Focused on global tourist spots, capitals, major Indian cities & hill stations.
OFFLINE_CITIES = [
    # India - Top Metros & Capitals
    (28.6139, 77.2090, "Delhi", "India", "North"),
    (28.7041, 77.1025, "Delhi", "India", "North"),
    (19.0760, 72.8777, "Mumbai", "India", "West"),
    (12.9716, 77.5946, "Bengaluru", "India", "South"),
    (17.3850, 78.4867, "Hyderabad", "India", "South"),
    (13.0827, 80.2707, "Chennai", "India", "South"),
    (22.5726, 88.3639, "Kolkata", "India", "East"),
    (23.0225, 72.5714, "Ahmedabad", "India", "West"),
    (18.5204, 73.8567, "Pune", "India", "West"),
    (26.9124, 75.7873, "Jaipur", "India", "Rajasthan"),
    (26.8467, 80.9462, "Lucknow", "India", "Uttar Pradesh"),
    (30.7333, 76.7794, "Chandigarh", "India", "North"),
    (25.5941, 85.1376, "Patna", "India", "Bihar"),
    (21.1702, 72.8311, "Surat", "India", "Gujarat"),

    # India - Popular Tourist & Vacation Hotspots
    (15.2993, 74.1240, "Goa", "India", "Goa"),
    (15.4989, 73.8278, "Panaji", "India", "Goa"),
    (15.5527, 73.7517, "Calangute", "India", "Goa"),
    (32.2432, 77.1892, "Manali", "India", "Himachal"),
    (31.1048, 77.1734, "Shimla", "India", "Himachal"),
    (32.2190, 76.3234, "Dharamshala", "India", "Himachal"),
    (34.0837, 74.7973, "Srinagar", "India", "Kashmir"),
    (34.1526, 77.5771, "Leh Ladakh", "India", "Ladakh"),
    (30.0869, 78.2676, "Rishikesh", "India", "Uttarakhand"),
    (29.9457, 78.1642, "Haridwar", "India", "Uttarakhand"),
    (30.4598, 78.0644, "Mussoorie", "India", "Uttarakhand"),
    (29.3919, 79.4542, "Nainital", "India", "Uttarakhand"),
    (27.1767, 78.0081, "Agra", "India", "Uttar Pradesh"),
    (25.3176, 82.9739, "Varanasi", "India", "Uttar Pradesh"),
    (24.5854, 73.7125, "Udaipur", "India", "Rajasthan"),
    (26.2389, 73.0243, "Jodhpur", "India", "Rajasthan"),
    (26.9157, 70.9083, "Jaisalmer", "India", "Rajasthan"),
    (9.9312, 76.2673, "Kochi", "India", "Kerala"),
    (10.0889, 77.0595, "Munnar", "India", "Kerala"),
    (9.4981, 76.3388, "Alleppey", "India", "Kerala"),
    (11.4102, 76.6950, "Ooty", "India", "Tamil Nadu"),
    (10.2381, 77.4892, "Kodaikanal", "India", "Tamil Nadu"),
    (27.0410, 88.2663, "Darjeeling", "India", "West Bengal"),
    (27.3389, 88.6065, "Gangtok", "India", "Sikkim"),
    (11.9416, 79.8083, "Puducherry", "India", "Puducherry"),
    (12.3051, 76.6552, "Mysuru", "India", "Karnataka"),
    (12.4244, 75.7382, "Coorg", "India", "Karnataka"),

    # Asia & Middle East
    (25.2048, 55.2708, "Dubai", "UAE", "Middle East"),
    (24.4539, 54.3773, "Abu Dhabi", "UAE", "Middle East"),
    (1.3521, 103.8198, "Singapore", "Singapore", "SE Asia"),
    (13.7563, 100.5018, "Bangkok", "Thailand", "SE Asia"),
    (7.8804, 98.3923, "Phuket", "Thailand", "SE Asia"),
    (-8.4095, 115.1889, "Bali", "Indonesia", "SE Asia"),
    (3.1390, 101.6869, "Kuala Lumpur", "Malaysia", "SE Asia"),
    (35.6762, 139.6503, "Tokyo", "Japan", "East Asia"),
    (35.0116, 135.7681, "Kyoto", "Japan", "East Asia"),
    (37.5665, 126.9780, "Seoul", "South Korea", "East Asia"),
    (22.3193, 114.1694, "Hong Kong", "Hong Kong", "East Asia"),
    (39.9042, 116.4074, "Beijing", "China", "East Asia"),
    (31.2304, 121.4737, "Shanghai", "China", "East Asia"),
    (27.7172, 85.3240, "Kathmandu", "Nepal", "South Asia"),
    (6.9271, 79.8612, "Colombo", "Sri Lanka", "South Asia"),
    (4.1755, 73.5093, "Maldives", "Maldives", "South Asia"),

    # Europe
    (48.8566, 2.3522, "Paris", "France", "Europe"),
    (43.7102, 7.2620, "Nice", "France", "Europe"),
    (51.5074, -0.1278, "London", "UK", "Europe"),
    (41.9028, 12.4964, "Rome", "Italy", "Europe"),
    (45.4408, 12.3155, "Venice", "Italy", "Europe"),
    (43.7696, 11.2558, "Florence", "Italy", "Europe"),
    (41.3879, 2.1686, "Barcelona", "Spain", "Europe"),
    (40.4168, -3.7038, "Madrid", "Spain", "Europe"),
    (47.3769, 8.5417, "Zurich", "Switzerland", "Europe"),
    (46.2044, 6.1432, "Geneva", "Switzerland", "Europe"),
    (46.6863, 7.8632, "Interlaken", "Switzerland", "Europe"),
    (48.2082, 16.3738, "Vienna", "Austria", "Europe"),
    (52.5200, 13.4050, "Berlin", "Germany", "Europe"),
    (48.1351, 11.5820, "Munich", "Germany", "Europe"),
    (52.3676, 4.9041, "Amsterdam", "Netherlands", "Europe"),
    (37.9838, 23.7275, "Athens", "Greece", "Europe"),
    (36.3932, 25.4615, "Santorini", "Greece", "Europe"),
    (41.0082, 28.9784, "Istanbul", "Turkey", "Europe/Asia"),
    (50.0755, 14.4378, "Prague", "Czech Republic", "Europe"),

    # Americas & Oceania
    (40.7128, -74.0060, "New York", "USA", "North America"),
    (34.0522, -118.2437, "Los Angeles", "USA", "North America"),
    (37.7749, -122.4194, "San Francisco", "USA", "North America"),
    (36.1699, -115.1398, "Las Vegas", "USA", "North America"),
    (25.7617, -80.1918, "Miami", "USA", "North America"),
    (43.6532, -79.3832, "Toronto", "Canada", "North America"),
    (49.2827, -123.1207, "Vancouver", "Canada", "North America"),
    (-33.8688, 151.2093, "Sydney", "Australia", "Oceania"),
    (-37.8136, 144.9631, "Melbourne", "Australia", "Oceania"),
    (-36.8485, 174.7633, "Auckland", "New Zealand", "Oceania"),
]

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in kilometers."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def reverse_geocode(lat: float, lon: float, max_distance_km: float = 120.0) -> Optional[GeoLocation]:
    """
    Offline reverse geocode (lat, lon) to nearest city.
    If closer than max_distance_km, returns GeoLocation(city, country, region).
    Otherwise returns None or broad region.
    """
    if lat is None or lon is None:
        return None

    best_match = None
    min_dist = float("inf")

    for clat, clon, city, country, region in OFFLINE_CITIES:
        dist = haversine_distance(lat, lon, clat, clon)
        if dist < min_dist:
            min_dist = dist
            best_match = GeoLocation(city=city, country=country, region=region)

    # If within reasonable radius (e.g. 100-150 km)
    if min_dist <= max_distance_km:
        return best_match
    
    # If a bit further out, still return closest city if under 300km
    if min_dist <= 300.0 and best_match:
        return best_match

    return None
