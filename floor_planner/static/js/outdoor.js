// ==================== INITIALIZATION ====================
let map = null;  // Will be set from window.map in initialize()
let currentTool = null;
let elements = [];
let joints = [];
let currentPathway = null;
let currentPathwayPoints = [];
let previewRoutes = [];
let selectedRouteIndex = -1;

let origin = null;
let originMarker = null;

let nextId = 1;
let pathwayCounter = 1;
let entryCounter = 1;
let exitCounter = 1;
let chokeCounter = 1;
let jointCounter = 1;

let selectedElement = null;
let mapLayers = {
    pathways: [],
    markers: [],
    previewRoutes: []
};

const ROUTE_COLORS = ['#e74c3c', '#3498db', '#27ae60', '#f39c12', '#9b59b6'];
const CONNECTED_COLOR = '#27ae60';
const DISCONNECTED_COLOR = '#95a5a6';

// Initialize map
function initMap() {
    console.log('initMap() called');
    console.log('L (Leaflet) available:', typeof L !== 'undefined');
    console.log('map element:', document.getElementById('map'));

    if (typeof L === 'undefined') {
        console.error('Leaflet library not loaded!');
        document.getElementById('map').innerHTML = '<div style="padding: 20px; color: red;">Error: Leaflet library not loaded</div>';
        setTimeout(initMap, 100); // Retry after 100ms
        return;
    }

    const mapElement = document.getElementById('map');
    if (!mapElement) {
        console.error('Map element not found!');
        setTimeout(initMap, 100); // Retry after 100ms
        return;
    }

    console.log('Map element dimensions:', mapElement.offsetWidth, 'x', mapElement.offsetHeight);

    try {
        // Remove any existing map instance
        if (map) {
            console.log('Removing existing map...');
            map.remove();
        }

        map = L.map('map').setView([12.9716, 77.5946], 15); // Default to Bangalore

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(map);

        map.on('click', onMapClick);

        // Force map to resize after a short delay
        setTimeout(() => {
            if (map) {
                map.invalidateSize();
                console.log('Map size invalidated/refreshed');
            }
        }, 100);

        console.log('Map initialized successfully!', map);
    } catch (error) {
        console.error('Error initializing map:', error);
        document.getElementById('map').innerHTML = '<div style="padding: 20px; color: red;">Error initializing map: ' + error.message + '</div>';
    }
}

// ==================== TOOL SELECTION ====================
function setActiveTool(toolName) {
    document.querySelectorAll('.tool-btn').forEach(btn => btn.classList.remove('active'));
    currentTool = toolName;

    // Cancel any pending pathway creation
    if (toolName !== 'pathway' && currentPathwayPoints.length > 0) {
        finishPathway();
    }
    clearPreviewRoutes();
}

function setupEventListeners() {
    console.log('setupEventListeners() called');

    document.getElementById('pathway-btn').addEventListener('click', () => {
        setActiveTool('pathway');
        document.getElementById('pathway-btn').classList.add('active');
    });

    document.getElementById('entry-btn').addEventListener('click', () => {
        setActiveTool('entry');
        document.getElementById('entry-btn').classList.add('active');
    });

    document.getElementById('exit-btn').addEventListener('click', () => {
        setActiveTool('exit');
        document.getElementById('exit-btn').classList.add('active');
    });

    document.getElementById('choke-btn').addEventListener('click', () => {
        setActiveTool('choke');
        document.getElementById('choke-btn').classList.add('active');
    });

    document.getElementById('select-btn').addEventListener('click', () => {
        setActiveTool('select');
        document.getElementById('select-btn').classList.add('active');
    });

    document.getElementById('set-origin-btn').addEventListener('click', () => {
        setActiveTool('origin');
        document.getElementById('set-origin-btn').classList.add('active');
    });

    document.getElementById('clear-btn').addEventListener('click', () => {
        if (confirm('Are you sure you want to clear everything?')) {
            clearAll();
        }
    });

    document.getElementById('export-btn').addEventListener('click', exportToYAML);

    document.getElementById('import-btn').addEventListener('click', () => {
        document.getElementById('file-input').click();
    });

    document.getElementById('file-input').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            importFromYAML(file);
            e.target.value = '';
        }
    });

    document.getElementById('search-btn').addEventListener('click', searchLocation);
    document.getElementById('location-search').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') searchLocation();
    });

    document.getElementById('confirm-route').addEventListener('click', confirmRouteSelection);
    document.getElementById('cancel-route').addEventListener('click', cancelRouteSelection);

    document.getElementById('visualize-btn').addEventListener('click', () => {
        if (!origin) {
            alert('Please set an origin point first!');
            return;
        }

        const pathways = elements.filter(e => e.type === 'pathway');
        const entries = elements.filter(e => e.type === 'entry');
        const exits = elements.filter(e => e.type === 'exit');

        if (pathways.length === 0) {
            alert('Please create at least one pathway before running the visualizer.');
            return;
        }
        if (entries.length === 0 || exits.length === 0) {
            alert('Please add at least one entry and one exit point before running the visualizer.');
            return;
        }

        // Build YAML data (reuse export logic)
        const data = {
            type: 'outdoor',
            origin: { lat: origin.lat, lng: origin.lng },
            pixelsPerMeter: 1,
            pathways: [],
            entries: [],
            exits: [],
            chokePoints: [],
            joints: []
        };

        elements.forEach(el => {
            if (el.type === 'pathway') {
                data.pathways.push({ id: el.id, name: el.name, width: el.width, points: el.points.map(p => ({ x: p.x, y: p.y, lat: p.lat, lng: p.lng })) });
            } else if (el.type === 'entry') {
                data.entries.push({ id: el.id, name: el.name, x: el.x, y: el.y, lat: el.lat, lng: el.lng, spawnRate: el.spawnRate });
            } else if (el.type === 'exit') {
                data.exits.push({ id: el.id, name: el.name, x: el.x, y: el.y, lat: el.lat, lng: el.lng, exitRate: el.exitRate });
            } else if (el.type === 'choke') {
                data.chokePoints.push({ id: el.id, name: el.name, x: el.x, y: el.y, lat: el.lat, lng: el.lng });
            }
        });

        joints.forEach(joint => {
            data.joints.push({ id: joint.id, name: joint.name, x: joint.x, y: joint.y, lat: joint.lat, lng: joint.lng, connectedPathways: joint.connectedPathways });
        });

        const yamlStr = convertToYAML(data);

        fetch('/api/save-and-visualize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ yaml: yamlStr, filename: 'outdoor_venue.yaml' })
        })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    if (window.parent !== window) {
                        window.parent.postMessage({
                            type: 'raahi_navigate',
                            path: '/visualizer',
                            venuePath: result.filepath
                        }, '*');
                    } else {
                        window.open(result.visualizer_url, '_blank');
                    }
                } else {
                    alert('Error saving venue: ' + (result.error || 'Unknown error'));
                }
            })
            .catch(error => {
                alert('Error: ' + error.message);
            });
    });

    console.log('Event listeners setup complete');
}

