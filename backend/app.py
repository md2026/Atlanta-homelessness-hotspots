# ~/projects/hotspot_atl/backend/app.py

import os
import json
import logging # For better logging
from flask import Flask, request, jsonify
from flask_cors import CORS # Make sure this import is here
import psycopg2
import psycopg2.extras
from scipy.stats import chisquare # Import chi-squared test
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv() # Load environment variables from .env file (optional but good practice)

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# Explicitly configure CORS to allow all origins for API routes
# Replace "*" with your frontend origin (e.g., "http://localhost:8000") for better security in production
cors = CORS(app, resources={r"/api/*": {"origins": os.getenv("FRONTEND_URL", "*")}})
logging.info(f"--- Flask-CORS initialized for origins: {os.getenv('FRONTEND_URL', '*')} ---")

# --- DATABASE CONFIGURATION ---
# Use environment variables with defaults
DB_NAME     = os.getenv("DB_NAME",     "atl")
DB_USER     = os.getenv("DB_USER",     "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234") # Be careful with default passwords
DB_HOST     = os.getenv("DB_HOST",     "localhost")
DB_PORT     = os.getenv("DB_PORT",     "5432")

# --- Database Connection Function ---
def get_db_connection():
    """Establishes connection to the PostGIS database."""
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        logging.info(f"Database connection successful (DB: {DB_NAME}, User: {DB_USER})")
        return conn
    except psycopg2.OperationalError as e:
        logging.error(f"❌ Database connection failed: {e}")
        return None # Return None on failure
    except Exception as e:
        logging.error(f"❌ Unexpected error connecting to database: {e}")
        return None

# --- Global Variable for City-Wide Proportions ---
CITY_WIDE_PROPORTIONS = {}
CITY_WIDE_CALCULATED = False # Flag to check if calculation was attempted

# --- Function to Calculate City-Wide Proportions ---
def calculate_city_wide_proportions():
    """
    Calculates the overall demographic proportions for the entire dataset
    based on the user's schema (COUNT(*) from demo.pit_counts).
    Stores the results in the global CITY_WIDE_PROPORTIONS dictionary.
    """
    global CITY_WIDE_PROPORTIONS, CITY_WIDE_CALCULATED
    if CITY_WIDE_CALCULATED: # Don't recalculate if already done
        logging.info("City-wide proportions already calculated.")
        return

    conn = None
    # --- Schema Configuration (Match user's app.py) ---
    pit_counts_table = "demo.pit_counts"
    tracts_table = "demo.tracts"
    join_column = "geoid" # Column used to join pit_counts and tracts
    # Define the demographic categories and their corresponding column names in pit_counts
    categories_config = {
        'age': 'age',
        'sex': 'sex',
        'ethnicity': 'ethnicity'
    }
    # --- End of Schema Configuration ---

    proportions = {f'by_{key}': {} for key in categories_config.keys()}
    logging.info("Attempting to calculate city-wide proportions...")

    try:
        conn = get_db_connection()
        if conn is None:
            raise ConnectionError("Failed to get DB connection for proportion calculation.")

        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            for key, column_name in categories_config.items():
                # Query to get total count for each group in the category across the entire dataset
                # Assumes demo.pit_counts represents the entire relevant population (e.g., all of Atlanta)
                query = f"""
                    SELECT {column_name}, COUNT(*) AS total_count
                    FROM {pit_counts_table}
                    WHERE {column_name} IS NOT NULL -- Exclude null category values
                    GROUP BY {column_name};
                """
                logging.info(f"Executing city-wide proportion query for category: {key}")
                cur.execute(query)
                results = cur.fetchall()

                # Calculate total population for this category
                category_total = sum(row['total_count'] for row in results if row['total_count'] is not None)
                logging.info(f"Total city-wide count for category '{key}': {category_total}")

                # Calculate proportion for each group
                prop_dict = {}
                if category_total > 0:
                    for row in results:
                        group_name = row[column_name]
                        count = row['total_count']
                        if group_name is not None and count is not None:
                            prop_dict[str(group_name)] = count / category_total # Use string keys
                else:
                    logging.warning(f"City-wide category '{key}' has zero total count. Proportions cannot be calculated.")

                proportions[f'by_{key}'] = prop_dict # Store proportions

        CITY_WIDE_PROPORTIONS = proportions
        logging.info(f"Successfully calculated City-Wide Proportions: {json.dumps(CITY_WIDE_PROPORTIONS, indent=2)}")

    except (Exception, psycopg2.DatabaseError, ConnectionError) as error:
        logging.error(f"❌ Error calculating city-wide proportions: {error}")
        CITY_WIDE_PROPORTIONS = {} # Reset to empty on error to indicate failure
    finally:
        CITY_WIDE_CALCULATED = True # Mark calculation as attempted
        if conn is not None:
            conn.close()
            logging.info("Database connection closed after calculating proportions.")

