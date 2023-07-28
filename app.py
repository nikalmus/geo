import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, session, redirect, url_for
from helpers import gmaps, get_static_map_url

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ['SECRET_KEY']

M2MI = 0.000621371  # multiply value by M2MI to convert meters (default unit returned by the Google Maps Directions API) to miles

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        starting_address = request.form.get('starting_address', '')
        waypoints = [request.form.get(f'waypoint{i}', '') for i in range(1, 8)]  # Use get() with a default value
        route_waypoints, route_total_distance, static_map_url = get_shortest_route(starting_address, waypoints)

        # Save the data in session so that it can be accessed in the results page
        session['route_waypoints'] = route_waypoints
        session['route_total_distance'] = route_total_distance
        session['static_map_url'] = static_map_url

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

    return render_template('result.html', route_waypoints=route_waypoints, route_total_distance=route_total_distance, static_map_url=static_map_url)


def get_shortest_route(starting_address, waypoints):
    """
    Find the shortest route using the Google Maps Directions API.

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

    # Combine the starting address and waypoints to create the waypoints for Directions API
    all_waypoints = [starting_address] + [wpt for wpt in waypoints if wpt]

    # Request directions from Google Maps Directions API
    directions_result = gmaps.directions(
        origin=starting_address,
        destination=starting_address,
        waypoints=all_waypoints[1:],
        mode='driving',
        optimize_waypoints=True
    )

    # Extract route details from the API response
    if not directions_result:
        return [], 0.0, None

    legs = directions_result[0]['legs']
    route_waypoints = []
    total_distance = 0.0

    for i, leg in enumerate(legs):
        distance_text = leg['distance']['text']
        distance_value = leg['distance']['value']
        address = leg['start_address']
        lat = leg['start_location']['lat']
        lng = leg['start_location']['lng']

        # Exclude distance for the starting point (i == 0)
        distance = distance_text if i > 0 else None

        route_waypoints.append({'lat': lat, 'lng': lng, 'address': address, 'distance': distance})
        total_distance += distance_value



    # Format the result with the starting point at the end to form a loop
    start_coords = route_waypoints[0]['lat'], route_waypoints[0]['lng']
    start_address = route_waypoints[0]['address']
    start_distance = route_waypoints[0]['distance']
    route_waypoints.append({'lat': start_coords[0], 'lng': start_coords[1], 'address': start_address, 'distance': None})

    # Get the static map URL
    static_map_url = get_static_map_url(route_waypoints)

    # Set the distance for the last leg manually
    route_waypoints[-1]['distance'] = gmaps.distance_matrix(route_waypoints[-2]['address'], start_address, mode='driving')['rows'][0]['elements'][0]['distance']['text']

    return route_waypoints, round(total_distance * M2MI, 2), static_map_url


if __name__ == '__main__':
    app.run(debug=True)
