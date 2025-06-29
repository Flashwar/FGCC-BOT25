import aiohttp
import json
import os
from typing import Dict, Any, List
from FCCSemesterAufgabe.settings import AZURE_KEYVAULT


class AzureCLUService:

    def __init__(self):
        # Initializes the Azure CLU (Conversational Language Understanding) Service

        # Retrieve all required secrets from Azure Key Vault
        self.prediction_key = AZURE_KEYVAULT.get_secret_from_keyvault("CLU-KEY")
        self.project_name = AZURE_KEYVAULT.get_secret_from_keyvault("CLU-PROJECT-NAME")
        self.deployment_name = AZURE_KEYVAULT.get_secret_from_keyvault("CLU-DEPLOYMENT-NAME")
        self.prediction_endpoint = AZURE_KEYVAULT.get_secret_from_keyvault("CLU-ENDPOINT")

        # Ensure all required values are present
        if not all([self.prediction_key, self.project_name, self.deployment_name, self.prediction_endpoint]):
            raise ValueError("Nicht alle CLU-Secrets konnten im KeyVault gefunden werden")

        print(f"CLU Service initialisiert - Projekt: {self.project_name}")

    async def get_entities(self, text: str) -> List[dict[str, str]]:
        # extract all entities out of the text

        try:
            url = f"{self.prediction_endpoint}/language/:analyze-conversations"

            headers = {
                'Ocp-Apim-Subscription-Key': self.prediction_key,
                'Content-Type': 'application/json'
            }

            data = {
                "kind": "Conversation",
                "analysisInput": {
                    "conversationItem": {
                        "participantId": "user",
                        "id": "1",
                        "modality": "text",
                        "language": "de",
                        "text": text
                    }
                },
                "parameters": {
                    "projectName": self.project_name,
                    "deploymentName": self.deployment_name,
                    "verbose": True
                }
            }

            # setup a session
            async with aiohttp.ClientSession() as session:
                # send the message
                async with session.post(f"{url}?api-version=2023-04-01", json=data, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        return self._extract_entities_from_response(result)
                    else:
                        print(f"CLU API Error: {response.status}")
                        return []

        except Exception as e:
            print(f"Error: {e}")
            return []

    def _extract_entities_from_response(self, response: Dict):
        # extract entites out of the input response
        entities = []

        prediction = response.get("result", {}).get("prediction", {})
        entity_list = prediction.get("entities", [])

        for entity in entity_list:
            # extract information
            entity_data = {
                "category": entity.get("category", ""),
                "text": entity.get("text", "")
            }

            # ckeck if extra information are there (List)
            extra_info = entity.get("extraInformation", [])
            for info in extra_info:
                if info.get("extraInformationKind") == "ListKey":
                    entity_data["key"] = info.get("key", "")
                    break

            entities.append(entity_data)

        return entities