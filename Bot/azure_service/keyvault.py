from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

#  Service to retrieve secrets from Azure Key Vault
class AzureKeyVaultService:

    # Initialize the SecretClient with DefaultAzureCredential
    def __init__(self, vault_url: str, ):
        self.vault_url = vault_url
        self.credential = DefaultAzureCredential()
        self.client = SecretClient(vault_url=self.vault_url, credential=self.credential)

    def get_secret_from_keyvault(self, secret_name: str):
        # Retrieve a secret value from Azure Key Vault by name
        # Returns the secret value if found, otherwise None
        try:
            secret = self.client.get_secret(secret_name)
            secret_value = secret.value
            return secret_value

        except Exception as e:
            print(f"Fehler beim Abrufen von Secret '{secret_name}': {e}")
            return None