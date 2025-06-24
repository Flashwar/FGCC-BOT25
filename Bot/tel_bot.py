# bot/audio_bot.py
from botbuilder.core import ActivityHandler, TurnContext, MessageFactory
from botbuilder.schema import ChannelAccount, Attachment
from typing import List
import logging

logger = logging.getLogger(__name__)


class AudioBot(ActivityHandler):
    """Audio Bot für Telegram und Web Chat"""

    def __init__(self):
        super().__init__()
        self.supported_audio_types = {
            'audio/ogg',
            'audio/mpeg',
            'audio/wav',
            'audio/webm',
            'audio/mp3'
        }

    async def on_message_activity(self, turn_context: TurnContext):
        # Prüfe auf Audio-Attachments
        audio_attachments = [
            att for att in (turn_context.activity.attachments or [])
            if att.content_type in self.supported_audio_types
        ]

        if not audio_attachments:
            await turn_context.send_activity(
                MessageFactory.text("🎵 Ich reagiere nur auf Audio-Nachrichten!")
            )
            return

        # Verarbeite Audio
        for attachment in audio_attachments:
            await self._process_audio(turn_context, attachment)

    async def _process_audio(self, turn_context: TurnContext, attachment: Attachment):
        try:
            logger.info(f"Audio erhalten: {attachment.name}")

            # Audio-Daten laden
            audio_data = await self._get_audio_data(attachment)

            if not audio_data:
                await turn_context.send_activity(
                    MessageFactory.text("❌ Audio konnte nicht geladen werden.")
                )
                return

            # Deine Audio-Verarbeitung hier
            result = await self._analyze_audio(audio_data, attachment)

            # Antwort senden
            response = f"✅ Audio '{attachment.name or 'Sprachnachricht'}' verarbeitet!\n📊 {result}"
            await turn_context.send_activity(MessageFactory.text(response))

        except Exception as e:
            logger.error(f"Fehler bei Audio-Verarbeitung: {str(e)}")
            await turn_context.send_activity(
                MessageFactory.text("❌ Fehler beim Verarbeiten der Audio-Datei.")
            )

    async def _get_audio_data(self, attachment: Attachment) -> bytes:
        """Lädt Audio-Daten"""
        if attachment.content_url:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.content_url) as response:
                    if response.status == 200:
                        return await response.read()
        return None

    async def _analyze_audio(self, audio_data: bytes, attachment: Attachment) -> str:
        """Deine Audio-Analyse"""
        # Hier deine spezifische Logik
        file_size = len(audio_data)

        # Beispiel: Hier würdest du machen:
        # - Speech-to-Text
        # - Audio-Features extrahieren
        # - etc.

        return f"Dateigröße: {file_size} bytes, Format: {attachment.content_type}"

    async def on_members_added_activity(
            self,
            members_added: List[ChannelAccount],
            turn_context: TurnContext
    ):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    MessageFactory.text("👋 Hallo! Sende mir eine Audio-Nachricht!")
                )