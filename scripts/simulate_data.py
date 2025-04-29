import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point
import os # Added for potential file path operations

print("Starting simulation...")

# --- Configuration ---
# Target total points ~2700
NEW_CLUSTER_SIZE = 810 # Increased from 300
NEW_NOISE_N = 270      # Increased from 100
# --- Using the user's original output filename ---
OUTPUT_CSV_FILENAME = "data/pit_counts_individuals.csv"
# --- Ensure these paths are correct relative to where you run the script ---
BOUNDARY_SHP_PATH = "data/Atlanta_Boundary.shp"
TRACTS_GEOJSON_PATH = "data/atl_tracts.geojson"

# Ensure output directory exists
output_dir = os.path.dirname(OUTPUT_CSV_FILENAME)
if output_dir and not os.path.exists(output_dir):
    os.makedirs(output_dir)
    print(f"Created output directory: {output_dir}")

# --- Define Demographic Categories and Probabilities (ADJUST AS NEEDED) ---
# Ensure these probabilities accurately reflect the distributions you want to simulate
age_cats = ["0-17", "18-34", "35-54", "55-64", "65+"]
age_probs = [0.10, 0.35, 0.35, 0.15, 0.05] # Example probabilities, must sum to 1

sex_cats = ["Male", "Female", "Other/Unknown"]
sex_probs = [0.60, 0.38, 0.02] # Example probabilities, must sum to 1

ethnicity_cats = ["Black", "White", "Hispanic", "Asian", "Other/Unknown"]
ethnicity_probs = [0.65, 0.25, 0.05, 0.02, 0.03] # Example probabilities, must sum to 1

# --- Validate Probabilities ---
if not np.isclose(sum(age_probs), 1.0): print("WARNING: Age probabilities do not sum to 1!")
if not np.isclose(sum(sex_probs), 1.0): print("WARNING: Sex probabilities do not sum to 1!")
if not np.isclose(sum(ethnicity_probs), 1.0): print("WARNING: Ethnicity probabilities do not sum to 1!")
# ---

# 1) Load city boundary
print(f"Loading boundary from {BOUNDARY_SHP_PATH}...")
try:
    city = gpd.read_file(BOUNDARY_SHP_PATH).to_crs(epsg=4326)
    # Check if boundary loaded correctly and has geometry
    if city.empty or not hasattr(city.geometry, 'total_bounds'):
         raise ValueError("Boundary shapefile loaded but is empty or lacks geometry.")
    minx, miny, maxx, maxy = city.total_bounds
    print(f"Boundary loaded successfully. Bounds: ({minx:.4f}, {miny:.4f}) to ({maxx:.4f}, {maxy:.4f})")
except Exception as e:
    print(f"❌ Error loading boundary shapefile: {e}")
    exit(1) # Exit script if boundary fails to load

# 2) Define cluster centers (Keep these the same unless you want to change distribution)
cluster_centers = [
    (-84.385, 33.850),  # Buckhead area
    (-84.390, 33.775),  # Midtown / Downtown area
    (-84.355, 33.740),  # East Atlanta area
]
sigma = 0.005 # Standard deviation for cluster spread (adjust if needed)

# 3) Simulate points with demographics
print(f"Simulating points (Cluster Size: {NEW_CLUSTER_SIZE}, Noise Points: {NEW_NOISE_N})...")
all_point_data = [] # Store dictionaries for each simulated person
total_points_generated = 0
points_in_boundary = 0

# Simulate clustered points
for i, (lon0, lat0) in enumerate(cluster_centers):
    print(f"  Simulating cluster {i+1} centered at ({lon0:.4f}, {lat0:.4f})...")
    # Generate points around the center
    xs = np.random.normal(lon0, sigma, size=NEW_CLUSTER_SIZE)
    ys = np.random.normal(lat0, sigma, size=NEW_CLUSTER_SIZE)
    cluster_points_in = 0
    for x, y in zip(xs, ys):
        total_points_generated += 1
        p = Point(x, y)
        # Check if the point falls within the city boundary geometry
        if city.geometry.contains(p).any():
            # Assign demographics based on defined probabilities
            chosen_age = np.random.choice(age_cats, p=age_probs)
            chosen_sex = np.random.choice(sex_cats, p=sex_probs)
            chosen_ethnicity = np.random.choice(ethnicity_cats, p=ethnicity_probs)
            # Store data for this person
            all_point_data.append({
                'geometry': p,
                'age': chosen_age,
                'sex': chosen_sex,
                'ethnicity': chosen_ethnicity
            })
            points_in_boundary += 1
            cluster_points_in += 1
    print(f"    {cluster_points_in} points added from cluster {i+1} within boundary.")


