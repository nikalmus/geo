import os
from urllib.parse import urlencode
import googlemaps
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ['API_KEY']

gmaps = googlemaps.Client(key=api_key)

def get_coordinates_from_address(address):
    geocode_result = gmaps.geocode(address)
    if geocode_result:
        location = geocode_result[0]['geometry']['location']
        return location['lat'], location['lng']
    else:
        return None


def get_static_map_url(waypoints):
    if not waypoints:
        return None

    markers = []
    for i, waypoint in enumerate(waypoints):
        if i == 0:
            # Use a different color (blue) and label (S) for the starting point
            markers.append(f'markers=color:blue|label:S|{waypoint["lat"]},{waypoint["lng"]}')
        else:
            markers.append(f'markers=color:red|label:{i}|{waypoint["lat"]},{waypoint["lng"]}')

    markers_str = '&'.join(markers)

    # Fetch the directions for the entire route
    start = f'{waypoints[0]["lat"]},{waypoints[0]["lng"]}'
    end = f'{waypoints[-1]["lat"]},{waypoints[-1]["lng"]}'
    directions_result = gmaps.directions(start, end, mode='driving', waypoints=[f'{waypoint["lat"]},{waypoint["lng"]}' for waypoint in waypoints[1:-1]])

    # Extract the detailed polylines from each leg and combine them
    polylines = []
    for leg in directions_result[0]['legs']:
        if 'steps' in leg:
            for step in leg['steps']:
                if 'polyline' in step:
                    points = googlemaps.convert.decode_polyline(step['polyline']['points'])
                    polylines.extend(points)

    # Limit the number of points in the path to keep it within the API limit
    max_points = 50
    step = max(len(polylines) // max_points, 1)
    reduced_polylines = polylines[::step]

    # Construct the path for the entire route using the reduced polylines
    path_points = '|'.join([f'{point["lat"]},{point["lng"]}' for point in reduced_polylines])

    path = f'path=color:blue|weight:3|{path_points}'

    params = {
        'size': '800x600',
        'maptype': 'roadmap',
        'key': api_key,
        'format': 'png',
        'visual_refresh': 'true',
    }

    url = f'https://maps.googleapis.com/maps/api/staticmap?{urlencode(params)}&{markers_str}&{path}'
    return url