# ==========================================
# WINDOWS SSL BUG PATCH (Place at absolute top)
# ==========================================
import ssl
try:
    import certifi
    orig_load_default_certs = ssl.SSLContext.load_default_certs
    def patched_load_default_certs(self, purpose=ssl.Purpose.SERVER_AUTH):
        try:
            return orig_load_default_certs(self, purpose)
        except Exception:
            # If Windows store has corrupt certs, fallback safely to certifi CA bundle
            return self.load_verify_locations(cafile=certifi.where())
    ssl.SSLContext.load_default_certs = patched_load_default_certs
# ==========================================
except ImportError:
    pass


import streamlit as st
from google.cloud import bigquery
import pandas as pd
import os
from dotenv import load_dotenv
from agent import run_agent_query

# Load the environment variables from your local .env file
load_dotenv()

# ---- 1. Page Configuration ----
st.set_page_config(
    page_title="GCP River Sensor Analytics",
    page_icon="🌊",
    layout="wide"
)


# ---- 2. BigQuery Data Fetching Logic (with caching for performance) ----
@st.cache_data
def get_sensor_locations():
    # Pull the project ID securely from the environment variables
    project_id = os.getenv("GCP_PROJECT_ID")

    # Initialize the client using that variable
    client = bigquery.Client(project=project_id)

    # Use the variable dynamically inside a SQL string using an f-string
    query = f"""
        SELECT 
            site_name,
            latitude,
            longitude
        FROM `{project_id}.lake_data.sensor_logs`
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        GROUP BY site_name, latitude, longitude
    """

    query_job = client.query(query)
    return query_job.to_dataframe()

# Run the function to fetch data
try:
    sensor_df = get_sensor_locations()

# Fallback dummy data so your app layout doesn't crash while troubleshooting schemas
except Exception as e:
    st.error(f"Failed to connect to BigQuery: {e}")
    sensor_df = pd.DataFrame({
        'site_name': ['Sensor Alpha', 'Sensor Beta'],
        'latitude': [40.43, 40.45],
        'longitude': [-111.89, -111.85]
    })


@st.cache_data
def get_sensor_trends():
    """
    Pulls historical data for all parameters over the past 7 days.
    """
    project_id = os.getenv("GCP_PROJECT_ID")
    client = bigquery.Client(project=project_id)

    query = f"""
            SELECT 
                date,
                site_name,
                value,
                param_code
            FROM `{project_id}.lake_data.sensor_logs`
            WHERE CAST(date AS DATETIME) >= DATETIME_SUB(CURRENT_DATETIME(), INTERVAL 7 DAY) AND value IS NOT NULL
            ORDER BY date ASC
            """

    query_job = client.query(query)
    return query_job.to_dataframe()

# Run the function to fetch historical trends
try:
    trends_df = get_sensor_trends()
except Exception as e:
    st.error(f"Failed to fetch trend data from BigQuery: {e}")
    trends_df = pd.DataFrame(columns=['date', 'site_name', 'value', 'param_code'])


# ---- 3. Main App Header ----
st.title("🌊 Real-Time River Sensor Analytics & AI Agent")
st.markdown("""
This dashboard monitors real-time environmental sensor metrics stored in **Google BigQuery** and utilizes a **LangChain SQL Agent** powered by **Gemini 2.5 Flash** to answer natural language questions.
""")

st.divider()


# ---- 4. Create Two Layout Columns (Map, LangChain prompt) ----
col1, col2 = st.columns([3, 2])

with col1:
    st.header("📊 Sensor Telemetry & Map")

    # Display the interactive map using the data pulled from BigQuery
    st.subheader("📍 Active Monitoring Stations")
    st.map(sensor_df, latitude='latitude', longitude='longitude', zoom=6)

    # view the raw data table underneath the map
    st.dataframe(sensor_df, use_container_width=True)

    st.divider()

    # ---- Interactive Analytics Section ----
    st.subheader("📈 Historical Parameter Trends")

    if not trends_df.empty:
        # 1. Extract unique param_codes to populate the dropdown menu
        unique_params = sorted(trends_df['param_code'].unique().tolist())

        # 2. Create the Streamlit selectbox widget
        selected_param = st.selectbox(
            label="Select a parameter code to plot:",
            options=unique_params,
            index=0  # Defaults to the first item in the list
        )

        # 3. Filter the dataframe instantly using the user's dropdown choice
        filtered_df = trends_df[trends_df['param_code'] == selected_param]

        if not filtered_df.empty:
            # Pivot the filtered data so rows are 'date', columns are 'site_name', and values are 'value'
            chart_data = filtered_df.pivot(index='date', columns='site_name', values='value')

            # Display the line chart matching the selected parameter
            st.line_chart(chart_data, use_container_width=True)
        else:
            st.warning(f"No data available to plot for parameter code: {selected_param}")

    else:
        st.warning("No historical trend data found to plot.")

with col2:
    st.header("🤖 Ask the Data Agent")
    st.write("Type a natural language question below to query the BigQuery database dynamically.")

    user_question = st.text_input(
        label="Enter your query:",
        placeholder="e.g., Which site had the highest reading yesterday?"
    )

    if user_question:
        # Use st.spinner to create a clean loading animation while the LLM thinks and runs SQL
        with st.spinner("🤖 Agent is thinking, writing SQL, and fetching data..."):
            try:
                # Fire off the query to your LangChain logic!
                agent_response = run_agent_query(user_question)

                # Display the beautiful final answer
                st.success("✨ Answer:")

                if isinstance(agent_response, str) and "text" in agent_response:
                    # Quick visual placeholder clean up if it's printing raw JSON strings
                    import json

                    try:
                        # If it's a valid JSON string masquerading as text, parse and print just the message
                        parsed = json.loads(agent_response)
                        if isinstance(parsed, list) and len(parsed) > 0:
                            st.write(parsed[0].get("text", agent_response))
                    except Exception:
                        st.write(agent_response)

                st.write(agent_response)

            except Exception as e:
                st.error(f"An error occurred while executing the agent: {e}")