# --- DEMOGRAPHICS ENDPOINT ---
@app.route("/api/demographics", methods=["POST"])
def get_demographics_with_stats():
    """
    API endpoint to get demographic counts (using COUNT(*)) and Chi-Squared results
    for a user-drawn polygon compared to city-wide averages.
    """
    global CITY_WIDE_PROPORTIONS, CITY_WIDE_CALCULATED
    logging.info("Received request for /api/demographics")

    # --- Ensure city-wide proportions are calculated (or attempted) ---
    if not CITY_WIDE_CALCULATED:
        calculate_city_wide_proportions()

    # --- Validate Request ---
    body = request.get_json()
    if not body or "geometry" not in body:
        logging.warning("Request missing geometry")
        return jsonify({"error": "Missing geometry in request body"}), 400

    geometry_data = body['geometry']
    if not isinstance(geometry_data, dict) or 'type' not in geometry_data or 'coordinates' not in geometry_data:
        logging.warning(f"Invalid GeoJSON geometry format received: {geometry_data}")
        return jsonify(error="Invalid GeoJSON geometry format"), 400

    # Stringify the GeoJSON geometry for ST_GeomFromGeoJSON
    try:
        geom_json = json.dumps(geometry_data)
    except TypeError as e:
        logging.error(f"Could not serialize received geometry to JSON: {e}")
        return jsonify(error="Invalid geometry data could not be processed"), 400

    # --- Check if city-wide proportions are available ---
    if not CITY_WIDE_PROPORTIONS or not any(CITY_WIDE_PROPORTIONS.values()):
         logging.error("City-wide proportions not available. Cannot perform statistical analysis.")
         # Proceed without stats, or return an error? Let's proceed but note it.
         stats_available = False
    else:
         stats_available = True


    # --- Database Interaction ---
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Database connection failed"}), 500

    # --- Schema Configuration (Match user's app.py) ---
    pit_counts_table = "demo.pit_counts"
    tracts_table = "demo.tracts"
    join_column = "geoid"
    tract_geom_column = "geom" # Geometry column in tracts table
    srid = 4326 # SRID of your geometry data (e.g., 4326 for WGS84)
    categories_config = {
        'age': 'age',
        'sex': 'sex',
        'ethnicity': 'ethnicity'
    }
    # --- End of Schema Configuration ---

    results = {'counts': {}, 'stats': {}} # Structure to hold counts and stats
    observed_counts_by_category = {key: {} for key in categories_config.keys()}
    total_in_polygon = 0

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # --- Step 1: Get Observed Counts within Polygon (using COUNT(*)) ---
            polygon_sql_geom = f"ST_SetSRID(ST_GeomFromGeoJSON(%s), {srid})"

            for key, column_name in categories_config.items():
                query_observed = f"""
                    SELECT pc.{column_name}, COUNT(*) AS observed_count
                    FROM {pit_counts_table} pc
                    JOIN {tracts_table} t ON pc.{join_column} = t.{join_column}
                    WHERE ST_Intersects(t.{tract_geom_column}, {polygon_sql_geom})
                      AND pc.{column_name} IS NOT NULL -- Exclude null categories
                    GROUP BY pc.{column_name};
                """
                logging.info(f"Executing query for observed counts (Category: {key})")
                try:
                    cur.execute(query_observed, (geom_json,))
                    observed_results = cur.fetchall()
                except psycopg2.Error as db_err:
                    logging.error(f"Database error querying observed counts for {key}: {db_err}")
                    raise # Re-raise to be caught by the outer try-except

                temp_counts = {}
                for row in observed_results:
                    group_name = str(row[column_name]) # Use string keys
                    count = row['observed_count']
                    if group_name and count is not None:
                        temp_counts[group_name] = count

                observed_counts_by_category[key] = temp_counts
                results['counts'][f'by_{key}'] = temp_counts # Add to results under 'counts' key
                logging.info(f"Observed counts for {key}: {temp_counts}")

            # Calculate total_in_polygon based on one of the categories (assuming consistency)
            # Or run a separate total query like the user originally had
            query_total = f"""
                 SELECT COUNT(pc.*) AS total
                 FROM {pit_counts_table} pc
                 JOIN {tracts_table} t ON pc.{join_column} = t.{join_column}
                 WHERE ST_Intersects(t.{tract_geom_column}, {polygon_sql_geom});
            """
            cur.execute(query_total, (geom_json,))
            total_row = cur.fetchone()
            total_in_polygon = total_row["total"] or 0
            results['counts']['total_homeless'] = total_in_polygon # Add total to results
            logging.info(f"Total individuals found in polygon: {total_in_polygon}")


            # --- Step 2: Perform Chi-Squared Test for each category ---
            if total_in_polygon > 0 and stats_available:
                logging.info("Performing Chi-Squared tests...")
                for key, column_name in categories_config.items():
                    observed = []
                    expected = []

                    # Get the expected proportions for this category (city-wide)
                    expected_proportions = CITY_WIDE_PROPORTIONS.get(f'by_{key}', {})
                    if not expected_proportions:
                        logging.warning(f"No city-wide proportions found for category '{key}'. Skipping test.")
                        results['stats'][key] = {'error': f"City-wide proportions for {key} unavailable."}
                        continue

                    # Get the observed counts for this category (within polygon)
                    observed_data = observed_counts_by_category.get(key, {})

                    # Prepare lists for chisquare function, ensuring order matches city-wide keys
                    category_labels = list(expected_proportions.keys()) # Use city-wide labels as the reference

                    for label in category_labels:
                        # Observed count for this label (default to 0 if not found in polygon)
                        observed_count = observed_data.get(label, 0)
                        observed.append(observed_count)

                        # Expected count = city_proportion * total_in_polygon
                        expected_count = expected_proportions.get(label, 0) * total_in_polygon
                        expected.append(expected_count)

                    # Filter out categories where expected count is effectively zero
                    valid_indices = [i for i, e in enumerate(expected) if e > 1e-9]
                    filtered_observed = [observed[i] for i in valid_indices]
                    filtered_expected = [expected[i] for i in valid_indices]

                    # Check conditions for the test
                    if len(filtered_observed) < 2:
                        logging.warning(f"Not enough categories with expected counts > 0 for Chi-squared test (Category: {key})")
                        results['stats'][key] = {'error': "Not enough data or categories with expected counts > 0."}
                        continue
                    # Check if sums match (within tolerance) - important for chisquare
                    sum_obs = sum(filtered_observed)
                    sum_exp = sum(filtered_expected)
                    if abs(sum_obs - sum_exp) > 1e-6 * max(sum_obs, 1): # Use relative tolerance, avoid division by zero
                         logging.warning(f"Sum of observed ({sum_obs}) != sum of expected ({sum_exp}) for {key}. Check proportion calculation or filtering. Skipping test.")
                         results['stats'][key] = {'error': "Internal calculation mismatch (observed vs expected totals)."}
                         continue

                    logging.info(f"Running chisquare for {key}: Observed={filtered_observed}, Expected={filtered_expected}")
                    try:
                        # ddof=0 for goodness-of-fit when expected frequencies are based on external proportions
                        chisq_stat, p_value = chisquare(f_obs=filtered_observed, f_exp=filtered_expected, ddof=0)
                        # Handle potential NaN results from chisquare if inputs are problematic
                        if chisq_stat != chisq_stat or p_value != p_value: # Check for NaN
                             raise ValueError("Chi-squared calculation resulted in NaN.")
                        results['stats'][key] = {'statistic': chisq_stat, 'p_value': p_value}
                        logging.info(f"Chi-squared result for {key}: Stat={chisq_stat}, P-value={p_value}")
                    except ValueError as e:
                        logging.error(f"Chi-squared calculation error for {key}: {e}")
                        results['stats'][key] = {'error': f"Chi-squared calculation error: {e}"}

            elif not stats_available:
                 results['stats'] = {'message': "City-wide proportions unavailable, statistical comparison skipped."}
            elif total_in_polygon == 0:
                logging.info("No population found in the selected area. Skipping Chi-squared tests.")
                results['stats'] = {'message': "No population found in the selected area."}


    except psycopg2.Error as e: # Catch specific DB errors
        conn.rollback()
        logging.error(f"❌ Query failed (psycopg2 Error): {e}")
        error_detail = str(e).split('\n')[0] # Get first line of error
        return jsonify({"error": "DB query failed", "details": error_detail}), 500
    except Exception as e: # Catch other potential errors
        conn.rollback()
        logging.error(f"❌ Query failed (General Exception): {e}", exc_info=True) # Log traceback
        return jsonify({"error": "Processing failed", "details": str(e)}), 500
    finally:
        if conn:
            conn.close()
            logging.info("Database connection closed for request.")

    # Final check before returning JSON
    try:
        json.dumps(results)
        return jsonify(results)
    except TypeError as e:
        logging.error(f"❌ Error serializing results to JSON: {e}")
        logging.error(f"Problematic data structure: {results}")
        # Return only the parts that are serializable if possible, or a generic error
        safe_results = {"counts": results.get("counts", {}), "stats": {"error": "Result serialization failed"}}
        return jsonify(safe_results), 500


# --- Run the app ---
if __name__ == "__main__":
    logging.info("--- Starting Flask Backend Server ---")
    logging.info(f"Attempting to connect to DB: host={DB_HOST}, port={DB_PORT}, dbname={DB_NAME}, user={DB_USER}")
    # Calculate proportions once on startup (best effort)
    calculate_city_wide_proportions()
    # Port 5001 is used to avoid conflict with default Flask port 5000 or common frontend port 8000
    app.run(host='0.0.0.0', port=5001, debug=True) # Use 0.0.0.0 to be accessible on network if needed
