import streamlit as st
import pandas as pd
import os
from supabase import create_client, Client
from datetime import datetime
import altair as alt

# --- Supabase Connection Setup ---
# Credentials are read from environment variables, which Modal will inject via the Secret
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TABLE_NAME = "demographics_data" # Ensure this matches your loader.py table name

def init_supabase_client() -> Client:
    """Initializes the Supabase client."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Supabase credentials not found. Please ensure SUPABASE_URL and SUPABASE_KEY are set in your Modal Secret.")
        st.stop()
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Data Fetching ---
@st.cache_data(ttl=600) # Cache the data for 10 minutes
def get_data(client: Client):
    """Fetches all data from the Supabase table."""
    try:
        # Fetch data ordered by the most recently extracted records
        response = client.table(TABLE_NAME).select("*").order("extracted_at", desc=True).execute()
        
        # Check if response data is valid
        if response.data:
            df = pd.DataFrame(response.data)
            
            # Convert rates to numeric, setting errors to NaN
            df['marriage_rate'] = pd.to_numeric(df['marriage_rate'], errors='coerce')
            df['divorce_rate'] = pd.to_numeric(df['divorce_rate'], errors='coerce')
            
            # Drop rows where both rates are null, as they are not useful for visualization
            df.dropna(subset=['marriage_rate', 'divorce_rate'], how='all', inplace=True)
            
            return df
        else:
            st.warning("No data found in the Supabase table.")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Error fetching data from Supabase: {e}")
        return pd.DataFrame()

# --- Streamlit UI and Visualization ---
def run_app():
    st.set_page_config(layout="wide", page_title="Global Demographics Dashboard")

    st.title("🌎 Global Marriage and Divorce Rate Analysis")
    st.caption(f"Data scraped from the web, structured by LLM, and loaded into Supabase. Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize client and fetch data
    supabase_client = init_supabase_client()
    data_df = get_data(supabase_client)

    if data_df.empty:
        st.info("The dashboard is ready, but the database is empty or connection failed.")
        return
        
    st.markdown("---")

    # --- Sidebar Filters ---
    st.sidebar.header("Data Filters")
    
    # Year filter
    min_year = int(data_df['year'].min()) if 'year' in data_df.columns and data_df['year'].any() else 2000
    max_year = int(data_df['year'].max()) if 'year' in data_df.columns and data_df['year'].any() else 2024
    
    selected_year = st.sidebar.slider(
        "Select Year Range:",
        min_value=min_year,
        max_value=max_year,
        value=(min_year, max_year),
        step=1
    )
    
    # Apply filters
    filtered_df = data_df[
        (data_df['year'] >= selected_year[0]) & 
        (data_df['year'] <= selected_year[1])
    ]

    # --- Visualizations ---
    
    st.header("1. Marriage Rate vs. Divorce Rate (Per 1,000 People)")
    
    if filtered_df.empty:
        st.warning("No data available for the selected year range.")
    else:
        # Create an interactive Altair scatter plot
        scatter_chart = alt.Chart(filtered_df).mark_circle(size=100).encode(
            x=alt.X('marriage_rate', title='Marriage Rate'),
            y=alt.Y('divorce_rate', title='Divorce Rate'),
            color=alt.Color('country', title='Country'),
            tooltip=['country', 'year', 'marriage_rate', 'divorce_rate']
        ).properties(
            title="Correlation Between Marriage and Divorce Rates"
        ).interactive() # Allows zooming and panning

        st.altair_chart(scatter_chart, use_container_width=True)

        st.markdown(
            """
            *Observation: The chart shows the rates by country/year. High data scatter indicates little direct correlation, 
            suggesting demographics are influenced heavily by country-specific factors.*
            """
        )

    # --- Raw Data Table ---
    st.header("2. Extracted Raw Data")
    # Display the most recent data first
    st.dataframe(
        filtered_df.sort_values(by='year', ascending=False), 
        use_container_width=True, 
        column_order=['country', 'year', 'marriage_rate', 'divorce_rate', 'extracted_at']
    )

if __name__ == "__main__":
    run_app()