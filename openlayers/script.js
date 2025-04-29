// --- Configuration ---
const flaskApiUrl = 'http://localhost:5001/api/demographics'; // Your Flask API endpoint
const atlantaCoords = [-84.3880, 33.7490]; // Longitude, Latitude for Atlanta center
const initialZoom = 11;
const atlantaBoundaryUrl = '/data/Atlanta_Boundary.geojson'; // Path to your Atlanta boundary GeoJSON file
// Note: Ensure this file is served by your frontend server (e.g., Python's http.server)

// --- Map Initialization ---
const map = new ol.Map({
    target: 'map', // ID of the map div
    layers: [
        new ol.layer.Tile({
            source: new ol.source.OSM() // OpenStreetMap base layer
        })
    ],
    view: new ol.View({
        center: ol.proj.fromLonLat(atlantaCoords), // Project coordinates
        zoom: initialZoom
    })
});

// --- Vector Layers ---
// Layer for the drawn polygon
const drawSource = new ol.source.Vector({ wrapX: false });
const drawLayer = new ol.layer.Vector({
    source: drawSource,
    style: new ol.style.Style({
        fill: new ol.style.Fill({
            color: 'rgba(0, 123, 255, 0.2)' // Light blue fill
        }),
        stroke: new ol.style.Stroke({
            color: '#007bff', // Blue border
            width: 2
        }),
        image: new ol.style.Circle({ // Style for points if needed
            radius: 7,
            fill: new ol.style.Fill({ color: '#007bff' })
        })
    })
});
map.addLayer(drawLayer);

// Layer for Atlanta boundary
const boundarySource = new ol.source.Vector({
    url: atlantaBoundaryUrl,
    format: new ol.format.GeoJSON()
});
const boundaryLayer = new ol.layer.Vector({
    source: boundarySource,
    style: new ol.style.Style({
        stroke: new ol.style.Stroke({
            color: '#28a745', // Green boundary
            width: 3
        })
    })
});
map.addLayer(boundaryLayer);

// --- Drawing Interaction ---
let drawInteraction; // Variable to hold the draw interaction
const drawButton = document.getElementById('draw-polygon-btn');
const loadingIndicator = document.getElementById('loading-indicator');

function addDrawInteraction() {
    drawInteraction = new ol.interaction.Draw({
        source: drawSource,
        type: 'Polygon' // Draw polygons
    });

    map.addInteraction(drawInteraction);

    // Event listener for when drawing starts
    drawInteraction.on('drawstart', function() {
        drawSource.clear(); // Clear previous polygon before starting new one
    });

    // Event listener for when drawing ends
    drawInteraction.on('drawend', function(event) {
        console.log("Drawing finished.");
        const feature = event.feature;
        const geometry = feature.getGeometry();

        // Transform geometry to standard EPSG:4326 (Lat/Lon) for GeoJSON
        const transformedGeometry = geometry.clone().transform(map.getView().getProjection(), 'EPSG:4326');

        // Convert the transformed geometry to GeoJSON format
        const format = new ol.format.GeoJSON();
        const polygonGeoJSON = format.writeGeometryObject(transformedGeometry);

        console.log("Polygon GeoJSON:", JSON.stringify(polygonGeoJSON, null, 2));

        // Send the GeoJSON to the backend
        fetchDemographics(polygonGeoJSON);

        // Deactivate drawing after one polygon is drawn
        deactivateDrawing();
    });
}

function activateDrawing() {
     if (!drawInteraction) {
         addDrawInteraction();
     }
     drawInteraction.setActive(true);
     drawButton.classList.add('active');
     drawButton.textContent = 'Drawing... (Click start point to finish)';
     console.log("Draw interaction activated.");
}

function deactivateDrawing() {
     if (drawInteraction) {
         drawInteraction.setActive(false);
         // Optional: remove interaction completely if needed
         // map.removeInteraction(drawInteraction);
         // drawInteraction = null;
     }
     drawButton.classList.remove('active');
     drawButton.textContent = 'Draw Polygon';
     console.log("Draw interaction deactivated.");
}


// Toggle drawing on button click
drawButton.addEventListener('click', () => {
    if (drawButton.classList.contains('active')) {
        deactivateDrawing();
    } else {
        activateDrawing();
    }
});


// --- Chart Initialization and Update Functions ---
// Store chart instances globally to destroy them before recreating
let ageChartInstance = null;
let sexChartInstance = null;
let ethnicityChartInstance = null;

// Function to create or update a bar chart
function createOrUpdateChart(canvasId, chartInstance, label, data, chartType = 'bar') {
    const ctx = document.getElementById(canvasId).getContext('2d');
    const labels = Object.keys(data);
    const values = Object.values(data);

    // Destroy previous chart instance if it exists
    if (chartInstance) {
        chartInstance.destroy();
    }

    // Define some colors (add more if needed)
    const backgroundColors = [
        'rgba(54, 162, 235, 0.6)', // Blue
        'rgba(255, 99, 132, 0.6)',  // Red
        'rgba(75, 192, 192, 0.6)', // Green
        'rgba(255, 206, 86, 0.6)',  // Yellow
        'rgba(153, 102, 255, 0.6)',// Purple
        'rgba(255, 159, 64, 0.6)'  // Orange
    ];
     const borderColors = backgroundColors.map(color => color.replace('0.6', '1')); // Make borders opaque

    return new Chart(ctx, {
        type: chartType,
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: values,
                backgroundColor: backgroundColors.slice(0, labels.length),
                borderColor: borderColors.slice(0, labels.length),
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false, // Allow chart to fill container height
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                         precision: 0 // Ensure whole numbers on y-axis for counts
                    }
                }
            },
            plugins: {
                legend: {
                    display: false // Hide legend if label is clear enough
                }
            }
        }
    });
}