// ==================== MAP CLICK HANDLER ====================
async function onMapClick(e) {
    const lat = e.latlng.lat;
    const lng = e.latlng.lng;

    console.log('Map clicked at:', lat, lng, 'currentTool:', currentTool);

    if (currentTool === 'origin') {
        console.log('Setting origin...');
        setOrigin(lat, lng);
    } else if (currentTool === 'pathway') {
        await handlePathwayClick(lat, lng);
    } else if (currentTool === 'entry' || currentTool === 'exit' || currentTool === 'choke') {
        await handlePointPlacement(lat, lng, currentTool);
    } else if (currentTool === 'select') {
        // Selection is handled by marker clicks
    }
}

// ==================== ORIGIN MANAGEMENT ====================
function setOrigin(lat, lng) {
    console.log('setOrigin called with:', lat, lng);
    origin = { lat, lng };

    if (originMarker) {
        map.removeLayer(originMarker);
    }

    const icon = L.divIcon({
        className: 'origin-marker',
        iconSize: [20, 20],
        iconAnchor: [10, 10]
    });

    originMarker = L.marker([lat, lng], { icon, draggable: true })
        .addTo(map)
        .bindPopup('Origin Point');

    console.log('Origin marker created:', originMarker);

    originMarker.on('dragend', (e) => {
        const pos = e.target.getLatLng();
        origin = { lat: pos.lat, lng: pos.lng };
        updateOriginDisplay();
        redrawAll(); // Recalculate offsets
    });

    updateOriginDisplay();
    setActiveTool(null);
}

function updateOriginDisplay() {
    document.getElementById('origin-lat').textContent = origin ? origin.lat.toFixed(6) : 'Not set';
    document.getElementById('origin-lng').textContent = origin ? origin.lng.toFixed(6) : 'Not set';
}

// Convert lat/lng to meters offset from origin
function latLngToMeters(lat, lng) {
    if (!origin) return { x: 0, y: 0 };

    const earthRadius = 6371000; // meters
    const dLat = (lat - origin.lat) * Math.PI / 180;
    const dLng = (lng - origin.lng) * Math.PI / 180;

    const x = dLng * earthRadius * Math.cos(origin.lat * Math.PI / 180);
    const y = dLat * earthRadius;

    return { x: Math.round(x * 100) / 100, y: Math.round(y * 100) / 100 };
}

// Convert meters offset to lat/lng
function metersToLatLng(x, y) {
    if (!origin) return { lat: 0, lng: 0 };

    const earthRadius = 6371000;
    const lat = origin.lat + (y / earthRadius) * (180 / Math.PI);
    const lng = origin.lng + (x / (earthRadius * Math.cos(origin.lat * Math.PI / 180))) * (180 / Math.PI);

    return { lat, lng };
}

// ==================== PATHWAY CREATION ====================
async function handlePathwayClick(lat, lng) {
    if (!origin) {
        alert('Please set an origin point first!');
        return;
    }

    showLoading();

    try {
        // Snap to nearest road
        const snapped = await snapToRoad(lat, lng);
        if (!snapped) {
            hideLoading();
            alert('Could not find a road nearby. Please click closer to a road.');
            return;
        }

        if (currentPathwayPoints.length === 0) {
            // First point
            currentPathwayPoints.push(snapped);
            addTempMarker(snapped.lat, snapped.lng);
            hideLoading();
        } else {
            // Calculate routes to this point
            const lastPoint = currentPathwayPoints[currentPathwayPoints.length - 1];
            const routes = await getRoutes(lastPoint, snapped);

            hideLoading();

            if (routes && routes.length > 0) {
                showRouteOptions(routes, snapped);
            } else {
                alert('No route found between these points.');
            }
        }
    } catch (error) {
        hideLoading();
        console.error('Error handling pathway click:', error);
        alert('Error: ' + error.message);
    }
}

