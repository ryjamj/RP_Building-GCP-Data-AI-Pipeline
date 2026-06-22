import os
import pandas as pd
import requests
import functions_framework
from google.cloud import bigquery

# 1. Initialize the BigQuery Client tool
bq_client = bigquery.Client()

# 2. Define your destination table location
TABLE_REF = "lake-sensor-analytics.lake_data.sensor_logs"


def fetch_usgs_to_dataframe(url):
    """
    Your exact flattening logic to extract USGS nested JSON into a clean DataFrame.
    """
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Error fetching data: {response.status_code}")
        return None

    data = response.json()
    time_series_list = data.get("value", {}).get("timeSeries", [])
    all_records = []

    for ts in time_series_list:
        # --- High Level / site info ---
        site_info = ts.get("sourceInfo", {})
        site_name = site_info.get("siteName")
        site_code = site_info.get("siteCode", [{}])[0].get("value")

        # --- geolocation info ---
        geo_location = site_info.get("geoLocation", {}).get("geogLocation", {})
        srs = geo_location.get("srs")
        latitude = geo_location.get("latitude")
        longitude = geo_location.get("longitude")

        # --- variable info ---
        variable_info = ts.get("variable", {})
        param_code = variable_info.get("variableCode", [{}])[0].get("value")
        param_desc = variable_info.get("variableDescription")
        unit = variable_info.get("unit", {}).get("unitCode")

        values_list = ts.get("values", [{}])[0].get("value", [])

        for val in values_list:
            date_time = val.get("dateTime")
            measurement = val.get("value")
            qualifiers = val.get("qualifiers", [])

            all_records.append({
                "site_code": site_code,
                "site_name": site_name,
                "param_code": param_code,
                "param_description": param_desc,
                "date": date_time,
                "value": measurement,
                "unit": unit,
                "qualification_code": ",".join(qualifiers),
                "srs": srs,
                "latitude": latitude,
                "longitude": longitude,
            })

    df = pd.DataFrame(all_records)
    if df.empty:
        print("No data found for the given parameters.")
        return df

    # Clean data types so BigQuery accepts them smoothly
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    return df


@functions_framework.http
def ingest_sensor_data(request):
    """
    The main entry point that Google Cloud triggers.
    """
    try:
        # The URL fetching Utah lake data for May 2026
        url = "https://waterservices.usgs.gov/nwis/dv/?format=json&stateCd=ut&startDT=2026-05-01&endDT=2026-05-31&siteStatus=all&siteType=LK"

        # Run your dataframe extraction logic
        df_sensor_data = fetch_usgs_to_dataframe(url)

        if df_sensor_data is None or df_sensor_data.empty:
            return {"status": "success", "message": "No new data found to upload."}, 200

        # Configure the BigQuery upload settings to APPEND new rows to the existing table
        job_config = bigquery.LoadJobConfig(
            write_disposition="WRITE_APPEND"
        )

        print(f"Uploading {len(df_sensor_data)} rows to BigQuery...")

        # Stream the entire Pandas DataFrame directly to BigQuery
        job = bq_client.load_table_from_dataframe(
            df_sensor_data, TABLE_REF, job_config=job_config
        )
        job.result()  # Wait for the database upload process to finish

        print(f"Successfully loaded data into {TABLE_REF}")
        return {"status": "success", "message": f"Successfully appended {len(df_sensor_data)} rows."}, 200

    except Exception as e:
        print(f"Execution failed: {str(e)}")
        return {"status": "error", "message": str(e)}, 500