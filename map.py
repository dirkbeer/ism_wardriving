#!/usr/bin/env python3

import csv
import folium
import json
import os
import subprocess
import socket
import sys
from folium import IFrame, Popup

DATA_DIR = 'data'
BLACKLIST = ['Secplus-v1', 'DSC-Security', 'Interlogix-Security', 'Generic-Remote', 'Microchip-HCS200', 'Waveman-Switch',
    'Hyundai-VDO', 'Schrader', 'Citroen', 'Renault', 'Schrader-EG53MA4', 'Abarth-124Spider', 'Ford', 'Truck', 'Renault-0435R',
    'Schrader-SMD3MA4', 'Toyota', 'Porsche', 'Kia', 'Megacode-Remote', 'Markisol','SimpliSafe-Gen3','SimpliSafe-Sensor']

from math import radians, sin, cos, sqrt, atan2

def filter_data_by_gps_and_radius(data, excl_center_lat=None, excl_center_lon=None, excl_radius=None):
    """Filter data based on GPS coordinates and radius from a center point.
    
    Parameters:
        data (list): List of dictionaries containing sensor data.
        excl_center_lat (float): Latitude of the center point.
        excl_center_lon (float): Longitude of the center point.
        radius (float): Radius in kilometers.
        
    Returns:
        list: Filtered list of dictionaries containing sensor data.
    """
    filtered_data = []
    
    for entry in data:
        lat = entry.get('gps_latitude') or entry.get('lat')
        lon = entry.get('gps_longitude') or entry.get('lon')
        
        if lat is None or lon is None:
            continue  # Skip entries without GPS coordinates
        
        if excl_center_lat is not None and excl_center_lon is not None and excl_radius is not None:
            # Calculate distance using Haversine formula
            R = 6371.0  # Radius of Earth in kilometers
            dlat = radians(float(lat) - excl_center_lat)
            dlon = radians(float(lon) - excl_center_lon)
            a = sin(dlat / 2)**2 + cos(radians(excl_center_lat)) * cos(radians(float(lat))) * sin(dlon / 2)**2
            c = 2 * atan2(sqrt(a), sqrt(1 - a))
            distance = R * c
            
            if distance < excl_radius:
                continue  # Skip entries inside the specified radius
        
        filtered_data.append(entry)
    
    return filtered_data

def human_readable_size(size, decimal_places=2):
    """Convert bytes to human-readable file sizes."""
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{size:.{decimal_places}f} {unit}"
        size /= 1024.0

def get_json_files():
    """Retrieve all .json files in the data directory and sort them by file age."""
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.json')]
    files.sort(key=lambda x: os.path.getmtime(os.path.join(DATA_DIR, x)))
    return files

def display_files(files):
    """Display files with their sizes."""
    for idx, file in enumerate(files, 1):
        file_path = os.path.join(DATA_DIR, file)
        file_size = human_readable_size(os.path.getsize(file_path))
        print(f"{idx}. {file} ({file_size})")

def get_user_choice(files):
    """Prompt the user to choose a file."""
    choice = int(input("\nEnter the number of the file you want to choose: "))
    if 1 <= choice <= len(files):
        return os.path.join(DATA_DIR, files[choice - 1])
    raise ValueError("Invalid choice.")