async function snapToRoad(lat, lng) {
    try {
        const response = await fetch('/api/snap-to-road', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lat, lng })
        });

        if (response.ok) {
            return await response.json();
        }
        return null;
    } catch (error) {
        console.error('Snap to road error:', error);
        return null;
    }
}

async function getRoutes(start, end) {
    try {
        const response = await fetch('/api/route', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start, end })
        });

        if (response.ok) {
            const data = await response.json();
            return data.routes || [];
        }
        return [];
    } catch (error) {
        console.error('Get routes error:', error);
        return [];
    }
}

function showRouteOptions(routes, endPoint) {
    clearPreviewRoutes();

    const container = document.getElementById('route-options');
    container.innerHTML = '';

    routes.forEach((route, index) => {
        // Draw route on map
        const coords = route.geometry.coordinates.map(c => [c[1], c[0]]);
        const polyline = L.polyline(coords, {
            color: ROUTE_COLORS[index % ROUTE_COLORS.length],
            weight: 6,
            opacity: 0.7
        }).addTo(map);

        polyline.on('click', () => selectRoute(index));
        mapLayers.previewRoutes.push(polyline);

        // Add option to panel
        const distance = (route.distance / 1000).toFixed(2);
        const duration = Math.round(route.duration / 60);

        const option = document.createElement('div');
        option.className = 'route-option';
        option.dataset.index = index;
        option.innerHTML = `
            <strong style="color: ${ROUTE_COLORS[index % ROUTE_COLORS.length]}">Route ${index + 1}</strong><br>
            ${distance} km • ~${duration} min walk
        `;
        option.addEventListener('click', () => selectRoute(index));
        container.appendChild(option);
    });

    // Store for later use
    previewRoutes = routes;
    window.pendingEndPoint = endPoint;

    document.getElementById('route-selector').style.display = 'block';
}

function selectRoute(index) {
    selectedRouteIndex = index;

    // Update UI
    document.querySelectorAll('.route-option').forEach((opt, i) => {
        opt.classList.toggle('selected', i === index);
    });

    // Highlight selected route
    mapLayers.previewRoutes.forEach((polyline, i) => {
        polyline.setStyle({
            weight: i === index ? 8 : 4,
            opacity: i === index ? 1 : 0.4
        });
        if (i === index) {
            polyline.bringToFront();
        }
    });
}

function confirmRouteSelection() {
    if (selectedRouteIndex < 0) {
        alert('Please select a route first.');
        return;
    }

    const route = previewRoutes[selectedRouteIndex];
    const endPoint = window.pendingEndPoint;

    // Convert route coordinates to pathway points
    const routeCoords = route.geometry.coordinates.map(c => ({
        lat: c[1],
        lng: c[0]
    }));

    // Add route points to current pathway
    routeCoords.forEach(coord => {
        currentPathwayPoints.push(coord);
    });

    // Add marker at end point
    addTempMarker(endPoint.lat, endPoint.lng);

    // Clear route selection UI
    clearPreviewRoutes();
    document.getElementById('route-selector').style.display = 'none';
    selectedRouteIndex = -1;
    previewRoutes = [];

    // Draw the confirmed pathway segment
    redrawCurrentPathway();
}

function cancelRouteSelection() {
    clearPreviewRoutes();
    document.getElementById('route-selector').style.display = 'none';
    selectedRouteIndex = -1;
    previewRoutes = [];
}

function clearPreviewRoutes() {
    mapLayers.previewRoutes.forEach(layer => map.removeLayer(layer));
    mapLayers.previewRoutes = [];
}

function addTempMarker(lat, lng) {
    const icon = L.divIcon({
        className: 'pathway-marker',
        iconSize: [12, 12],
        iconAnchor: [6, 6]
    });

    const marker = L.marker([lat, lng], { icon }).addTo(map);
    mapLayers.markers.push(marker);
}

function redrawCurrentPathway() {
    // Remove existing current pathway line
    if (window.currentPathwayLine) {
        map.removeLayer(window.currentPathwayLine);
    }

    if (currentPathwayPoints.length > 1) {
        const coords = currentPathwayPoints.map(p => [p.lat, p.lng]);
        window.currentPathwayLine = L.polyline(coords, {
            color: '#3498db',
            weight: 5,
            opacity: 0.8
        }).addTo(map);
    }
}

function finishPathway() {
    if (currentPathwayPoints.length > 1) {
        // Convert to meter offsets
        const points = currentPathwayPoints.map(p => {
            const offset = latLngToMeters(p.lat, p.lng);
            return { x: offset.x, y: offset.y, lat: p.lat, lng: p.lng };
        });

        const pathway = {
            id: nextId++,
            type: 'pathway',
            name: `Pathway ${pathwayCounter++}`,
            width: 2.0,
            points: points
        };

        elements.push(pathway);
    }

    // Clear temp markers
    mapLayers.markers.forEach(m => map.removeLayer(m));
    mapLayers.markers = [];

    if (window.currentPathwayLine) {
        map.removeLayer(window.currentPathwayLine);
        window.currentPathwayLine = null;
    }

    currentPathwayPoints = [];

    detectJoints();
    redrawAll();
    updateStats();
}