// --- API Call Function ---
function fetchDemographics(polygonGeoJSON) {
    console.log("Fetching demographics from API...");
    loadingIndicator.style.display = 'block'; // Show loading indicator

    fetch(flaskApiUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ polygon: polygonGeoJSON }) // Send polygon as JSON
    })
    .then(response => {
        if (!response.ok) {
            // Try to get error message from response body
            return response.json().then(errData => {
                 throw new Error(`API Error (${response.status}): ${errData.error || 'Unknown error'}`);
            }).catch(() => {
                 // If response body is not JSON or empty
                 throw new Error(`API Error (${response.status}): ${response.statusText}`);
            });
        }
        return response.json(); // Parse JSON response
    })
    .then(data => {
        console.log("API Response Received:", data);
        loadingIndicator.style.display = 'none'; // Hide loading indicator

        // --- Update Charts ---
        // Ensure data.counts exists and has the expected keys
        if (data.counts) {
            ageChartInstance = createOrUpdateChart('ageChart', ageChartInstance, 'Count by Age Group', data.counts.age || {});
            sexChartInstance = createOrUpdateChart('sexChart', sexChartInstance, 'Count by Sex', data.counts.sex || {});
            ethnicityChartInstance = createOrUpdateChart('ethnicityChart', ethnicityChartInstance, 'Count by Ethnicity', data.counts.ethnicity || {});
        } else {
             console.warn("No 'counts' data received from API.");
             // Optionally clear charts or show a message
        }


        // --- Display Statistical Results ---
        const statsResultsDiv = document.getElementById('stats-results');
        if (!statsResultsDiv) {
            console.error("Element with ID 'stats-results' not found.");
            return;
        }

        statsResultsDiv.innerHTML = '<h3>Statistical Comparison (vs. City Average)</h3>'; // Clear previous results

        if (data.stats) {
             if (data.stats.message) { // Handle messages like "No population found"
                 statsResultsDiv.innerHTML += `<p>${data.stats.message}</p>`;
             } else {
                 // Iterate through categories (age, sex, ethnicity)
                 for (const category in data.stats) {
                     const stat = data.stats[category];
                     let resultText = '';
                     // Make category name more readable (e.g., 'age_group' -> 'Age Group')
                     const categoryName = category.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

                     if (stat.error) {
                         resultText = `<p><strong>${categoryName}:</strong> <span style="color: orange;">${stat.error}</span></p>`;
                     } else if (stat.p_value !== undefined && stat.p_value !== null) {
                         const pValue = stat.p_value;
                         const significanceThreshold = 0.05;
                         const isSignificant = pValue < significanceThreshold;

                         resultText = `<p><strong>${categoryName}:</strong> Chi-squared test p-value = ${pValue.toExponential(3)}. `; // Use exponential notation for small p-values
                         if (isSignificant) {
                             resultText += '<span style="color: red; font-weight: bold;">The distribution in this area is significantly different from the city average (p < 0.05).</span>';
                         } else {
                             resultText += '<span style="color: green;">No significant difference found compared to the city average (p ≥ 0.05).</span>';
                         }
                         resultText += '</p>';
                     } else {
                          // Handle cases where stats might be missing p-value without an error
                          resultText = `<p><strong>${categoryName}:</strong> <span style="color: grey;">Analysis result unavailable.</span></p>`;
                     }
                     statsResultsDiv.innerHTML += resultText;
                 }
             }
        } else {
             statsResultsDiv.innerHTML += '<p style="color: orange;">Statistical analysis results not available from the server.</p>';
             console.warn("No 'stats' data received from API.");
        }

    })
    .catch(error => {
        console.error('Error fetching or processing demographics:', error);
        loadingIndicator.style.display = 'none'; // Hide loading indicator

        const statsResultsDiv = document.getElementById('stats-results');
        if (statsResultsDiv) {
            statsResultsDiv.innerHTML = `<h3>Statistical Comparison (vs. City Average)</h3><p style="color: red;">Error retrieving analysis results: ${error.message}</p>`;
        }
         // Optionally clear charts on error too
         if (ageChartInstance) ageChartInstance.destroy();
         if (sexChartInstance) sexChartInstance.destroy();
         if (ethnicityChartInstance) ethnicityChartInstance.destroy();
         ageChartInstance = sexChartInstance = ethnicityChartInstance = null;
         // You might want to reset the canvas elements here if needed
    });
}

// --- Initial Setup ---
// Optional: Add event listener to ensure boundary layer loads before allowing drawing
boundarySource.on('change', function(evt){
    const source = evt.target;
    if (source.getState() === 'ready') {
        console.log('Atlanta boundary loaded.');
        // You could enable the draw button here if desired
        // drawButton.disabled = false;
    }
});

// Initially disable draw button until boundary loads? (Optional)
// drawButton.disabled = true;

console.log("Map and script initialized.");