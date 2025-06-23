import azure.cognitiveservices.speech as speechsdk
import tempfile
import os
from typing import Dict, Optional
from keyvault import AzureKeyVaultService


class AzureSpeechService:
    def __init__(self, keyvault: AzureKeyVaultService = None):
        """
        Initializes the Azure Speech Service
        """
        # Retrieve secrets from Azure Key Vault
        self.speech_key = keyvault.get_secret("COG-KEY")
        self.service_region = keyvault.get_secret("AZURE-SPEECH-REGION")

        if not self.speech_key or not self.service_region:
            raise ValueError("AZURE-SPEECH-KEY or AZURE-SPEECH-REGION not found in KeyVault")

        # Configuration for Text-to-Speech
        self.tts_config = speechsdk.SpeechConfig(
            subscription=self.speech_key,
            region=self.service_region
        )
        self.tts_config.speech_synthesis_voice_name = "de-DE-KatjaNeural"

        # Configuration for Speech-to-Text
        self.stt_config = speechsdk.SpeechConfig(
            subscription=self.speech_key,
            region=self.service_region
        )
        self.stt_config.speech_recognition_language = "de-DE"

    def text_to_speech_bytes(self, text: str, voice: str = "de-DE-KatjaNeural") -> Optional[bytes]:
        """
        Converts text to audio bytes using Azure TTS (Text-to-Speech)
        Returns: The generated audio in WAV format, or None if an error occurred
        """
        try:
            self.tts_config.speech_synthesis_voice_name = voice

            # Create a temporary WAV file to store the audio output
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_file.close()

            audio_config = speechsdk.audio.AudioOutputConfig(filename=temp_file.name)

            # Create a synthesizer with config
            speech_synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.tts_config,
                audio_config=audio_config
            )

            # Perform synthesis
            result = speech_synthesizer.speak_text_async(text).get()

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                # Read and return the generated audio
                with open(temp_file.name, 'rb') as f:
                    audio_bytes = f.read()
                # delete the temporary file
                os.unlink(temp_file.name)
                return audio_bytes
            else:
                os.unlink(temp_file.name)
                print(f"TTS Error: {result.reason}")
                return None

        except Exception as e:
            print(f"Text-to-Speech Exception: {e}")
            return None

    def speech_to_text_from_bytes(self, audio_bytes: bytes, language: str = "de-DE") -> Dict:
        """
        Converts audio bytes into text using Azure STT (Speech-to-Text)
        Returns: Dictionary containing a transcription result with metadata
        """
        try:
            # Save audio bytes to a temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_file.flush()

                # Configure audio input
                audio_config = speechsdk.audio.AudioConfig(filename=temp_file.name)

                # Create a new STT config with the specified language
                stt_config = speechsdk.SpeechConfig(
                    subscription=self.speech_key,
                    region=self.service_region
                )
                stt_config.speech_recognition_language = language

                # Create speech recognizer
                speech_recognizer = speechsdk.SpeechRecognizer(
                    speech_config=stt_config,
                    audio_config=audio_config
                )

                # Perform recognition
                result = speech_recognizer.recognize_once()

                # Delete the temporary file
                os.unlink(temp_file.name)

                # Process result
                if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    return {
                        "success": True,
                        "text": result.text,
                        "language": language,
                        "duration": getattr(result, 'duration', None)
                    }
                elif result.reason == speechsdk.ResultReason.NoMatch:
                    return {
                        "success": False,
                        "text": "",
                        "error": "No speech recognized",
                        "reason": "NoMatch"
                    }
                else:
                    return {
                        "success": False,
                        "text": "",
                        "error": f"STT error: {result.reason}",
                        "reason": str(result.reason)
                    }

        except Exception as e:
            return {
                "success": False,
                "text": "",
                "error": f"Speech-to-Text Exception: {str(e)}",
                "exception": str(e)
            }