// Double-click to finish pathway (registered in initializeOutdoorEditor)

// ==================== POINT PLACEMENT ====================
async function handlePointPlacement(lat, lng, type) {
    if (!origin) {
        alert('Please set an origin point first!');
        return;
    }

    // Check if point is on a pathway
    if (!isPointOnAnyPathway(lat, lng)) {
        alert(`${type.charAt(0).toUpperCase() + type.slice(1)} points must be placed on a pathway!`);
        return;
    }

    const offset = latLngToMeters(lat, lng);

    const element = {
        id: nextId++,
        type: type,
        x: offset.x,
        y: offset.y,
        lat: lat,
        lng: lng
    };

    if (type === 'entry') {
        element.name = `Entry ${entryCounter++}`;
        element.spawnRate = 1.0;
    } else if (type === 'exit') {
        element.name = `Exit ${exitCounter++}`;
        element.exitRate = 1.0;
    } else if (type === 'choke') {
        element.name = `Choke ${chokeCounter++}`;
    }

    elements.push(element);
    redrawAll();
    updateStats();
}

function isPointOnAnyPathway(lat, lng, threshold = 0.0001) {
    for (let el of elements) {
        if (el.type === 'pathway') {
            for (let i = 1; i < el.points.length; i++) {
                const p1 = el.points[i - 1];
                const p2 = el.points[i];

                // Use lat/lng for distance calculation
                const dist = distanceToSegmentLatLng(
                    lat, lng,
                    p1.lat, p1.lng,
                    p2.lat, p2.lng
                );

                if (dist < threshold) {
                    return true;
                }
            }
        }
    }
    return false;
}

function distanceToSegmentLatLng(lat, lng, lat1, lng1, lat2, lng2) {
    const A = lat - lat1;
    const B = lng - lng1;
    const C = lat2 - lat1;
    const D = lng2 - lng1;

    const dot = A * C + B * D;
    const lenSq = C * C + D * D;
    let param = -1;
    if (lenSq !== 0) param = dot / lenSq;

    let closeLat, closeLng;
    if (param < 0) {
        closeLat = lat1;
        closeLng = lng1;
    } else if (param > 1) {
        closeLat = lat2;
        closeLng = lng2;
    } else {
        closeLat = lat1 + param * C;
        closeLng = lng1 + param * D;
    }

    return Math.sqrt(Math.pow(lat - closeLat, 2) + Math.pow(lng - closeLng, 2));
}

// ==================== JOINT DETECTION ====================
function detectJoints() {
    joints = [];
    jointCounter = 1;

    const pathways = elements.filter(e => e.type === 'pathway');
    const jointThreshold = 0.00005; // ~5 meters in lat/lng

    const jointMap = new Map();

    // Check for endpoint connections
    for (let pathway of pathways) {
        if (!pathway.points || pathway.points.length < 2) continue;

        const startPoint = pathway.points[0];
        const endPoint = pathway.points[pathway.points.length - 1];

        [startPoint, endPoint].forEach(point => {
            let found = false;
            for (let [key, joint] of jointMap) {
                const dist = Math.sqrt(
                    Math.pow(joint.lat - point.lat, 2) +
                    Math.pow(joint.lng - point.lng, 2)
                );
                if (dist < jointThreshold) {
                    if (!joint.connectedPathways.includes(pathway.id)) {
                        joint.connectedPathways.push(pathway.id);
                    }
                    found = true;
                    break;
                }
            }
            if (!found) {
                jointMap.set(`${point.lat},${point.lng}`, {
                    lat: point.lat,
                    lng: point.lng,
                    connectedPathways: [pathway.id]
                });
            }
        });
    }

    // Check for T-junctions
    for (let i = 0; i < pathways.length; i++) {
        for (let j = 0; j < pathways.length; j++) {
            if (i === j) continue;

            const p1 = pathways[i];
            const p2 = pathways[j];

            const endpoints = [p1.points[0], p1.points[p1.points.length - 1]];

            for (let endpoint of endpoints) {
                for (let b = 1; b < p2.points.length; b++) {
                    const segStart = p2.points[b - 1];
                    const segEnd = p2.points[b];

                    const dist = distanceToSegmentLatLng(
                        endpoint.lat, endpoint.lng,
                        segStart.lat, segStart.lng,
                        segEnd.lat, segEnd.lng
                    );

                    if (dist < jointThreshold) {
                        let found = false;
                        for (let [key, joint] of jointMap) {
                            const d = Math.sqrt(
                                Math.pow(joint.lat - endpoint.lat, 2) +
                                Math.pow(joint.lng - endpoint.lng, 2)
                            );
                            if (d < jointThreshold) {
                                if (!joint.connectedPathways.includes(p1.id)) {
                                    joint.connectedPathways.push(p1.id);
                                }
                                if (!joint.connectedPathways.includes(p2.id)) {
                                    joint.connectedPathways.push(p2.id);
                                }
                                found = true;
                                break;
                            }
                        }
                        if (!found) {
                            jointMap.set(`tjunc_${endpoint.lat},${endpoint.lng}`, {
                                lat: endpoint.lat,
                                lng: endpoint.lng,
                                connectedPathways: [p1.id, p2.id]
                            });
                        }
                    }
                }
            }
        }
    }

    // Convert to joints array
    for (let [key, joint] of jointMap) {
        if (joint.connectedPathways.length >= 2) {
            const offset = latLngToMeters(joint.lat, joint.lng);
            joints.push({
                id: nextId++,
                name: `Joint ${jointCounter++}`,
                x: offset.x,
                y: offset.y,
                lat: joint.lat,
                lng: joint.lng,
                connectedPathways: joint.connectedPathways
            });
        }
    }
}

