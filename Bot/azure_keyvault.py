from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def get_secret_from_keyvault(secret_name: str, vault_url: str):
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=vault_url, credential=credential)
    secret = client.get_secret(secret_name)
    return secret.value
