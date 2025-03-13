import json
import os

from azure.identity import DefaultAzureCredential
from openai import AzureOpenAI

# Use DefaultAzureCredential to get a token
def get_azure_ad_token():
    try:
        credential = DefaultAzureCredential()
        token = credential.get_token("https://cognitiveservices.azure.com/.default")

        print("[DEBUG] Retrieved Azure AD token successfully using DefaultAzureCredential.")
    except Exception as e:
        print(f"[ERROR] Failed to retrieve Azure AD token: {e}")
        raise e
    return token.token

# Fetch AD Token
azure_ad_token = get_azure_ad_token()

aoai_client = AzureOpenAI(
    api_version="2024-09-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_ad_token=azure_ad_token
)
print("[DEBUG] Initialized Azure OpenAI client.")

def generate_embedding(text):
    response = aoai_client.embeddings.create(input=text, model=os.getenv("AZURE_OPENAI_EMBEDDINGDEPLOYMENTID"))
    json_response = response.model_dump_json(indent=2)
    parsed_response = json.loads(json_response)
    return parsed_response['data'][0]['embedding']