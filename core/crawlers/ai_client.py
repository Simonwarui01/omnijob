import os
from openai import AzureOpenAI

client = AzureOpenAI(
    azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT', 'https://omnijob-foundry.cognitiveservices.azure.com/'),
    api_key=os.getenv('AZURE_OPENAI_KEY'),
    api_version='2024-12-01-preview'
)
DEPLOYMENT = 'gpt-4-1-mini'