function getLargestPathwayNetwork() {
    const pathways = elements.filter(e => e.type === 'pathway');
    if (pathways.length === 0) return [];

    const networks = [];
    const visited = new Set();

    for (let pathway of pathways) {
        if (visited.has(pathway.id)) continue;

        const network = [];
        const queue = [pathway];
        visited.add(pathway.id);

        while (queue.length > 0) {
            const current = queue.shift();
            network.push(current);

            for (let other of pathways) {
                if (visited.has(other.id)) continue;
                if (arePathwaysConnected(current, other)) {
                    visited.add(other.id);
                    queue.push(other);
                }
            }
        }

        networks.push(network);
    }

    return networks.reduce((largest, current) =>
        current.length > largest.length ? current : largest, []);
}

function arePathwaysConnected(p1, p2) {
    // Check via joints
    for (let joint of joints) {
        if (joint.connectedPathways.includes(p1.id) && joint.connectedPathways.includes(p2.id)) {
            return true;
        }
    }
    return false;
}

// ==================== RENDERING ====================
function redrawAll() {
    // Clear existing layers
    mapLayers.pathways.forEach(layer => map.removeLayer(layer));
    mapLayers.pathways = [];
    mapLayers.markers.forEach(marker => map.removeLayer(marker));
    mapLayers.markers = [];

    const largestNetwork = getLargestPathwayNetwork();
    const largestNetworkIds = new Set(largestNetwork.map(p => p.id));

    // Draw pathways
    elements.filter(e => e.type === 'pathway').forEach(pathway => {
        if (!pathway.points || pathway.points.length < 2) return;

        const coords = pathway.points.map(p => [p.lat, p.lng]);
        const isConnected = largestNetworkIds.has(pathway.id);

        const polyline = L.polyline(coords, {
            color: isConnected ? CONNECTED_COLOR : DISCONNECTED_COLOR,
            weight: (pathway.width || 2) * 3,
            opacity: 0.8
        }).addTo(map);

        polyline.on('click', () => selectElement(pathway));
        mapLayers.pathways.push(polyline);
    });

    // Draw joints
    joints.forEach(joint => {
        const icon = L.divIcon({
            className: 'joint-marker',
            iconSize: [16 + joint.connectedPathways.length * 2, 16 + joint.connectedPathways.length * 2],
            iconAnchor: [8 + joint.connectedPathways.length, 8 + joint.connectedPathways.length],
            html: `<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:white;font-size:10px;font-weight:bold;">${joint.connectedPathways.length}</div>`
        });

        const marker = L.marker([joint.lat, joint.lng], { icon })
            .addTo(map);
        marker.on('click', () => selectElement(joint));
        mapLayers.markers.push(marker);
    });

    // Draw other elements
    elements.filter(e => e.type !== 'pathway').forEach(el => {
        let className = '';
        if (el.type === 'entry') className = 'entry-marker';
        else if (el.type === 'exit') className = 'exit-marker';
        else if (el.type === 'choke') className = 'choke-marker';

        const icon = L.divIcon({
            className: className,
            iconSize: [16, 16],
            iconAnchor: [8, 8]
        });

        const marker = L.marker([el.lat, el.lng], { icon, draggable: true })
            .addTo(map)
            .bindPopup(el.name);

        marker.on('click', () => selectElement(el));
        marker.on('dragend', (e) => {
            const pos = e.target.getLatLng();
            if (isPointOnAnyPathway(pos.lat, pos.lng)) {
                el.lat = pos.lat;
                el.lng = pos.lng;
                const offset = latLngToMeters(pos.lat, pos.lng);
                el.x = offset.x;
                el.y = offset.y;
            } else {
                marker.setLatLng([el.lat, el.lng]);
                alert('Point must stay on a pathway!');
            }
        });

        mapLayers.markers.push(marker);
    });
}

// ==================== ELEMENT SELECTION ====================
function selectElement(element) {
    selectedElement = element;
    showPropertyEditor(element);
}

