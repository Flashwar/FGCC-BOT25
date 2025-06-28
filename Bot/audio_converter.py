import subprocess
import tempfile
import os
import asyncio
import shutil
from typing import Optional


class FFmpegAudioConverter:
    # FFmpeg based audio converter


    def __init__(self):
        self.ffmpeg_available = self._check_ffmpeg_availability()
        if self.ffmpeg_available:
            print("ffmpeg will be initalised")
        else:
            print("FFmpeg not available, please install it")

    def _check_ffmpeg_availability(self) -> bool:
        # check if is installed
        try:
            result = subprocess.run(['ffmpeg', '-version'],
                                    capture_output=True,
                                    text=True,
                                    timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            return False

    async def convert_to_azure_wav(self, audio_bytes: bytes, source_format: str = 'auto'):
       # convert file to wav
        if not self.ffmpeg_available:
            print("❌ FFmpeg not available, please install it")
            return None

        try:
            print(f"🔄 FFmpeg Converting: {source_format} -> WAV (16kHz, Mono, 16-bit)")

            # create temporary file
            with tempfile.NamedTemporaryFile(delete=False) as input_file:
                input_file.write(audio_bytes)
                input_path = input_file.name

            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as output_file:
                output_path = output_file.name

            # ffmpeg command for converting
            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,  # Input-file
                '-ar', '16000',  # Sample Rate: 16 kHz (Azure recommended)
                '-ac', '1',  # Channels: Mono
                '-sample_fmt', 's16',  # 16-bit signed integer samples
                '-f', 'wav',  # Output Format: WAV
                '-acodec', 'pcm_s16le',  # Audio Codec: 16-bit PCM little-endian
                output_path
            ]


            # use FFmpeg command asychron
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                # read file
                with open(output_path, 'rb') as f:
                    wav_bytes = f.read()

                print(f"✅ FFmpeg Konvertierung erfolgreich:")
                print(f"   Input: {len(audio_bytes)} bytes")
                print(f"   Output: {len(wav_bytes)} bytes")
                print(f"   Komprimierung: {len(wav_bytes) / len(audio_bytes):.2f}x")

                return wav_bytes
            else:
                error_msg = stderr.decode('utf-8', errors='ignore')
                print(f"❌ FFmpeg Error (Code {process.returncode}):")
                print(f"   Stderr: {error_msg}")
                return None

        except asyncio.TimeoutError:
            print("❌ FFmpeg Timeout - File was to big")
            return None
        except Exception as e:
            print(f"❌ FFmpe conversion error: {e}")
            return None
        finally:
            # delete temporary file
            try:
                if 'input_path' in locals():
                    os.unlink(input_path)
                if 'output_path' in locals():
                    os.unlink(output_path)
            except OSError:
                pass  # Nicht kritisch wenn Cleanup fehlschlägt

    def get_audio_info(self, audio_bytes: bytes):

        # extract audio infromation
        if not self.ffmpeg_available:
            return {}

        try:
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_path = temp_file.name

            # ffprobe Kommando
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                temp_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                import json
                info = json.loads(result.stdout)

                # Relevante Audio-Info extrahieren
                audio_info = {}
                if 'format' in info:
                    audio_info['duration'] = float(info['format'].get('duration', 0))
                    audio_info['size'] = int(info['format'].get('size', 0))
                    audio_info['format_name'] = info['format'].get('format_name', 'unknown')

                if 'streams' in info and info['streams']:
                    stream = info['streams'][0]  # Erster Audio-Stream
                    audio_info['sample_rate'] = int(stream.get('sample_rate', 0))
                    audio_info['channels'] = int(stream.get('channels', 0))
                    audio_info['codec'] = stream.get('codec_name', 'unknown')

                return audio_info
            else:
                print(f"❌ ffprobe Fehler: {result.stderr}")
                return {}

        except Exception as e:
            print(f"❌ Audio-Info Extraktion fehlgeschlagen: {e}")
            return {}
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
