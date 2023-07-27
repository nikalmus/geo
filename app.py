import os
from dotenv import load_dotenv
from flask import Flask, render_template, request
import googlemaps

import itertools
from urllib.parse import urlencode

load_dotenv()
api_key = os.environ['API_KEY']

app = Flask(__name__)

gmaps = googlemaps.Client(key=api_key)


hardware_stores = [
    "13650 Orchard Pkwy, Westminster, CO 80023, USA", 
    "5600 West 88TH Ave Westminster, CO 80031, USA",
    "2910 Arapahoe Rd, Erie, CO 80026, USA",
    "12171 Sheridan Blvd, Broomfield, CO 80020, USA",
    "7125 W 88th Ave, Westminster, CO 80021, USA"
]

M2MI = 0.000621371 # multiply value by M2MI to convert meters (default unit returned by the Google Maps Directions API) to miles


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        starting_address = request.form['address']
        route_waypoints, route_total_distance, static_map_url = get_shortest_route(starting_address)
        return render_template('index.html', route_waypoints=route_waypoints, route_total_distance=route_total_distance, static_map_url=static_map_url)

    return render_template('index.html', route_waypoints=None, route_total_distance=None, static_map_url=None)


def get_coordinates_from_address(address):
    geocode_result = gmaps.geocode(address)
    if geocode_result:
        location = geocode_result[0]['geometry']['location']
        return location['lat'], location['lng']
    else:
        return None

def get_consecutive_route(starting_address):
    hardware_stores_coordinates = [get_coordinates_from_address(address) for address in hardware_stores]
    starting_coordinates = get_coordinates_from_address(starting_address)
    route_waypoints = []
    total_distance = 0.0
    for dest_coords in hardware_stores_coordinates:
        directions_result = gmaps.directions(starting_coordinates, dest_coords, mode='driving')
        if not directions_result:
            print(f"No route found from starting address to {dest_coords}.")
            continue

        if 'legs' in directions_result[0]:
            for leg in directions_result[0]['legs']:
                end_location = leg['end_location']
                end_address = leg['end_address']
                distance = leg['distance']['text']
                total_distance += float(leg['distance']['value'])
                route_waypoints.append({'lat': end_location['lat'], 
                                        'lng': end_location['lng'], 
                                        'address': end_address,
                                        'distance': distance })

        starting_coordinates = dest_coords

    return route_waypoints, round(total_distance * M2MI, 2)

def get_static_map_url_straight_directins(waypoints, api_key):
    if not waypoints:
        return None

    markers = '&'.join([f'markers=color:red%7C{waypoint["lat"]},{waypoint["lng"]}' for waypoint in waypoints])
    path_points = '|'.join([f'{waypoint["lat"]},{waypoint["lng"]}' for waypoint in waypoints])
    path = f'path=color:blue|weight:3|{path_points}'
    params = {
        'size': '800x600',
        'maptype': 'roadmap',
        'key': api_key,
        'format': 'png',
        'visual_refresh': 'true',
    }
    url = f'https://maps.googleapis.com/maps/api/staticmap?{urlencode(params)}&{markers}&{path}'
    return url

def get_static_map_url(waypoints, api_key):
    if not waypoints:
        return None

    markers = '&'.join([f'markers=color:red%7C{waypoint["lat"]},{waypoint["lng"]}' for waypoint in waypoints])

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

    url = f'https://maps.googleapis.com/maps/api/staticmap?{urlencode(params)}&{markers}&{path}'
    return url


def get_shortest_route(starting_address):
    """
    Brute force to find shortest route.
    Each element in the permutation represents a different order in which the destination coordinates can be visited. 
    E.g., if there are 5 destinations with coordinates [A, B, C, D, E], one of the permutations might be (B, A, C, E, D), 
    which means the route would start at B, then go to A, then C, and so on.
    """
    hardware_stores_coordinates = [get_coordinates_from_address(address) for address in hardware_stores]
    starting_coordinates = get_coordinates_from_address(starting_address)
    min_distance = float('inf')
    optimal_route = []

    # Generate all possible permutations of the waypoints (excluding starting point)
    for perm in itertools.permutations(hardware_stores_coordinates):
        total_distance = 0.0
        current_coordinates = starting_coordinates

        for dest_coords in perm:
            directions_result = gmaps.directions(current_coordinates, dest_coords, mode='driving')

            if not directions_result:
                print(f"No route found from starting address to {dest_coords}.")
                break

            if 'legs' in directions_result[0]:
                for leg in directions_result[0]['legs']:
                    total_distance += float(leg['distance']['value'])
                    current_coordinates = dest_coords

        # Calculate the distance to return back to the starting point
        directions_result = gmaps.directions(current_coordinates, starting_coordinates, mode='driving')
        if directions_result and 'legs' in directions_result[0]:
            for leg in directions_result[0]['legs']:
                total_distance += float(leg['distance']['value'])

        if total_distance < min_distance:
            min_distance = total_distance
            optimal_route = list(perm)

    # Format the result to match the original structure
    
    route_waypoints = []
    for dest_coords in optimal_route:
        address = gmaps.reverse_geocode(dest_coords)[0]['formatted_address']
        distance = gmaps.distance_matrix(starting_address, address, mode='driving')['rows'][0]['elements'][0]['distance']['text']
        route_waypoints.append({'lat': dest_coords[0], 'lng': dest_coords[1], 'address': address, 'distance': distance})

    route_waypoints.append({'lat': starting_coordinates[0], 'lng': starting_coordinates[1], 'address': starting_address, 'distance': '0 mi'})


    # Get the static map URL
    static_map_url = get_static_map_url(route_waypoints, api_key)

    return route_waypoints, round(min_distance * M2MI, 2), static_map_url


if __name__ == '__main__':
    app.run(debug=True)