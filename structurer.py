import os
import json
from openai import OpenAI
from dotenv import load_dotenv
import json
from pathlib import Path


load_dotenv()

try: 
    client = OpenAI(
        base_url="https://cdong1--azure-proxy-web-app.modal.run",
        api_key=os.getenv("OPENAI_API_KEY")
        
)
    print("✅ OpenAI Client initialized.")
except Exception as e:
    print(f"❌ Error initializing OpenAI client: {e}")
    exit()

# Load blob
# --- 2. Load Blob ---
BLOB_PATH = Path("data/raw_blob.txt")
try:
    with open(BLOB_PATH, "r", encoding="utf-8") as f:
        blob = f.read()
    print(f"✅ Loaded raw blob. Length: {len(blob):,} characters.")
except FileNotFoundError:
    print(f"❌ Error: {BLOB_PATH} not found. Run collector.py first!")
    exit()        

# --- 3. Prompt and API Call ---

# IMPORTANT: Ensure the schema here matches the columns expected by loader.py and UI.py!
prompt = f"""
You are an expert data extraction assistant. Your task is to extract structured demographic data
from the provided text, focusing on marriage and divorce trends.

You MUST return a JSON object where the top-level keys are the COUNTRY NAME, and the values are
dictionaries where the keys are the YEAR (as a string) and the values are the data records.

Data structure template:
{{
  "United States": {{
    "2020": {{
      "country": "United States",
      "year": 2020,
      "marriage_rate": 6.1,
      "divorce_rate": 2.7,
      "extracted_at": 1672531199.0,
      "updated_at": 1672531199.0
    }}
  }}
}}

For all rate and age fields (e.g., marriage_rate, divorce_rate, extracted_at), you MUST
ONLY use floating point numbers, integers, or null. DO NOT use descriptive strings.

Full Schema:
- country: The country name (must be explicitly included in the inner object).
- year: The year as an integer (must be explicitly included in the inner object).
- marriage_rate: Marriages per 1,000 people (float or null).
- divorce_rate: Divorces per 1,000 people (float or null).
- extracted_at: Timestamp of data extraction (UNIX epoch, float or null).
- updated_at: Timestamp of last data update (UNIX epoch, float or null).

Text to analyze:
---
{blob}
---
"""

try:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts structured JSON."},
            {"role": "user", "content": prompt}
        ],
        # CRITICAL FIX: Use the JSON response format for reliable structured output
        response_format={"type": "json_object"}
    )

    structured_json_str = response.choices[0].message.content
    print("--- LLM Output Start ---")
    # Print a snippet of the JSON for inspection
    print(structured_json_str[:500] + "...") 
    print("--- LLM Output End ---")
    
    # CRITICAL FIX: Parse the JSON string into a Python object for validation
    data = json.loads(structured_json_str)
    
    # Save the Python object directly to the file
    OUT_PATH = Path("data/structured_data.json")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        # Use json.dump for a properly formatted, single-encoded JSON file
        json.dump(data, f, indent=4) 
        
    print(f"✅ Structured JSON saved successfully to: {OUT_PATH.resolve()}")
    print(f"Total top-level records (countries): {len(data)}")

except json.JSONDecodeError as e:
    print(f"❌ Failed to parse JSON from LLM output: {e}")
    print("The LLM likely returned malformed JSON despite the instruction.")
    exit()
except Exception as e:
    print(f"❌ An error occurred during the API call or file writing: {e}")
    exit()



    