def analyze_rtl(filename, excl_center_lat=None, excl_center_lon=None, excl_radius=None):
    """Analyze the chosen JSON file and save the results as a CSV."""
    if os.path.getsize(filename) == 0:
        print(f"The file '{filename}' is empty. Exiting ...")
        sys.exit(0)

    base_filename = os.path.splitext(filename)[0]

    sensor_counts, all_keys = {}, set()
    data = []

    with open(filename, 'r') as jsonfile:
        for line in jsonfile:
            try:
                entry = json.loads(line)
                all_keys.update(entry.keys())
                if 'id' in entry and 'model' in entry and entry['model'] not in BLACKLIST:
                    pair = (entry['model'], entry['id'])
                    sensor_counts[pair] = sensor_counts.get(pair, 0) + 1
                data.append(entry)
            except json.JSONDecodeError:
                print(f"Skipping malformed JSON line: {line.strip()}")

    # Filter data based on GPS and radius
    data = filter_data_by_gps_and_radius(data, excl_center_lat, excl_center_lon, excl_radius)

    sorted_pairs = sorted(sensor_counts.items(), key=lambda x: x[1], reverse=True)

    model_id_counts = {}
    for (model_val, id_val), _ in sensor_counts.items():
        if model_val not in model_id_counts:
            model_id_counts[model_val] = set()
        model_id_counts[model_val].add(id_val)

    # Convert the dictionary to a list of tuples and sort by descending count
    sorted_model_id_counts = sorted(
        ((model, len(ids)) for model, ids in model_id_counts.items()),
        key=lambda x: x[1],
        reverse=True
    )

    print("\n{:<20} {:<10} {:<10}".format("model", "id", "count"))
    for (model_val, id_val), count in sorted_pairs:
        print(f"{model_val:<20} {id_val:<10} {count:<10}")
    print(f"\nTotal unique sensors: {len(sorted_pairs)}")

    # Print the new table with the count of unique IDs for each model, sorted by descending count
    print("\n{:<20} {:<10}".format("model", "unique id count"))
    for model_val, count in sorted_model_id_counts:
        print(f"{model_val:<20} {count:<10}")

    # Write the data to a CSV file
    csv_filename = base_filename + '.csv'
    sorted_keys = sorted(list(all_keys))  # Sort the keys alphabetically
    with open(csv_filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=sorted_keys)
        writer.writeheader()
        for row in data:
            writer.writerow(row)

    return data, sorted_pairs, sorted_model_id_counts

def plot_sensor_locations(filename, data, sorted_pairs, buffer=0.01):  # buffer is in degrees
    latitudes, longitudes = [], []
    m = folium.Map()

    # Create a dictionary to store the feature groups
    feature_groups = {}

    # Create a dictionary to store unique frequencies and assign colors to them
    unique_frequencies = {}
    color_list = ['red', 'blue', 'green', 'orange', 'purple', 'pink', 'yellow']
    color_idx = 0

    for entry in data:
        try:
            # Initialize variables to None
            lat, lon = None, None
            if 'gps_latitude' in entry and 'gps_longitude' in entry:
                lat = float(entry['gps_latitude'])
                lon = float(entry['gps_longitude'])
            elif 'lat' in entry and 'lon' in entry:
                lat = float(entry['lat'])
                lon = float(entry['lon'])
            else:
                raise KeyError("Either ('gps_latitude', 'gps_longitude') or ('lat', 'lon') must be present in the entry.")
            if lat == 0 or lon == 0:
                continue
            model = entry['model'] if 'model' in entry else 'Unknown'
            id = entry['id'] if 'id' in entry else '-'
            frequency = entry['frequency'] if 'frequency' in entry else 'Unknown'
            latitudes.append(lat)
            longitudes.append(lon)

            # Check if the feature group for this model-id combination already exists
            if model not in feature_groups and model not in BLACKLIST:
                feature_groups[model] = folium.FeatureGroup(name=model, show=False)
                m.add_child(feature_groups[model])

            # Check if the frequency is already in unique_frequencies, if not assign a new color
            if frequency not in unique_frequencies:
                unique_frequencies[frequency] = color_list[color_idx % len(color_list)]
                color_idx += 1

            color = unique_frequencies[frequency]

            # Add the marker to the corresponding feature group
            folium.CircleMarker(
                [lat, lon],
                radius=5,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.6,
                popup=f"Model: {model}\nID: {id}\nFrequency: {frequency}"
            ).add_to(feature_groups[model])

        except (ValueError, KeyError):
            continue

    if latitudes and longitudes:

        # Determine the bounding box of the data
        min_lat, max_lat = min(latitudes), max(latitudes)
        min_lon, max_lon = min(longitudes), max(longitudes)

        # Add a buffer to the bounding box
        min_lat -= buffer
        max_lat += buffer
        min_lon -= buffer
        max_lon += buffer

        # Adjust the viewport to the buffered bounding box
        m.fit_bounds([(min_lat, min_lon), (max_lat, max_lon)])

    # Add a layer control to toggle visibility
    m.add_child(folium.LayerControl())

    print(f"Unique frequencies and their colors: {unique_frequencies}")

    m.save(os.path.join(DATA_DIR, 'sensor_map.html'))
    
    return unique_frequencies

