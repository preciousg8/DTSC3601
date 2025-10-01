import streamlit as st
import pandas as pd
import os
from supabase import create_client, Client
import plotly.express as px 
from dotenv import load_dotenv

load_dotenv()
# --- Configuration ---
# MUST MATCH the lowercase name used in your loader.py
TABLE_NAME = "demographics_data1" 

# --- 1. Supabase Client Initialization and Caching ---

# @st.cache_resource
def get_supabase_client() -> Client:
    """Initializes and returns the Supabase client, cached for performance."""
    try:
        # These environment variables are supplied by Modal's Secret object
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        
        if not url or not key:
            # Return None if credentials aren't set (expected during early Modal deployment)
            return None
            
        supabase_client: Client = create_client(url, key)
        return supabase_client
    except Exception as e:
        st.error(f"❌ Supabase client initialization failed: {e}")
        return None

# Define the client object once
supabase_client = get_supabase_client()

# --- 2. Data Fetching ---

#@st.cache_data(ttl=600) # Cache data for 10 minutes
def fetch_data(client: Client) -> pd.DataFrame:
    """Fetches all structured data from the table and performs type conversion."""
    if client is None:
        return pd.DataFrame()
        
    try:
        # Fetch all columns, ordered by country and year
        response = client.table(TABLE_NAME).select("*").order('country').order('year', desc=False).execute()
        
        df = pd.DataFrame(response.data)
        
        if df.empty:
            return df
            
        # Ensure rates and year are numeric types for plotting
        numeric_cols = [
            'year', 'marriage_rate', 'divorce_rate', 'extracted_at', 'updated_at',
        ]
        
        for col in numeric_cols:
            # Convert to numeric, coercing errors to NaN
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Convert 'year' to integer type
        df['year'] = df['year'].fillna(0).astype(int)
        
        return df

    except Exception as e:
        st.error(f"❌ Error fetching data from Supabase. Check if table name ({TABLE_NAME}) is correct.")
        # st.code(e) # Uncomment for detailed database error
        return pd.DataFrame()

# --- 3. Streamlit UI and Visualization ---

def main():
    st.set_page_config(layout="wide", page_title="Global Demographics Data")
    st.title("❤️ Global Demographic Indicators Dashboard")
    st.caption(f"Expanded Data Extracted and Structured by LLM. Table: `{TABLE_NAME}`")

    if supabase_client is None:
        st.error("Cannot connect to database. Please ensure your Modal Secret is properly configured with SUPABASE_URL and SUPABASE_KEY.")
        return
        
    data_df = fetch_data(supabase_client)

    if data_df.empty:
        st.warning("No structured data retrieved. This means either your Loader failed, or the table is empty. Please check your Supabase data.")
        st.stop() # CRITICAL: Stop execution if data is empty to prevent KeyError

    # --- Sidebar Filters ---
    st.sidebar.header("Filter & Visualize")
    
    countries = sorted(data_df['country'].unique())
    # Default to showing the first two countries for a clean start
    selected_countries = st.sidebar.multiselect("Select Countries for Analysis", countries, default=countries[:2])
    
    filtered_df = data_df[data_df['country'].isin(selected_countries)]
    
    # --- Metrics ---
    st.subheader("Key Global Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    # Safely calculate means across all data
    with col1:
        st.metric("Avg Marriage Rate", f"{data_df['marriage_rate'].mean():.2f}")
    with col2:
        st.metric("Avg Divorce Rate", f"{data_df['divorce_rate'].mean():.2f}")
    

    st.divider()

    # --- Visualizations ---
    
    # Only proceed with plotting if the filtered data isn't empty (handles case where
    # a user deselects all countries)
    if not filtered_df.empty:
        
        st.subheader("1. Marriage Rate Trend")
        
        fig_age = px.line(
            filtered_df.sort_values(by='year'),
            x='year', 
            y='marriage_rate', 
            color='country', 
            markers=True,
            title='Marriage rate Over Time by Country'
        )
        fig_age.update_layout(xaxis_title="Year", yaxis_title="Age (Years)")
        st.plotly_chart(fig_age, use_container_width='stretch')

        st.subheader("2. Marriage Rate vs. Divorce Rate")
        
        fig_scatter = px.scatter(
            filtered_df,
            x='divorce_rate',
            y='marriage_rate',
            color='country',
            size='year', # Size indicates year (recency)
            hover_data=['year', 'divorce_rate'],
            title='Impact of Cohabitation Rate on Marriage Rate'
        )
        fig_scatter.update_layout(
            xaxis_title="Cohabitation Rate (%)", 
            yaxis_title="Marriage Rate (per 1,000)"
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    st.subheader("3. Raw Extracted Data")
    st.dataframe(
        data_df[['country', 'year', 'marriage_rate', 'divorce_rate', 
                  'extracted_at', 'updated_at']],
        use_container_width=True,
        hide_index=True
    )
   
if __name__ == "__main__":
    main() 