function showPropertyEditor(element) {
    const editor = document.getElementById('property-editor');
    const content = document.getElementById('property-content');
    content.innerHTML = '';

    if (element.type === 'pathway') {
        content.innerHTML = `
            <div class="property-group">
                <label>Name:</label>
                <input type="text" id="prop-name" value="${element.name}">
            </div>
            <div class="property-group">
                <label>Width (meters):</label>
                <input type="number" id="prop-width" value="${element.width}" min="0.5" max="10" step="0.1">
            </div>
            <button class="delete-btn" onclick="deleteSelectedElement()">Delete Pathway</button>
        `;
    } else if (element.type === 'entry') {
        content.innerHTML = `
            <div class="property-group">
                <label>Name:</label>
                <input type="text" id="prop-name" value="${element.name}">
            </div>
            <div class="property-group">
                <label>Spawn Rate (people/sec):</label>
                <input type="number" id="prop-spawn-rate" value="${element.spawnRate}" min="0" step="0.1">
            </div>
            <button class="delete-btn" onclick="deleteSelectedElement()">Delete Entry</button>
        `;
    } else if (element.type === 'exit') {
        content.innerHTML = `
            <div class="property-group">
                <label>Name:</label>
                <input type="text" id="prop-name" value="${element.name}">
            </div>
            <div class="property-group">
                <label>Exit Rate (people/sec):</label>
                <input type="number" id="prop-exit-rate" value="${element.exitRate}" min="0" step="0.1">
            </div>
            <button class="delete-btn" onclick="deleteSelectedElement()">Delete Exit</button>
        `;
    } else if (element.type === 'choke') {
        content.innerHTML = `
            <div class="property-group">
                <label>Name:</label>
                <input type="text" id="prop-name" value="${element.name}">
            </div>
            <button class="delete-btn" onclick="deleteSelectedElement()">Delete Choke Point</button>
        `;
    } else if (element.type === 'joint' || element.connectedPathways) {
        const pathwayNames = element.connectedPathways.map(id => {
            const p = elements.find(e => e.id === id);
            return p ? p.name : `Pathway ${id}`;
        }).join(', ');

        content.innerHTML = `
            <div class="property-group">
                <label>Name:</label>
                <input type="text" id="prop-name" value="${element.name}">
            </div>
            <div class="property-group">
                <label>Connected Pathways:</label>
                <p style="font-size: 12px; color: #bdc3c7;">${pathwayNames}</p>
            </div>
        `;
    }

    // Add event listeners
    const nameInput = document.getElementById('prop-name');
    if (nameInput) {
        nameInput.addEventListener('input', (e) => {
            element.name = e.target.value;
        });
    }

    const widthInput = document.getElementById('prop-width');
    if (widthInput) {
        widthInput.addEventListener('input', (e) => {
            element.width = parseFloat(e.target.value);
            redrawAll();
        });
    }

    const spawnRateInput = document.getElementById('prop-spawn-rate');
    if (spawnRateInput) {
        spawnRateInput.addEventListener('input', (e) => {
            element.spawnRate = parseFloat(e.target.value);
        });
    }

    const exitRateInput = document.getElementById('prop-exit-rate');
    if (exitRateInput) {
        exitRateInput.addEventListener('input', (e) => {
            element.exitRate = parseFloat(e.target.value);
        });
    }

    editor.style.display = 'block';
}

function hidePropertyEditor() {
    document.getElementById('property-editor').style.display = 'none';
}

function deleteSelectedElement() {
    if (selectedElement) {
        elements = elements.filter(e => e.id !== selectedElement.id);
        selectedElement = null;
        hidePropertyEditor();
        detectJoints();
        redrawAll();
        updateStats();
    }
}

// ==================== STATS ====================
function updateStats() {
    document.getElementById('pathway-count').textContent = elements.filter(e => e.type === 'pathway').length;
    document.getElementById('entry-count').textContent = elements.filter(e => e.type === 'entry').length;
    document.getElementById('exit-count').textContent = elements.filter(e => e.type === 'exit').length;
    document.getElementById('choke-count').textContent = elements.filter(e => e.type === 'choke').length;
    document.getElementById('joint-count').textContent = joints.length;
}

