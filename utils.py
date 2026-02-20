# import httpx
# from typing import Dict, Optional

# # ============================================
# # DEVICE INFO PARSER
# # ============================================
# def parse_device_info(user_agent: str) -> Dict[str, str]:
#     """
#     Parse user agent into user-friendly device information.
#     Returns: device_type, device_name, browser, os
#     """
#     ua = user_agent.lower()
    
#     # Determine device type
#     if 'mobile' in ua or 'android' in ua or 'iphone' in ua:
#         device_type = "Mobile"
#     elif 'tablet' in ua or 'ipad' in ua:
#         device_type = "Tablet"
#     else:
#         device_type = "Desktop"
    
#     # Determine device name
#     device_name = "Unknown Device"
#     if 'iphone' in ua:
#         if 'iphone15' in ua or 'iphone 15' in ua:
#             device_name = "iPhone 15"
#         elif 'iphone14' in ua or 'iphone 14' in ua:
#             device_name = "iPhone 14"
#         elif 'iphone13' in ua or 'iphone 13' in ua:
#             device_name = "iPhone 13"
#         else:
#             device_name = "iPhone"
#     elif 'ipad' in ua:
#         device_name = "iPad"
#     elif 'samsung' in ua:
#         device_name = "Samsung Galaxy"
#     elif 'pixel' in ua:
#         device_name = "Google Pixel"
#     elif 'oneplus' in ua:
#         device_name = "OnePlus"
#     elif 'xiaomi' in ua or 'redmi' in ua:
#         device_name = "Xiaomi"
#     elif 'windows' in ua:
#         device_name = "Windows PC"
#     elif 'macintosh' in ua or 'mac os' in ua:
#         device_name = "Mac"
#     # elif 'linux' in ua:
#     #     device_name = "Linux PC"
#     elif 'android' in ua:
#         device_name = "Android Device"
    
#     # Determine browser
#     browser = "Unknown Browser"
#     if 'edg' in ua or 'edge' in ua:
#         browser = "Edge"
#     elif 'chrome' in ua and 'edg' not in ua:
#         browser = "Chrome"
#     elif 'safari' in ua and 'chrome' not in ua:
#         browser = "Safari"
#     elif 'firefox' in ua:
#         browser = "Firefox"
#     elif 'opera' in ua or 'opr' in ua:
#         browser = "Opera"
    
#     # Determine OS
#     os = "Unknown OS"
#     if 'windows nt 10' in ua:
#         os = "Windows 10/11"
#     elif 'windows nt 6.3' in ua:
#         os = "Windows 8.1"
#     elif 'windows nt 6.2' in ua:
#         os = "Windows 8"
#     elif 'windows nt 6.1' in ua:
#         os = "Windows 7"
#     # elif 'mac os x' in ua:
#     #     os = "iOS"
#     elif 'iphone os' in ua or 'cpu iphone' in ua:
#         # Extract iOS version
#         if 'os 17' in ua:
#             os = "iOS 17"
#         elif 'os 16' in ua:
#             os = "iOS 16"
#         elif 'os 15' in ua:
#             os = "iOS 15"
#         else:
#             os = "iOS"
#     elif 'android 14' in ua:
#         os = "Android 14"
#     elif 'android 13' in ua:
#         os = "Android 13"
#     elif 'android 12' in ua:
#         os = "Android 12"
#     elif 'android 11' in ua:
#         os = "Android 11"
#     elif 'android' in ua:
#         os = "Android"
#     # elif 'linux' in ua:
#     #     os = "Linux"
    
#     return {
#         "device_type": device_type,
#         "device_name": device_name,
#         "browser": browser,
#         "os": os
#     }


# # ============================================
# # GPS TO LOCATION (REVERSE GEOCODING)
# # ============================================
# async def get_location_from_gps(latitude: float, longitude: float) -> Dict[str, Optional[str]]:
#     """
#     Convert GPS coordinates to city/country using reverse geocoding.
#     Uses BigDataCloud API - free, no API key needed, better accuracy.
#     """
#     try:
#         async with httpx.AsyncClient(timeout=5.0) as client:
#             response = await client.get(
#                 f"https://api.bigdatacloud.net/data/reverse-geocode-client",
#                 params={
#                     "latitude": latitude,
#                     "longitude": longitude,
#                     "localityLanguage": "en"
#                 }
#             )
            
#             if response.status_code == 200:
#                 data = response.json()
                
#                 return {
#                     "country": data.get("countryName"),
#                     "city": data.get("city") or data.get("locality") or data.get("principalSubdivision"),
#                     "region": data.get("principalSubdivision")
#                 }
#     except Exception as e:
#         print(f"GPS location error: {e}")
    
