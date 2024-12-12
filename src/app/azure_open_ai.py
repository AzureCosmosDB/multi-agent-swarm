import json
import os

from openai import AzureOpenAI

aoai_client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-09-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

def generate_embedding(text):
    response = aoai_client.embeddings.create(input=text, model=os.getenv("AZURE_OPENAI_EMBEDDINGDEPLOYMENTID"))
    json_response = response.model_dump_json(indent=2)
    parsed_response = json.loads(json_response)
    return parsed_response['data'][0]['embedding']