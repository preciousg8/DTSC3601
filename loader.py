import os
import json
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path # Ensure Path is imported for consistent file handling

# --- Configuration ---
STRUCTURED_JSON_PATH = Path("data/structured_data.json")
TABLE_NAME = "demographics_data1" # Name your Supabase table

load_dotenv()

# Get environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") # Use the Service Role Key for secure upserts

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: SUPABASE_URL or SUPABASE_KEY not found in .env file.")
    exit()

def connect_to_supabase() -> Client:
    """Initializes and returns the Supabase client."""
    print("⏳ Connecting to Supabase...")
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase connection successful.")
        return supabase
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        exit()
        
def load_data_and_upsert(supabase: Client):
    """Loads JSON, converts to DataFrame, and upserts to Supabase."""

    data = None
    
    # 1. Load the structured JSON
    try:
        print(f"⏳ Reading structured content from {STRUCTURED_JSON_PATH}...")
        # Load the file created by structurer.py
        with open(STRUCTURED_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f) 
            
        # Check root object type (must be a dictionary for the flattening logic to work)
        if not isinstance(data, dict):
            print(f"❌ Error: Root object in JSON is a {type(data)}, expected a dictionary. Check structurer output.")
            return

        print(f"✅ Loaded {len(data)} records (countries) from structured JSON.")

    except FileNotFoundError:
        print(f"❌ Error: {STRUCTURED_JSON_PATH} not found. Run structurer.py first!")
        return
    except json.JSONDecodeError as e:
        print(f"❌ Error decoding JSON. Check file syntax: {e}")
        return

    # 2. Flatten the nested structure
    # This loop deconstructs the JSON (Country -> Year -> Metrics) into a flat list of records.
    flat_records = []
    for country, country_data in data.items():
        if not isinstance(country_data, dict):
            print(f"Warning: Skipping {country} as its data is not a dictionary.")
            continue
            
        for year_str, year_data in country_data.items():
            
            # Use .copy() to avoid modifying the original dictionary structure
            record = year_data.copy()
            
            # If the LLM didn't insert country/year keys (for robustness)
            if 'country' not in record:
                record["country"] = country 
            if 'year' not in record:
                # Attempt to convert the year key from the JSON structure to an integer
                try:
                    record["year"] = int(year_str)
                except ValueError:
                    print(f"Warning: Skipping record for {country}/{year_str} due to invalid year format.")
                    continue
            
            # Add timestamps required by the database
            current_time = datetime.utcnow().isoformat()
            record["extracted_at"] = record.get("extracted_at", current_time) 
            record["updated_at"] = current_time
            
            flat_records.append(record)
            
    if not flat_records:
        print("❌ No valid records were flattened. Check LLM output structure.")
        return

    # 3. Convert to Pandas DataFrame
    df = pd.DataFrame(flat_records)
    print(f"✅ Converted to DataFrame with {len(df)} rows.")

    # 4. Handle data types for database insertion
    # List of all metric columns to ensure they are numeric
    numeric_cols = [
        'year', 
        'marriage_rate', 
        'divorce_rate', 
        'extracted_at', 
        'updated_at',
    ]
    
    for col in numeric_cols:
        if col in df.columns:
            # Convert to numeric, coercing errors (non-numeric or missing values become NaN)
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Replace NaN or None with None for proper Supabase handling of NULL values (important for REAL/float columns)
    df = df.where(pd.notna(df), None)
    
    # Convert DataFrame back to a list of dicts for the Supabase upsert function
    records_to_upsert = df.to_dict('records')

    print(f"⏳ Upserting {len(records_to_upsert)} records into table '{TABLE_NAME}'...")

    # 5. Upsert/Insert the data
    try:
        # Assumes 'country' and 'year' are the composite primary key for upsert
        response = supabase.table(TABLE_NAME).upsert(
            records_to_upsert, 
            on_conflict="country, year" 
        ).execute()

        if response.data and isinstance(response.data, list):
            print(f"✅ Data upsert successful. {len(response.data)} rows processed/updated.")
        else:
            print(f"❌ Upsert returned an unexpected response. Rows processed: {len(response.data)}")
            
    except Exception as e:
        print(f"❌ An error occurred during upsert: {e}")
        print("   -> Ensure your Supabase table schema and unique constraints are correct.")
        print(
            "  Expected Table Schema:\n"
            "  - country (TEXT, Primary Key)\n"
            "  - year (INTEGER, Primary Key)\n"
            "  - marriage_rate (REAL)\n"
            "  - divorce_rate (REAL)\n"
            "  - extracted_at (TIMESTAMPTZ)\n"
            "  - updated_at (TIMESTAMPTZ)"
        )

if __name__ == "__main__":
    db_client = connect_to_supabase()
    load_data_and_upsert(db_client)
