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
    # Visualizing Toronto with Earth Engine Data
    """)
    return


@app.cell
def _(ee):
    # Toronto bounding box
    toronto = ee.Geometry.Rectangle([-79.64, 43.58, -79.12, 43.86]) #Add the long/lat

    # Search for Landsat 8/9 scenes, summer 2023, low cloud cover
    landsat = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .filterBounds(toronto)
        .filterDate("2023-06-01", "2023-08-31")
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
def _(df, px):
    fig = px.scatter_map(
        df,
        lat="lat",
        lon="lon",
        color="lst_celsius",
        color_continuous_scale="RdYlBu_r",
        range_color=[10, 50],
        zoom=9.5,
        title="<b>Toronto Land Surface Temperature during Summer 2023</b>",
        labels={"lst_celsius": "LST (°C)"},
        opacity=0.85,
        size_max=5,
        hover_data={"ndvi": ":.3f", "lst_celsius": ":.1f", "lat": ":.4f", "lon": ":.4f"}
    )

    fig.update_traces(marker=dict(size=4))
    fig.show()
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
def _(filtered_df, px):
    fig2 = px.scatter(
        filtered_df,
        x="ndvi",
        y="lst_celsius",
        color="lst_celsius",
        color_continuous_scale="RdYlBu_r",
        range_color=[10, 50],
        labels={"ndvi": "NDVI (vegetation)", "lst_celsius": "LST (°C)"},
        title="<b>Vegetation vs Temperature — Toronto Summer 2023</b>",
        opacity=0.5,
    )
    fig2.show()
    return


@app.cell
def _(filtered_df, px):
    fig3 = px.scatter_map(
        filtered_df,
        lat="lat",
        lon="lon",
        color="ndvi",
        color_continuous_scale="RdYlGn",  # red = no vegetation, green = lots
        zoom=9.5,
        title="<b>Toronto NDVI (Normalized Difference Vegetation Index) during Summer 2023</b>",
        labels={"ndvi": "NDVI"},
        opacity=0.85,
    )
    fig3.update_traces(marker=dict(size=4))
    fig3.show()
    return


if __name__ == "__main__":
    app.run()
