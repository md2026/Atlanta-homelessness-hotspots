import geopandas as gpd

# 1. Read GA tracts and filter to Fulton & DeKalb
tracts = gpd.read_file("data/tl_2024_13_tract.shp")
tracts = tracts[tracts["COUNTYFP"].isin(["121","089"])]

# 2. Read your Atlanta boundary shapefile
city = gpd.read_file("data/Atlanta_Boundary.shp").to_crs(tracts.crs)

# 3. Clip to the city limits
atl_tracts = gpd.overlay(tracts, city, how="intersection")

# 4. Write out the clipped tracts
atl_tracts.to_file("data/atl_tracts.geojson", driver="GeoJSON")
print(f"Wrote {len(atl_tracts)} tracts to data/atl_tracts.geojson")
