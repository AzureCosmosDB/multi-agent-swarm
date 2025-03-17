import json
import config

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI


token_provider = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")

aoai_client = AzureOpenAI(
    api_version="2024-09-01-preview",
    azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
    azure_ad_token_provider=token_provider
)
print("[DEBUG] Initialized Azure OpenAI client.")

def generate_embedding(text):
    response = aoai_client.embeddings.create(input=text, model=config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT)
    json_response = response.model_dump_json(indent=2)
    parsed_response = json.loads(json_response)
    return parsed_response['data'][0]['embedding']