def add_text_to_map(html_file, text):
    text_html = f'<div style="position: fixed; top: 20px; right: 180px; width: auto; height: auto; z-index:9999; font-size:14px; background-color: white; padding: 5px;">{text}</div>'

    with open(html_file, 'r') as file:
        html_content = file.read()

    html_content = html_content.replace('</body>', text_html + '</body>')

    with open(html_file, 'w') as file:
        file.write(html_content)

def add_color_key_to_map(html_file, unique_frequencies):
    color_key_html = '<div style="position: fixed; bottom: 10px; left: 630px; width: 150px; height: auto; border:2px solid grey; z-index:9999; font-size:14px; background-color: white;">'
    color_key_html += '<p>Frequency Color Key:</p>'
    for freq, color in unique_frequencies.items():
        color_key_html += f'<p style="margin-left: 10px; color: {color};">{freq}</p>'
    color_key_html += '</div>'

    with open(html_file, 'r') as file:
        html_content = file.read()

    html_content = html_content.replace('</body>', color_key_html + '</body>')

    with open(html_file, 'w') as file:
        file.write(html_content)

def add_table_to_map(html_file, sorted_pairs, sorted_model_id_counts):

    # Create HTML table
    html_table = '<div style="position: fixed; bottom: 10px; left: 10px; width: 300px; height: 800px; border:2px solid grey; z-index:9999; font-size:14px; background-color: white; overflow: auto;">'
    html_table += '<table style="width:100%"><tr><th>model</th><th>id</th><th>count</th></tr>'
    for (model_val, id_val), count in sorted_pairs:
        html_table += f"<tr><td>{model_val}</td><td>{id_val}</td><td>{count}</td></tr>"
    html_table += f"</table><p>Total unique sensors: {len(sorted_pairs)}</p></div>"

    # table code for unique ID counts
    html_table += '<div style="position: fixed; bottom: 10px; left: 320px; width: 300px; height: 400px; border:2px solid grey; z-index:9999; font-size:14px; background-color: white; overflow: auto;">'
    html_table += '<table style="width:100%"><tr><th>model</th><th>unique id count</th></tr>'
    for model_val, count in sorted_model_id_counts:
        html_table += f"<tr><td>{model_val}</td><td>{count}</td></tr>"
    html_table += "</table></div>"

    # Read the existing HTML content
    with open(html_file, 'r') as file:
        html_content = file.read()

    # Insert the table HTML before the closing body tag
    html_content = html_content.replace('</body>', html_table + '</body>')

    # Write the modified HTML content back to the file
    with open(html_file, 'w') as file:
        file.write(html_content)

def get_ip_address():
    """Retrieve the IP address of the machine."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(('10.254.254.254', 1))
            return s.getsockname()[0]
        except Exception:
            return '127.0.0.1'

def serve_map():
    """Serve the map using a simple HTTP server."""
    with subprocess.Popen(['python3', '-m', 'http.server', '8000']) as server_process:
        ip_address = get_ip_address()
        print(f"\nServer started. Access the map at: http://{ip_address}:8000/{DATA_DIR}/sensor_map.html")
        print("Press Enter to stop the server and exit the script...")
        input()
        server_process.terminate()
        print("Server stopped. Exiting...")

if __name__ == "__main__":
    os.system(f'rm {DATA_DIR}/combined.json')
    os.system(f'cat {DATA_DIR}/*.json > {DATA_DIR}/combined.json')
    os.system('find ' + DATA_DIR + ' -type f -size 0 -exec rm -f {} \\;')
    files = get_json_files()
    if not files:
        raise ValueError("No .json files found in the data directory.")
    display_files(files)
    chosen_file = get_user_choice(files)
    data, sorted_pairs, sorted_model_id_counts = analyze_rtl(chosen_file, excl_center_lat=32.7298145, excl_center_lon=-116.9937531, excl_radius=0.5)
    unique_frequencies = plot_sensor_locations(chosen_file, data, sorted_pairs)  

    html_file = os.path.join(DATA_DIR, 'sensor_map.html')
    add_table_to_map(html_file, sorted_pairs, sorted_model_id_counts)
    add_color_key_to_map(html_file, unique_frequencies)
    add_text_to_map(html_file, "Select sensors for display here -->")

    print("Map saved in the 'data' subdirectory as sensor_map.html")
    serve_map()
