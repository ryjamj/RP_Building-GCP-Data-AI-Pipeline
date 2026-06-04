import os
from google.cloud import bigquery
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

# Securely load the environment variable from your hidden .env file
load_dotenv()

# --- DIAGNOSTICS CODE: Add these two lines ---
print(f"Current Working Directory: {os.getcwd()}")
print(f"Loaded API Key: {os.environ.get('GEMINI_API_KEY')}\n")
# ---------------------------------------------

# 1. Point LangChain to your BigQuery dataset
PROJECT_ID = "lake-sensor-analytics"
DATASET_ID = "lake_data"
sqlalchemy_url = f"bigquery://{PROJECT_ID}/{DATASET_ID}"

db = SQLDatabase.from_uri(sqlalchemy_url)

# 2. Initialize the Gemini Brain (Using the working 2.5-flash model)
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

# 3. Create the SQL Agent toolkit
agent_executor = create_sql_agent(
    llm=llm,
    db=db,
    agent_type="tool-calling",
    verbose=True
)

# 4. Ask your question!
query = "Show me the top 5 unique site names present in the logs along with their parameter descriptions."

print(f"Question: {query}\n")
response = agent_executor.invoke({"input": query})
print(f"\nAnswer: {response['output']}")