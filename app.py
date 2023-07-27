import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, session, jsonify, redirect, url_for
import googlemaps

import itertools
from urllib.parse import urlencode

load_dotenv()
api_key = os.environ['API_KEY']

app = Flask(__name__)
app.secret_key = os.environ['SECRET_KEY']

gmaps = googlemaps.Client(key=api_key)



M2MI = 0.000621371  # multiply value by M2MI to convert meters (default unit returned by the Google Maps Directions API) to miles


@app.route('/reset', methods=['POST'])
def reset_data():
    session.pop('route_waypoints', None)
    session.pop('static_map_url', None)
    return jsonify(success=True)


# @app.route('/', methods=['GET', 'POST'])
# def index():
#     if request.method == 'POST':
#         starting_address = request.form.get('starting_address', '')  # Use get() with a default value
#         waypoints = [request.form.get(f'waypoint{i}', '') for i in range(1, 5)]  # Use get() with a default value
#         route_waypoints, route_total_distance, static_map_url = get_shortest_route(starting_address, waypoints)
#         return render_template('index.html', route_waypoints=route_waypoints, route_total_distance=route_total_distance, static_map_url=static_map_url)

#     return render_template('index.html', route_waypoints=None, route_total_distance=None, static_map_url=None)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        starting_address = request.form.get('starting_address', '')
        # waypoint1 = request.form.get('waypoint1', '')
        # waypoint2 = request.form.get('waypoint2', '')
        # waypoint3 = request.form.get('waypoint3', '')
        # waypoint4 = request.form.get('waypoint4', '')
        # waypoints = [waypoint1, waypoint2, waypoint3, waypoint4]
        waypoints = [request.form.get(f'waypoint{i}', '') for i in range(1, 5)]  # Use get() with a default value
        route_waypoints, route_total_distance, static_map_url = get_shortest_route(starting_address, waypoints)

        # Save the data in session so that it can be accessed in the results page
        session['route_waypoints'] = route_waypoints
        session['route_total_distance'] = route_total_distance
        session['static_map_url'] = static_map_url

        # Redirect to the results page
        return redirect(url_for('results'))

    return render_template('index.html')

@app.route('/results')
def results():
    # Retrieve the data from session
    route_waypoints = session.get('route_waypoints', None)
    route_total_distance = session.get('route_total_distance', None)
    static_map_url = session.get('static_map_url', None)

    # Check if the data exists in session
    if route_waypoints is None or route_total_distance is None or static_map_url is None:
        return redirect(url_for('index'))  # Redirect back to the index page if data is not available

    # Clear the session data after displaying it on the results page
    session.pop('route_waypoints', None)
    session.pop('route_total_distance', None)
    session.pop('static_map_url', None)

    # Render the results page with the data and map
    return render_template('result.html', route_waypoints=route_waypoints, route_total_distance=route_total_distance, static_map_url=static_map_url)


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


def get_shortest_route(starting_address, waypoints):
    """
    Brute force to find the shortest route.

    Parameters:
        starting_address (str): The starting address entered by the user.
        waypoints (list of str): The list of waypoints (addresses) entered by the user.

    Returns:
        tuple: A tuple containing:
            - route_waypoints (list of dict): List of waypoints in the optimized route, including their coordinates,
                                              addresses, and distances.
            - route_total_distance (float): The total distance of the optimized route in miles.
            - static_map_url (str): The URL of the static map displaying the optimized route.
    """

    
    stop_coordinates = []
    for wpt in waypoints:
        if wpt:
            coordinates = get_coordinates_from_address(wpt)
            if coordinates is not None:
                stop_coordinates.append(coordinates)

    if len(stop_coordinates) < 2:
        return [], 0.0, None  # Return empty route and map URL if there are fewer than two waypoints
    
    starting_coordinates = get_coordinates_from_address(starting_address)
    min_distance = float('inf')
    optimal_route = []

    # Generate all possible permutations of the waypoints (excluding starting point)
    for perm in itertools.permutations(stop_coordinates):
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
    static_map_url = get_static_map_url(route_waypoints)

    return route_waypoints, round(min_distance * M2MI, 2), static_map_url



if __name__ == '__main__':
    app.run(debug=True)
