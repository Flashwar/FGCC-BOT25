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

    async def analyze_conversation(self, text: str, conversation_id: str = None,
                                   participant_id: str = "user"):
        #  Sends a user input message to Azure CLU for intent and entity analysis
        # Returns: Parsed CLU response with intent and entity data

        try:
            url = f"{self.prediction_endpoint}/language/:analyze-conversations"

            headers = {
                'Ocp-Apim-Subscription-Key': self.prediction_key,
                'Content-Type': 'application/json',
                'Apim-Request-Id': conversation_id or 'default-conversation'
            }

            # CLU request payload
            data = {
                "kind": "Conversation",
                "analysisInput": {
                    "conversationItem": {
                        "participantId": participant_id,
                        "id": f"turn-{hash(text) % 10000}",
                        "modality": "text",
                        "language": "de",
                        "text": text
                    }
                },
                "parameters": {
                    "projectName": self.project_name,
                    "deploymentName": self.deployment_name,
                    "verbose": True,
                    "isLoggingEnabled": False,
                    "stringIndexType": "Utf16CodeUnit"
                }
            }

            print(f"🧠 CLU Request für Text: '{text}'")

            # Perform async API request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        f"{url}?api-version=2023-04-01",
                        json=data,
                        headers=headers
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        parsed_result = self.parse_clu_response(result, text)
                        print(f"✅ CLU Analyse erfolgreich")
                        return parsed_result
                    else:
                        error_text = await response.text()
                        print(f"❌ CLU API error {response.status}: {error_text}")
                        return self.get_default_response(text)

        except Exception as e:
            print(f"❌ CLU service Error: {e}")
            return self._create_error_response(text)

    def parse_clu_response(self, clu_result: Dict, original_text: str):
        # Parses the raw CLU response and extracts intents and entities

        try:
            prediction = clu_result.get("result", {}).get("prediction", {})



            # Extract all intents with their confidence scores
            intents_list = prediction.get("intents", [])
            all_intents = []
            for intent in intents_list:
                intent_name = intent.get("category", "")
                intent_confidence = intent.get("confidenceScore", 0.0)

                all_intents.append({
                    "intent": intent_name,
                    "confidence": intent_confidence,
                    "recognized_text": original_text,
                    "text_length": len(original_text)
                })

            # Get Top Ident
            top_intent = all_intents[0] if all_intents else {"intent": "None", "confidence": 0.0}

            # Sort intents by confidence descending
            all_intents.sort(key=lambda x: x["confidence"], reverse=True)

            # Extract entities from the response
            entities = {}
            entity_list = prediction.get("entities", [])

            for entity in entity_list:
                entity_category = entity.get("category", "")
                entity_text = entity.get("text", "")
                entity_confidence = entity.get("confidenceScore", 0.0)

                # Handle multiple entities per category
                if entity_category in entities:
                    if not isinstance(entities[entity_category], list):
                        entities[entity_category] = [entities[entity_category]]
                    entities[entity_category].append({
                        "text": entity_text,
                        "confidence": entity_confidence
                    })
                else:
                    entities[entity_category] = {
                        "text": entity_text,
                        "confidence": entity_confidence
                    }

            return {
                "top_intent": top_intent["intent"],
                "top_confidence": top_intent["confidence"],
                "all_intents": all_intents,
                "entities": entities,
                "original_text": original_text,
                "service": "CLU",
                "success": True,
                "total_intents_found": len(all_intents)
            }

        except Exception as e:
            print(f"❌ CLU Parse Error: {e}")
            return self._create_error_response(original_text)

    def _create_error_response(self, text: str):
        # Returns a standardized error response if CLU processing fails

        return {
            "top_intent": "None",
            "top_confidence": 0.0,
            "all_intents": [{
                "intent": "None",
                "confidence": 0.0,
                "recognized_text": text,
                "text_length": len(text)
            }],
            "entities": {},
            "original_text": text,
            "service": "CLU",
            "success": False,
            "error": True,
            "total_intents_found": 0
        }


