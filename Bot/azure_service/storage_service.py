import uuid
from azure.storage.blob import BlobServiceClient

from FCCSemesterAufgabe.settings import AZURE_KEYVAULT


class BlobService:
    # Handles audio upload to Azure Blob Storage using SAS and Connection String

    def __init__(self):
        # Retrieve Azure Storage configuration from Azure Key Vault
        self.connection_string = AZURE_KEYVAULT.get_secret_from_keyvault("STORAGE-CONNECTION-STRING")
        self.container_name = AZURE_KEYVAULT.get_secret_from_keyvault("STORAGE-CONTAINER-NAME")
        self.sas_token = AZURE_KEYVAULT.get_secret_from_keyvault("STORAGE-SAS-TOKEN")

        if self.connection_string:
            self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
            print("Azure Blob Storage initialized with Connection String")
        else:
            self.blob_service_client = None
            print("⚠️ Azure Storage Connection String not found")

    async def upload_audio_blob(self, audio_bytes: bytes, content_type: str = "audio/wav"):
        # Uploads audio to Azure Blob Storage and returns the SAS URL
        try:
            if not self.blob_service_client:
                raise Exception("Azure Blob Storage not configured")

            # Generate a unique blob name
            file_extension = ".wav" if content_type == "audio/wav" else ".mp3"
            blob_name = f"bot-audio-{uuid.uuid4()}{file_extension}"

            # Upload to Blob Storage
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )

            # Upload with metadata
            blob_client.upload_blob(
                audio_bytes,
                content_type=content_type,
                overwrite=True,
                metadata={
                    'source': 'telegram-bot',
                    'created': str(uuid.uuid4())[:8]
                }
            )

            # Generate SAS URL if a SAS token is available
            if self.sas_token:
                blob_url_with_sas = f"{blob_client.url}?{self.sas_token}"
                print(f"Audio uploaded with SAS URL: {blob_name}")
            else:
                blob_url_with_sas = blob_client.url
                print(f"Audio uploaded with public URL: {blob_name}")

            return blob_url_with_sas

        except Exception as e:
            print(f"Blob upload failed: {e}")
            return None

    def generate_sas_url(self, blob_url: str):
        # Appends the SAS token to an existing blob URL if available
        try:
            if self.sas_token and '?' not in blob_url:
                return f"{blob_url}?{self.sas_token}"
            return blob_url
        except Exception as e:
            print(f"SAS URL generation failed: {e}")
            return blob_url