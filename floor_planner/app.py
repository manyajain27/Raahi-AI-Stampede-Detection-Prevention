from flask import Flask, render_template, request, jsonify
import requests
import os
import json
import base64
import re
from pathlib import Path

# Load API key from .env
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    for line in env_path.read_text().strip().split('\n'):
        if '=' in line and not line.startswith('#'):
            key, val = line.split('=', 1)
            os.environ[key.strip()] = val.strip()

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


@app.route('/api/save-and-visualize', methods=['POST'])
def save_and_visualize():
    """Save the floor plan YAML and return the visualizer URL."""
    data = request.json
    yaml_text = data.get('yaml', '')
    filename = data.get('filename', 'floor_plan.yaml')
    
    if not yaml_text:
        return jsonify({'error': 'No YAML data provided'}), 400
    
    # Save to project root (parent of floor_planner/)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filepath = os.path.join(project_root, filename)
    
    try:
        with open(filepath, 'w') as f:
            f.write(yaml_text)
        
        # Return the visualizer URL with the venue path
        visualizer_url = f'http://localhost:5001?venue={filepath}'
        return jsonify({
            'success': True, 
            'filepath': filepath,
            'visualizer_url': visualizer_url
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyze-image', methods=['POST'])
def analyze_image():
    """Analyze a venue image using Gemini Vision AI to extract floor plan elements."""
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return jsonify({'error': 'Gemini API key not configured'}), 500
    
    data = request.json
    image_b64 = data.get('image', '')   # base64-encoded image
    mime_type = data.get('mimeType', 'image/png')
    
    if not image_b64:
        return jsonify({'error': 'No image data provided'}), 400
    
    # Remove data URL prefix if present
    if ',' in image_b64:
        image_b64 = image_b64.split(',', 1)[1]
    
    response_text = ''
    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=api_key)
        
        prompt = """Analyze this venue/building floor plan or layout image. Your job is to identify:

1. PATHWAYS: All walkable corridors, hallways, roads, or paths that people walk through.
   - Return each pathway as a series of points tracing its center line.
   - Estimate the width in meters.
   
2. ENTRIES: Points where people enter the venue (main doors, gates, entrances).

3. EXITS: Points where people exit (exit doors, emergency exits, gates out).

4. CHOKE POINTS: Narrow bottleneck areas where crowd congestion could occur.

IMPORTANT COORDINATE RULES:
- Return ALL coordinates as PERCENTAGES (0 to 100) of the image width (x) and height (y).
- x=0 is the LEFT edge, x=100 is the RIGHT edge.
- y=0 is the TOP edge, y=100 is the BOTTOM edge.
- Be as accurate as possible with the positions.

Return ONLY valid JSON in exactly this format (no markdown, no explanation):
{
  "pathways": [
    {
      "name": "Main Corridor",
      "width": 3.0,
      "points": [{"x": 10, "y": 50}, {"x": 50, "y": 50}, {"x": 90, "y": 50}]
    }
  ],
  "entries": [
    {"name": "Main Entrance", "x": 5, "y": 50, "spawnRate": 2.0}
  ],
  "exits": [
    {"name": "Exit A", "x": 95, "y": 50, "exitRate": 3.0}
  ],
  "chokePoints": [
    {"name": "Narrow Hall", "x": 40, "y": 30}
  ]
}

Rules:
- Identify at least 1 pathway, 1 entry, and 1 exit if possible.
- For entries, estimate a reasonable spawnRate (people per second, typically 1-5).
- For exits, estimate exitRate (people per second, typically 2-5).
- For pathway width, estimate in meters (typical corridor: 2-4m, narrow: 1-2m, wide: 4-8m).
- Name elements descriptively based on what you see.
- Return ONLY the JSON object, no other text."""

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(
                        data=base64.b64decode(image_b64),
                        mime_type=mime_type,
                    ),
                    types.Part.from_text(text=prompt),
                ],
            ),
        ]
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.2,
            ),
        )
        
        # Parse the response text as JSON
        response_text = response.text.strip()
        
        # Remove markdown code fences if present
        if response_text.startswith('```'):
            response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
        
        result = json.loads(response_text)
        
        # Validate structure
        if 'pathways' not in result:
            result['pathways'] = []
        if 'entries' not in result:
            result['entries'] = []
        if 'exits' not in result:
            result['exits'] = []
        if 'chokePoints' not in result:
            result['chokePoints'] = []
        
        return jsonify({'success': True, 'floorPlan': result})
        
    except json.JSONDecodeError as e:
        return jsonify({'error': f'Failed to parse AI response as JSON: {str(e)}', 'raw': response_text}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)