// ==================== EXPORT/IMPORT ====================
function exportToYAML() {
    if (!origin) {
        alert('Please set an origin point before exporting.');
        return;
    }

    const data = {
        type: 'outdoor',
        origin: {
            lat: origin.lat,
            lng: origin.lng
        },
        pixelsPerMeter: 1,
        pathways: [],
        entries: [],
        exits: [],
        chokePoints: [],
        joints: []
    };

    elements.forEach(el => {
        if (el.type === 'pathway') {
            data.pathways.push({
                id: el.id,
                name: el.name,
                width: el.width,
                points: el.points.map(p => ({ x: p.x, y: p.y, lat: p.lat, lng: p.lng }))
            });
        } else if (el.type === 'entry') {
            data.entries.push({
                id: el.id,
                name: el.name,
                x: el.x,
                y: el.y,
                lat: el.lat,
                lng: el.lng,
                spawnRate: el.spawnRate
            });
        } else if (el.type === 'exit') {
            data.exits.push({
                id: el.id,
                name: el.name,
                x: el.x,
                y: el.y,
                lat: el.lat,
                lng: el.lng,
                exitRate: el.exitRate
            });
        } else if (el.type === 'choke') {
            data.chokePoints.push({
                id: el.id,
                name: el.name,
                x: el.x,
                y: el.y,
                lat: el.lat,
                lng: el.lng
            });
        }
    });

    joints.forEach(joint => {
        data.joints.push({
            id: joint.id,
            name: joint.name,
            x: joint.x,
            y: joint.y,
            lat: joint.lat,
            lng: joint.lng,
            connectedPathways: joint.connectedPathways
        });
    });

    const yamlStr = convertToYAML(data);
    const blob = new Blob([yamlStr], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'outdoor_venue.yaml';
    a.click();
    URL.revokeObjectURL(url);
}

function convertToYAML(obj, indent = 0) {
    let yaml = '';
    const spaces = '  '.repeat(indent);

    for (let key in obj) {
        const value = obj[key];
        if (Array.isArray(value)) {
            yaml += `${spaces}${key}:\n`;
            value.forEach(item => {
                if (typeof item === 'object') {
                    yaml += `${spaces}  -\n`;
                    for (let k in item) {
                        const v = item[k];
                        if (Array.isArray(v)) {
                            yaml += `${spaces}      ${k}:\n`;
                            v.forEach(subItem => {
                                if (typeof subItem === 'object') {
                                    yaml += `${spaces}        -\n`;
                                    for (let sk in subItem) {
                                        yaml += `${spaces}            ${sk}: ${subItem[sk]}\n`;
                                    }
                                } else {
                                    yaml += `${spaces}        - ${subItem}\n`;
                                }
                            });
                        } else {
                            yaml += `${spaces}      ${k}: ${v}\n`;
                        }
                    }
                } else {
                    yaml += `${spaces}  - ${item}\n`;
                }
            });
        } else if (typeof value === 'object' && value !== null) {
            yaml += `${spaces}${key}:\n`;
            for (let k in value) {
                yaml += `${spaces}  ${k}: ${value[k]}\n`;
            }
        } else {
            yaml += `${spaces}${key}: ${value}\n`;
        }
    }
    return yaml;
}

function importFromYAML(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
        try {
            const yamlText = e.target.result;
            const data = parseYAML(yamlText);

            // Check if this is an outdoor file
            if (data.type && data.type !== 'outdoor') {
                alert('This appears to be an indoor venue file. Please use the Indoor Editor.');
                return;
            }

            clearAll();

            // Set origin
            if (data.origin) {
                setOrigin(data.origin.lat, data.origin.lng);
                map.setView([data.origin.lat, data.origin.lng], 15);
            }

            // Load pathways
            if (data.pathways) {
                data.pathways.forEach(p => {
                    elements.push({
                        id: nextId++,
                        type: 'pathway',
                        name: p.name,
                        width: p.width,
                        points: p.points
                    });
                    pathwayCounter++;
                });
            }

            // Load entries
            if (data.entries) {
                data.entries.forEach(e => {
                    elements.push({
                        id: nextId++,
                        type: 'entry',
                        name: e.name,
                        x: e.x,
                        y: e.y,
                        lat: e.lat,
                        lng: e.lng,
                        spawnRate: e.spawnRate
                    });
                    entryCounter++;
                });
            }

            // Load exits
            if (data.exits) {
                data.exits.forEach(e => {
                    elements.push({
                        id: nextId++,
                        type: 'exit',
                        name: e.name,
                        x: e.x,
                        y: e.y,
                        lat: e.lat,
                        lng: e.lng,
                        exitRate: e.exitRate
                    });
                    exitCounter++;
                });
            }

            // Load choke points
            if (data.chokePoints) {
                data.chokePoints.forEach(c => {
                    elements.push({
                        id: nextId++,
                        type: 'choke',
                        name: c.name,
                        x: c.x,
                        y: c.y,
                        lat: c.lat,
                        lng: c.lng
                    });
                    chokeCounter++;
                });
            }

            detectJoints();
            redrawAll();
            updateStats();
            alert('Venue imported successfully!');
        } catch (error) {
            alert('Error importing YAML file: ' + error.message);
            console.error('YAML parse error:', error);
        }
    };
    reader.readAsText(file);
}

function parseYAML(yamlText) {
    const lines = yamlText.split('\n');
    const result = {
        type: 'outdoor',
        origin: null,
        pixelsPerMeter: 1,
        pathways: [],
        entries: [],
        exits: [],
        chokePoints: [],
        joints: []
    };

    let currentSection = null;
    let currentObject = null;
    let currentSubArray = null;
    let currentSubObject = null;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmed = line.trim();

        if (!trimmed || trimmed.startsWith('#')) continue;

        const indent = line.search(/\S/);

        if (indent === 0 && trimmed.includes(':')) {
            const colonIndex = trimmed.indexOf(':');
            const key = trimmed.substring(0, colonIndex).trim();
            const value = trimmed.substring(colonIndex + 1).trim();

            if (key === 'origin') {
                result.origin = {};
                currentSection = 'origin';
            } else if (value) {
                result[key] = isNaN(value) ? value : parseFloat(value);
            } else {
                currentSection = key;
            }
            currentObject = null;
            currentSubArray = null;
            currentSubObject = null;
        }
        else if (indent === 2 && currentSection === 'origin' && trimmed.includes(':')) {
            const colonIndex = trimmed.indexOf(':');
            const key = trimmed.substring(0, colonIndex).trim();
            const value = trimmed.substring(colonIndex + 1).trim();
            result.origin[key] = parseFloat(value);
        }
        else if (indent === 2 && trimmed.startsWith('-')) {
            currentObject = {};
            if (currentSection === 'pathways') result.pathways.push(currentObject);
            else if (currentSection === 'entries') result.entries.push(currentObject);
            else if (currentSection === 'exits') result.exits.push(currentObject);
            else if (currentSection === 'chokePoints') result.chokePoints.push(currentObject);
            else if (currentSection === 'joints') result.joints.push(currentObject);
            currentSubArray = null;
            currentSubObject = null;
        }
        else if ((indent === 4 || indent === 6) && trimmed.includes(':') && !trimmed.startsWith('-') && currentObject) {
            const colonIndex = trimmed.indexOf(':');
            const key = trimmed.substring(0, colonIndex).trim();
            const value = trimmed.substring(colonIndex + 1).trim();

            if (value) {
                currentObject[key] = isNaN(value) ? value : parseFloat(value);
            } else {
                currentObject[key] = [];
                currentSubArray = currentObject[key];
            }
            currentSubObject = null;
        }
        else if (indent === 8 && trimmed.startsWith('-') && currentSubArray) {
            const content = trimmed.substring(1).trim();

            if (content === '') {
                currentSubObject = {};
                currentSubArray.push(currentSubObject);
            } else {
                currentSubArray.push(isNaN(content) ? content : parseFloat(content));
            }
        }
        else if (indent === 12 && trimmed.includes(':') && currentSubObject) {
            const colonIndex = trimmed.indexOf(':');
            const key = trimmed.substring(0, colonIndex).trim();
            const value = trimmed.substring(colonIndex + 1).trim();
            currentSubObject[key] = isNaN(value) ? value : parseFloat(value);
        }
    }

    return result;
}

