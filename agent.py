import os
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

# Securely load the environment variable from your hidden .env file
load_dotenv()

def run_agent_query(user_prompt: str) -> str:
    """
    Takes a natural language string, runs it through the LangChain SQL agent,
    and returns the final natural language answer text.
    """

    # 1. Initialize BigQuery connection for LangChain
    project_id = os.getenv("GCP_PROJECT_ID")
    dataset_id = "lake_data"
    db = SQLDatabase.from_uri(f"bigquery://{project_id}/{dataset_id}")


    # 2. Initialize the Gemini Brain (Using the working 2.5-flash model)
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

    # 3. Create the SQL Agent toolkit
    agent_executor = create_sql_agent(
        llm=llm,
        db=db,
        agent_type="tool-calling",
        verbose=True
    )

    # 4. Run the query and return the text result.
    # If LangChain returns a dict with 'output' string, use it
    # Else, if the response is a complex object/list, force it to a string cleanly
    response = agent_executor.invoke({"input": user_prompt})
    if isinstance(response, dict) and "output" in response:
        return response["output"]
    return str(response)