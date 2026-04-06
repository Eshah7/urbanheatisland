import marimo

__generated_with = "0.22.0"
app = marimo.App(width="medium")


@app.cell
def _():
    # Import Packages
    import marimo as mo
    import ee
    import pandas as pd
    import matplotlib.pyplot as plt
    import folium
    import plotly.express as px
    ee.Initialize(project="boxwood-valve-473515-t3")

    # Check if the connection works
    print(ee.String("Connection successful").getInfo())
    return ee, mo, pd, px


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Visualizing Toronto with Earth Engine Data — Summer 2024
    """)
    return


@app.cell
def _(ee):
    # Toronto bounding box
    toronto = ee.Geometry.Rectangle([-79.64, 43.58, -79.12, 43.86])

    # Search for Landsat 8/9 scenes, summer 2024, low cloud cover
    landsat = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .filterBounds(toronto)
        .filterDate("2024-06-01", "2024-08-31")
        .filter(ee.Filter.lt("CLOUD_COVER", 10))
        .select(["ST_B10", "SR_B4", "SR_B5"])
    )

    print(f"Scenes found: {landsat.size().getInfo()}")
    return landsat, toronto


@app.cell
def _(landsat, toronto):
    # Convert each image into celsius
    def compute_lst(image):
        lst = (
            image.select("ST_B10")
            .multiply(0.00341802)
            .add(149.0)
            .subtract(273.15)
            .rename("LST_celsius")
        )
        ndvi = image.normalizedDifference(["SR_B5", "SR_B4"]).rename("NDVI")
        return lst.addBands(ndvi).copyProperties(image, ["system:time_start"])


    lst_collection = landsat.map(compute_lst)
    lst_median = lst_collection.median().clip(toronto)
    return (lst_median,)


@app.cell
def _(lst_median, pd, toronto):
    sample = lst_median.sample(region=toronto, scale=100, numPixels=5000, seed=42, geometries=True)
    features = sample.getInfo()["features"]

    df = pd.DataFrame([{
        "lon": f["geometry"]["coordinates"][0],
        "lat": f["geometry"]["coordinates"][1],
        "lst_celsius": f["properties"]["LST_celsius"],
        "ndvi": f["properties"]["NDVI"],
    } for f in features]).dropna()
    return (df,)


@app.cell
def _(df, mo):
    temp_df = mo.sql(
        f"""
        SELECT * FROM
        df
        """
    )
    return (temp_df,)


@app.cell
def _(mo, temp_df):
    _df = mo.sql(
        f"""
        select avg(lst_celsius), min(lst_celsius), max(lst_celsius), count(*) as pixels
        from temp_df
        """
    )
    return


@app.cell
def _(mo, temp_df):
    ndvi_df = mo.sql(
        f"""
        SELECT
            CASE
                WHEN ndvi < 0.01  THEN 'Water'
                WHEN ndvi < 0.2  THEN 'Urban / Pavement'
                WHEN ndvi < 0.4  THEN 'Sparse Vegetation'
                ELSE 'Dense Vegetation'
            END AS land_type, *
        FROM temp_df
        """
    )
    return (ndvi_df,)


@app.cell
def _(mo, ndvi_df):
    filtered_df = mo.sql(
        f"""
        select * from ndvi_df
        where land_type != 'Water'
        and lst_celsius > 20
        """
    )
    return (filtered_df,)


@app.cell
def _(filtered_df):
    import os

    # mo.sql() returns a Polars DataFrame — round and select columns, then export via pandas
    export = (
        filtered_df
        .select(["lon", "lat", "lst_celsius", "ndvi", "land_type"])
        .with_columns([
            __import__("polars").col("lon").round(5),
            __import__("polars").col("lat").round(5),
            __import__("polars").col("lst_celsius").round(2),
            __import__("polars").col("ndvi").round(4),
            __import__("polars").col("land_type").cast(__import__("polars").Utf8),
        ])
    )

    os.makedirs("data", exist_ok=True)
    export.write_json("data/toronto_uhi_2024.json", row_oriented=True)
    print(f"Exported {len(export)} rows to data/toronto_uhi_2024.json")
    return


if __name__ == "__main__":
    app.run()
