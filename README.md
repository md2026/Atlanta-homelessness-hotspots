# Interactive Homelessness Demographics Explorer for Atlanta

Final project for CSC 4730 Data Visualization by Matt Dawit and Dhanush Reddy Pucha.

## Overview

This project provides an interactive web application to explore simulated homeless demographics within user-defined areas of Atlanta. Users can draw polygons on a map to see demographic breakdowns (age, sex, ethnicity) and statistical comparisons (Chi-Squared test) against city-wide averages for the selected area.

## Features

* Interactive map using OpenLayers displaying Atlanta boundary.
* Draw custom polygons to select areas of interest.
* Dynamic charts (Chart.js) showing demographic counts for the selected area.
* Statistical analysis (Chi-Squared Goodness-of-Fit) comparing selected area demographics to city-wide averages.
* Click on previously drawn polygons to recall their data.
* Backend powered by Flask, PostGIS, and Python (SciPy for stats).

## Setup and Running

**Prerequisites:**

* Python 3.x
* PostgreSQL with PostGIS extension enabled
* Git (for cloning)

**Backend Setup:**

1.  **Clone:** `git clone <your-repo-url>` (Replace with actual URL after creating repo)
2.  **Navigate:** `cd hotspot_atl/backend`
3.  **Create Virtual Environment:** `python3 -m venv venv` (or `python -m venv venv`)
4.  **Activate:** `source venv/bin/activate` (Linux/macOS) or `.\venv\Scripts\activate` (Windows)
5.  **Install Dependencies:** `pip install -r requirements.txt`
6.  **Database Setup:**
    * Ensure PostgreSQL/PostGIS is running.
    * Create a database (e.g., `atl`).
    * Connect to the database using `psql` or another tool.
    * Run the `setup.sql` script provided in the repository root to enable PostGIS, create the `demo` schema, and create the `demo.tracts` and `demo.pit_counts` tables with appropriate columns and spatial indexes.
        * Example: `psql -d atl -U your_db_user -f setup.sql`
    * **Load Data:** Follow the instructions within `setup.sql` or below to load data:
        * Load your census tract boundaries (e.g., from `atl_tracts.geojson` or shapefile) into the `demo.tracts` table. Ensure the `geoid` and `geom` (SRID 4326) columns are populated. (Tools like `ogr2ogr` or GIS software can be used).
        * Run the simulation script (`scripts/simulate_data.py`) if you haven't already to generate `data/pit_counts_individuals.csv`.
        * Load the generated `data/pit_counts_individuals.csv` into the `demo.pit_counts` table using the `psql \copy` command (see example in `setup.sql`).
7.  **Environment Variables:** Create a `.env` file in the `backend` directory with your database credentials:
    ```dotenv
    DB_HOST=your_db_host
    DB_NAME=atl
    DB_USER=your_db_user
    DB_PASSWORD=your_db_password
    DB_PORT=5432
    FRONTEND_URL=http://localhost:8000
    ```
8.  **Run Backend:** `python app.py` (Server will run on port 5001 by default)

**Frontend Setup:**

1.  **Navigate:** `cd ../frontend` (from backend) or `cd hotspot_atl/frontend` (from main project dir)
2.  **Serve Files:** Run a simple HTTP server: `python -m http.server 8000` (or `python3 ...`)
3.  **Access:** Open your browser to `http://localhost:8000`

## Data

* The application requires `CityBoundary.geojson` in the `frontend/data/` directory (included in repo).
* The backend requires census tracts (`demo.tracts`) and simulated point-in-time counts (`demo.pit_counts`) loaded into the PostGIS database. See `setup.sql` for table structure and loading instructions.
* The simulation script (`scripts/simulate_data.py`) can be used to generate the `data/pit_counts_individuals.csv` file needed for `demo.pit_counts`. Original shapefiles/tract data used by the simulation script are not included in the repository due to size but can be obtained from sources like the US Census TIGER/Line shapefiles.

## Presentation

* The final presentation slides (`DataVis-2.pdf`) are included in the repository root.


