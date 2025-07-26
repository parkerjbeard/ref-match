import math
from typing import Tuple, Optional
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Initialize geocoder
geolocator = Nominatim(user_agent="refmatch-mvp")


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points using Haversine formula
    Returns distance in kilometers
    """
    # Earth's radius in kilometers
    R = 6371.0
    
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Differences
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    # Haversine formula
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    distance = R * c
    
    return round(distance, 2)


def get_coordinates_from_address(address: str, city: str, state: str, zip_code: str) -> Optional[Tuple[float, float]]:
    """
    Get latitude and longitude from address
    Returns (latitude, longitude) or None if not found
    """
    full_address = f"{address}, {city}, {state} {zip_code}"
    
    try:
        location = geolocator.geocode(full_address, timeout=10)
        if location:
            return location.latitude, location.longitude
        else:
            # Try with just city, state, zip
            fallback_address = f"{city}, {state} {zip_code}"
            location = geolocator.geocode(fallback_address, timeout=10)
            if location:
                return location.latitude, location.longitude
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        logger.error(f"Geocoding error for {full_address}: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error geocoding {full_address}: {str(e)}")
    
    return None


def is_within_distance(ref_lat: float, ref_lon: float, game_lat: float, game_lon: float, max_distance_km: float) -> bool:
    """Check if referee is within acceptable distance from game"""
    distance = calculate_distance(ref_lat, ref_lon, game_lat, game_lon)
    return distance <= max_distance_km