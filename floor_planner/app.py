from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/outdoor')
def outdoor():
    return render_template('outdoor.html')

@app.route('/test_map')
def test_map():
    return render_template('test_map.html')

@app.route('/api/route', methods=['POST'])
def get_route():
    """Get route options between two points using OSRM"""
    data = request.json
    start = data.get('start')  # {lat, lng}
    end = data.get('end')  # {lat, lng}
    
    # Use OSRM demo server for routing (for production, use self-hosted)
    url = f"http://router.project-osrm.org/route/v1/foot/{start['lng']},{start['lat']};{end['lng']},{end['lat']}"
    params = {
        'alternatives': 'true',
        'steps': 'true',
        'geometries': 'geojson',
        'overview': 'full'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/snap-to-road', methods=['POST'])
def snap_to_road():
    """Snap a point to the nearest road using OSRM"""
    data = request.json
    lat = data.get('lat')
    lng = data.get('lng')
    
    url = f"http://router.project-osrm.org/nearest/v1/foot/{lng},{lat}"
    params = {'number': 1}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        result = response.json()
        if result.get('waypoints') and len(result['waypoints']) > 0:
            waypoint = result['waypoints'][0]
            return jsonify({
                'lat': waypoint['location'][1],
                'lng': waypoint['location'][0],
                'name': waypoint.get('name', 'Unknown Road')
            })
        return jsonify({'error': 'No road found nearby'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/geocode', methods=['POST'])
def geocode():
    """Search for a location using Nominatim"""
    data = request.json
    query = data.get('query', '')
    
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'format': 'json',
        'q': query,
        'limit': 5
    }
    headers = {
        'User-Agent': 'FloorPlannerApp/1.0 (Educational Project)'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)