#     return {"country": "Unknown", "city": "Unknown", "region": "Unknown"}


# # ============================================
# # IP TO LOCATION (FALLBACK)
# # ============================================
# async def get_location_from_ip(ip_address: str) -> Dict[str, Optional[str]]:
#     """
#     Get location data from IP address using ip-api.com (free, no key needed).
#     Returns: country, city, region
#     """
#     if not ip_address or ip_address == "127.0.0.1" or ip_address.startswith("192.168"):
#         return {
#             "country": "Local",
#             "city": "Localhost",
#             "region": "Local Network"
#         }
    
#     try:
#         async with httpx.AsyncClient(timeout=3.0) as client:
#             response = await client.get(f"http://ip-api.com/json/{ip_address}")
            
#             if response.status_code == 200:
#                 data = response.json()
                
#                 if data.get("status") == "success":
#                     return {
#                         "country": data.get("country"),
#                         "city": data.get("city"),
#                         "region": data.get("regionName")
#                     }
#     except Exception as e:
#         print(f"Error getting location: {e}")
    
#     return {
#         "country": "Unknown",
#         "city": "Unknown",
#         "region": "Unknown"
#     }


from typing import Dict

# ============================================
# DEVICE INFO PARSER
# ============================================
def parse_device_info(user_agent: str) -> Dict[str, str]:
    """
    Parse user agent into user-friendly device information.
    Returns: device_type, device_name, browser, os
    """
    ua = user_agent.lower()
    
    # Determine device type
    if 'mobile' in ua or 'android' in ua or 'iphone' in ua:
        device_type = "Mobile"
    elif 'tablet' in ua or 'ipad' in ua:
        device_type = "Tablet"
    else:
        device_type = "Desktop"
    
    # Determine device name
    device_name = "Unknown Device"
    if 'iphone' in ua:
        if 'iphone15' in ua or 'iphone 15' in ua:
            device_name = "iPhone 15"
        elif 'iphone14' in ua or 'iphone 14' in ua:
            device_name = "iPhone 14"
        elif 'iphone13' in ua or 'iphone 13' in ua:
            device_name = "iPhone 13"
        else:
            device_name = "iPhone"
    elif 'ipad' in ua:
        device_name = "iPad"
    elif 'samsung' in ua:
        device_name = "Samsung Galaxy"
    elif 'pixel' in ua:
        device_name = "Google Pixel"
    elif 'oneplus' in ua:
        device_name = "OnePlus"
    elif 'xiaomi' in ua or 'redmi' in ua:
        device_name = "Xiaomi"
    elif 'windows' in ua:
        device_name = "Windows PC"
    elif 'macintosh' in ua or 'mac os' in ua:
        device_name = "Mac"
    # elif 'linux' in ua:
    #     device_name = "Linux PC"
    elif 'android' in ua:
        device_name = "Android Device"
    
    # Determine browser
    browser = "Unknown Browser"
    if 'edg' in ua or 'edge' in ua:
        browser = "Edge"
    elif 'chrome' in ua and 'edg' not in ua:
        browser = "Chrome"
    elif 'safari' in ua and 'chrome' not in ua:
        browser = "Safari"
    elif 'firefox' in ua:
        browser = "Firefox"
    elif 'opera' in ua or 'opr' in ua:
        browser = "Opera"
    
    # Determine OS
    os = "Unknown OS"
    if 'windows nt 10' in ua:
        os = "Windows 10/11"
    elif 'windows nt 6.3' in ua:
        os = "Windows 8.1"
    elif 'windows nt 6.2' in ua:
        os = "Windows 8"
    elif 'windows nt 6.1' in ua:
        os = "Windows 7"
    # elif 'mac os x' in ua:
    #     os = "iOS"
    elif 'iphone os' in ua or 'cpu iphone' in ua:
        # Extract iOS version
        if 'os 17' in ua:
            os = "iOS 17"
        elif 'os 16' in ua:
            os = "iOS 16"
        elif 'os 15' in ua:
            os = "iOS 15"
        else:
            os = "iOS"
    elif 'android 14' in ua:
        os = "Android 14"
    elif 'android 13' in ua:
        os = "Android 13"
    elif 'android 12' in ua:
        os = "Android 12"
    elif 'android 11' in ua:
        os = "Android 11"
    elif 'android' in ua:
        os = "Android"
    # elif 'linux' in ua:
    #     os = "Linux"
    
    return {
        "device_type": device_type,
        "device_name": device_name,
        "browser": browser,
        "os": os
    }