# 4) Add uniform background noise with demographics
print(f"  Simulating {NEW_NOISE_N} background noise points...")
xs = np.random.uniform(minx, maxx, size=NEW_NOISE_N)
ys = np.random.uniform(miny, maxy, size=NEW_NOISE_N)
noise_points_in = 0
for x, y in zip(xs, ys):
    total_points_generated += 1
    p = Point(x, y)
    if city.geometry.contains(p).any():
        # Assign demographics
        chosen_age = np.random.choice(age_cats, p=age_probs)
        chosen_sex = np.random.choice(sex_cats, p=sex_probs)
        chosen_ethnicity = np.random.choice(ethnicity_cats, p=ethnicity_probs)
        # Store data for this person
        all_point_data.append({
            'geometry': p,
            'age': chosen_age,
            'sex': chosen_sex,
            'ethnicity': chosen_ethnicity
        })
        points_in_boundary += 1
        noise_points_in += 1
print(f"    {noise_points_in} noise points added within boundary.")

print(f"Total points generated (before boundary check): {total_points_generated}")
print(f"Total points generated within boundary: {points_in_boundary}")

# Check if any points were actually generated within the boundary
if points_in_boundary == 0:
    print("❌ ERROR: No points were generated within the city boundary. Check boundary file and cluster centers/spread.")
    exit(1)

# Create GeoDataFrame with attributes from the collected data
inc_with_attrs = gpd.GeoDataFrame(all_point_data, crs="EPSG:4326")

# 5) Spatial Join to assign Tract GEOID to each point
print(f"Loading tracts from {TRACTS_GEOJSON_PATH}...")
try:
    tracts = gpd.read_file(TRACTS_GEOJSON_PATH).to_crs(epsg=4326)
    # Ensure tracts have necessary columns
    if 'GEOID' not in tracts.columns or 'geometry' not in tracts.columns:
         raise ValueError("Tracts file missing required 'GEOID' or 'geometry' column.")
    print("Tracts loaded successfully.")
except Exception as e:
    print(f"❌ Error loading tracts file: {e}")
    exit(1)

print("Performing spatial join (assigning points to tracts)...")
# Keep only necessary columns from tracts to avoid duplicates after join
tracts_simple = tracts[["GEOID", "geometry"]]
# Perform the join using 'within' predicate
joined = gpd.sjoin(inc_with_attrs, tracts_simple, how="left", predicate="within")
print("Spatial join complete.")

# Check for points that didn't join
unjoined_count = joined['GEOID'].isnull().sum()
if unjoined_count > 0:
    print(f"⚠️ WARNING: {unjoined_count} points did not fall within any tract. These points will be excluded from the output CSV.")
    # Drop points that didn't join to avoid issues loading null GEOID
    joined = joined.dropna(subset=['GEOID'])
    print(f"  {len(joined)} points remaining after dropping unjoined.")

if joined.empty:
    print("❌ ERROR: No points remained after spatial join. Check tract coverage and point locations.")
    exit(1)

# 6) Prepare and Save Individual Data for Database Loading
print("Preparing individual records for saving...")
# Select only the columns needed for the 'demo.pit_counts' table
# Ensure column names match your database table exactly: GEOID, age, sex, ethnicity
output_df = joined[['GEOID', 'age', 'sex', 'ethnicity']]

# Save to CSV - this file will be loaded into demo.pit_counts
print(f"Writing {len(output_df)} individual records to {OUTPUT_CSV_FILENAME}...")
try:
    output_df.to_csv(OUTPUT_CSV_FILENAME, index=False)
    print(f"Successfully wrote CSV file.")
except Exception as e:
    print(f"❌ Error writing CSV file: {e}")
    exit(1)

print("Script finished successfully.")
