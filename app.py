import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for
import googlemaps
from pprint import pprint

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

import json

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        starting_address = request.form['address']
        route_waypoints, total_distance = get_shortest_route(starting_address)
        # Convert the list of waypoints to a JSON string
        waypoints_json = json.dumps(route_waypoints)

        # Redirect to the show_result route with the JSON string as a URL parameter
        return redirect(url_for('show_result', waypoints=waypoints_json, total_distance=total_distance))

    return render_template('index.html')

@app.route('/result', methods=['GET'])
def show_result():
    waypoints_json = request.args.get('waypoints')
    total_distance_json = request.args.get('total_distance')

    # Parse the JSON string back to a Python list
    route_waypoints = json.loads(waypoints_json)
    route_total_distance = json.loads(total_distance_json)

    return render_template('result.html', route_waypoints=route_waypoints, route_total_distance=route_total_distance)


def get_coordinates_from_address(address):
    geocode_result = gmaps.geocode(address)
    print(f"geocode_result: {geocode_result}")
    if geocode_result:
        location = geocode_result[0]['geometry']['location']
        return location['lat'], location['lng']
    else:
        return None

def get_shortest_route(starting_address):
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

if __name__ == '__main__':
    app.run(debug=True)