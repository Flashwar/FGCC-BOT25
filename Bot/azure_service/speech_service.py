import azure.cognitiveservices.speech as speechsdk
import tempfile
import os
from typing import Optional, Dict, Any, List

from FCCSemesterAufgabe.settings import isDocker, AZURE_KEYVAULT


class AzureSpeechService:
    def __init__(self):
        # Initializes the Azure Speech Service

        # Determine key and region
        if not isDocker:
            self.speech_key = AZURE_KEYVAULT.get_secret_from_keyvault("COG-KEY")
            self.service_region = AZURE_KEYVAULT.get_secret_from_keyvault("AZURE-SPEECH-REGION")
        else:
            self.speech_key = None
            self.service_region = None

        if not self.speech_key or not self.service_region:
            raise ValueError("Speech Key and Service Region must be provided (directly or via KeyVault)")

        print(f"Azure Speech Service initialized - Region: {self.service_region}")

        # Base configurations
        self._create_configs()


    def _create_configs(self):
        # Creates the base configurations for TTS and STT

        # Text-to-Speech configuration
        self.tts_config = speechsdk.SpeechConfig(
            subscription=self.speech_key,
            region=self.service_region
        )
        self.tts_config.speech_synthesis_voice_name = "de-DE-KatjaNeural"

        # Speech-to-Text configuration
        self.stt_config = speechsdk.SpeechConfig(
            subscription=self.speech_key,
            region=self.service_region
        )
        self.stt_config.speech_recognition_language = "de-DE"


    def text_to_speech_bytes(self, text: str, voice: str = "de-DE-KatjaNeural"):
        # Converts text to audio bytes using Azure TTS

        try:
            if not text or not text.strip():
                print("Empty text for TTS")
                return None

            print(f"TTS for text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            print(f"Using voice: {voice}")

            # Set voice
            self.tts_config.speech_synthesis_voice_name = voice

            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_filename = temp_file.name

            try:
                # Audio configuration
                audio_config = speechsdk.audio.AudioOutputConfig(filename=temp_filename)

                # Create synthesizer
                speech_synthesizer = speechsdk.SpeechSynthesizer(
                    speech_config=self.tts_config,
                    audio_config=audio_config
                )

                # Perform synthesis
                result = speech_synthesizer.speak_text_async(text).get()

                if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                    # Read audio data
                    with open(temp_filename, 'rb') as f:
                        audio_bytes = f.read()

                    print(f"TTS successful: {len(audio_bytes)} bytes generated")
                    return audio_bytes

                elif result.reason == speechsdk.ResultReason.Canceled:
                    cancellation = result.cancellation_details
                    print(f"TTS canceled: {cancellation.reason}")
                    if cancellation.error_details:
                        print(f"Error details: {cancellation.error_details}")
                    return None
                else:
                    print(f"TTS error: {result.reason}")
                    return None

            finally:
                # Delete temporary file
                if os.path.exists(temp_filename):
                    os.unlink(temp_filename)

        except Exception as e:
            print(f"Text-to-Speech Exception: {e}")
            return None


    def speech_to_text_from_bytes(self, audio_bytes: bytes, language: str = "de-DE"):
        # Converts audio bytes to text using Azure STT
        try:
            if not audio_bytes or len(audio_bytes) == 0:
                return {
                    "success": False,
                    "text": "",
                    "error": "No audio data available",
                    "language": language
                }

            # Create temporary audio file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_filename = temp_file.name

            try:
                # Audio configuration
                audio_config = speechsdk.audio.AudioConfig(filename=temp_filename)

                # STT configuration for desired language
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

                if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    print(f"STT successful: '{result.text}'")
                    return {
                        "success": True,
                        "text": result.text,
                        "language": language,
                        "confidence": getattr(result, 'confidence', None),
                        "duration": getattr(result, 'duration', None)
                    }

                elif result.reason == speechsdk.ResultReason.NoMatch:
                    print("STT: No speech detected")
                    return {
                        "success": False,
                        "text": "",
                        "error": "No speech detected in audio file",
                        "reason": "NoMatch",
                        "language": language
                    }

                elif result.reason == speechsdk.ResultReason.Canceled:
                    cancellation = result.cancellation_details
                    error_msg = f"STT canceled: {cancellation.reason}"
                    if cancellation.error_details:
                        error_msg += f" - {cancellation.error_details}"

                    print(f"❌ {error_msg}")
                    return {
                        "success": False,
                        "text": "",
                        "error": error_msg,
                        "reason": "Canceled",
                        "language": language
                    }
                else:
                    print(f"❌ STT unknown error: {result.reason}")
                    return {
                        "success": False,
                        "text": "",
                        "error": f"Unknown STT error: {result.reason}",
                        "reason": str(result.reason),
                        "language": language
                    }

            finally:
                # Delete temporary file
                if os.path.exists(temp_filename):
                    os.unlink(temp_filename)

        except Exception as e:
            print(f"❌ Speech-to-Text Exception: {e}")
            return {
                "success": False,
                "text": "",
                "error": f"Speech-to-Text Exception: {str(e)}",
                "exception": str(e),
                "language": language
            }


    def text_to_speech_file(self, text: str, output_file: str, voice: str = "de-DE-KatjaNeural"):
        # Converts text to audio and saves directly to file
        try:
            audio_bytes = self.text_to_speech_bytes(text, voice)
            if audio_bytes:
                with open(output_file, 'wb') as f:
                    f.write(audio_bytes)
                print(f"Audio saved: {output_file}")
                return True
            return False
        except Exception as e:
            print(f"❌ Error saving audio file: {e}")
            return False


    def speech_to_text_from_file(self, audio_file: str, language: str = "de-DE"):
        # Converts audio file to text

        try:
            if not os.path.exists(audio_file):
                return {
                    "success": False,
                    "text": "",
                    "error": f"Audio file not found: {audio_file}",
                    "language": language
                }

            with open(audio_file, 'rb') as f:
                audio_bytes = f.read()

            return self.speech_to_text_from_bytes(audio_bytes, language)

        except Exception as e:
            print(f"❌ Error reading audio file: {e}")
            return {
                "success": False,
                "text": "",
                "error": f"Error reading audio file: {str(e)}",
                "language": language
            }