// ==================== UTILITIES ====================
function clearAll() {
    elements = [];
    joints = [];
    currentPathwayPoints = [];

    mapLayers.pathways.forEach(layer => map.removeLayer(layer));
    mapLayers.pathways = [];
    mapLayers.markers.forEach(marker => map.removeLayer(marker));
    mapLayers.markers = [];

    if (window.currentPathwayLine) {
        map.removeLayer(window.currentPathwayLine);
        window.currentPathwayLine = null;
    }

    clearPreviewRoutes();
    hidePropertyEditor();
    updateStats();
}

function searchLocation() {
    const query = document.getElementById('location-search').value;
    if (!query) return;

    console.log('searchLocation called, map:', map);

    if (!map) {
        console.error('Map is not initialized!');
        alert('Map not initialized yet. Please wait a moment and try again.');
        return;
    }

    const resultsContainer = document.getElementById('search-results');
    const resultsList = document.getElementById('search-results-list');

    // Show loading state
    resultsList.innerHTML = '<p style="color: #95a5a6; padding: 10px;">Searching...</p>';
    resultsContainer.style.display = 'block';

    fetch('/api/geocode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query })
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Geocode response:', data);
            if (data.error) {
                resultsList.innerHTML = `<p style="color: #e74c3c; padding: 10px;">Error: ${data.error}</p>`;
                return;
            }
            if (data && data.length > 0) {
                displaySearchResults(data);
            } else {
                resultsList.innerHTML = '<p style="color: #f39c12; padding: 10px;">No locations found. Try a different search.</p>';
            }
        })
        .catch(error => {
            console.error('Search error:', error);
            resultsList.innerHTML = `<p style="color: #e74c3c; padding: 10px;">Error: ${error.message}</p>`;
        });
}

function displaySearchResults(results) {
    const resultsList = document.getElementById('search-results-list');
    resultsList.innerHTML = '';

    results.forEach((result, index) => {
        const item = document.createElement('div');
        item.className = 'search-result-item';

        // Parse the display name - take the first part as name, rest as type/location
        const nameParts = result.display_name.split(',');
        const name = nameParts[0].trim();
        const location = nameParts.slice(1, 4).join(',').trim();

        item.innerHTML = `
            <div class="result-name">${name}</div>
            <div class="result-type">${location || result.type || 'Location'}</div>
        `;

        item.addEventListener('click', () => {
            selectSearchResult(result);
        });

        resultsList.appendChild(item);
    });
}

function selectSearchResult(result) {
    const lat = parseFloat(result.lat);
    const lon = parseFloat(result.lon);

    console.log('Selected location:', result.display_name, lat, lon);

    // Move map to selected location
    map.setView([lat, lon], 16);

    // Add a temporary marker to show the location
    const marker = L.marker([lat, lon])
        .addTo(map)
        .bindPopup(result.display_name)
        .openPopup();

    // Remove marker after 5 seconds
    setTimeout(() => {
        if (map.hasLayer(marker)) {
            map.removeLayer(marker);
        }
    }, 5000);

    // Hide search results
    document.getElementById('search-results').style.display = 'none';
}

function showLoading() {
    document.getElementById('loading-overlay').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loading-overlay').style.display = 'none';
}

// ==================== INITIALIZE ====================
function initializeOutdoorEditor() {
    console.log('initializeOutdoorEditor() called');

    // Initialize map
    try {
        map = L.map('map').setView([12.9716, 77.5946], 15);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(map);
        map.on('click', onMapClick);
        map.on('dblclick', (e) => {
            if (currentTool === 'pathway' && currentPathwayPoints.length > 1) {
                e.originalEvent.preventDefault();
                finishPathway();
            }
        });
        console.log('Map initialized and click handler attached');
    } catch (e) {
        console.error('Map init failed:', e);
        return;
    }

    // Set up event listeners
    try {
        setupEventListeners();
        console.log('Event listeners set up');
    } catch (e) {
        console.error('setupEventListeners failed:', e);
    }

    // Update stats
    try {
        updateStats();
    } catch (e) {
        console.error('updateStats failed:', e);
    }

    console.log('Initialization complete!');
}
