# bot/audio_bot.py - Vollversion mit Antworten
from botbuilder.core import ActivityHandler, TurnContext, MessageFactory
from botbuilder.schema import ChannelAccount, Attachment
from typing import List

print("=== AUDIO BOT WIRD GELADEN ===")


class AudioBot(ActivityHandler):
    def __init__(self):
        super().__init__()
        self.supported_audio_types = {
            'audio/ogg',
            'audio/mpeg',
            'audio/wav',
            'audio/webm',
            'audio/mp3'
        }
        print("✅ AudioBot initialisiert")

    async def on_message_activity(self, turn_context: TurnContext):
        print("\n" + "-" * 30)
        print("📱 MESSAGE ACTIVITY")
        print("-" * 30)

        try:
            print(f"Channel: {turn_context.activity.channel_id}")
            print(f"Text: {turn_context.activity.text}")
            print(f"Service URL: {turn_context.activity.service_url}")

            attachments = turn_context.activity.attachments or []
            print(f"Anzahl Attachments: {len(attachments)}")

            # Zeige Attachment Details
            for i, att in enumerate(attachments):
                print(f"  Attachment {i + 1}:")
                print(f"    Content-Type: {att.content_type}")
                print(f"    Name: {att.name}")

            # Audio-Attachments filtern
            audio_attachments = [
                att for att in attachments
                if att.content_type in self.supported_audio_types
            ]

            print(f"🎵 Audio Attachments: {len(audio_attachments)}")

            if not audio_attachments:
                print("📝 Sende 'Nur Audio' Nachricht")
                await turn_context.send_activity(
                    MessageFactory.text("🎵 Ich reagiere nur auf Audio-Nachrichten!")
                )
                return

            # Verarbeite Audio
            for attachment in audio_attachments:
                await self._process_audio(turn_context, attachment)

        except Exception as e:
            print(f"❌ Fehler in on_message_activity: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")

    async def _process_audio(self, turn_context: TurnContext, attachment: Attachment):
        try:
            print(f"🎤 Verarbeite Audio: {attachment.name}")
            print(f"Content-Type: {attachment.content_type}")
            print(f"Content-URL: {attachment.content_url}")

            response = f"✅ Audio erhalten: {attachment.name or 'Sprachnachricht'}"
            print(f"📤 Sende Antwort: {response}")

            await turn_context.send_activity(MessageFactory.text(response))
            print("✅ Antwort gesendet")

        except Exception as e:
            print(f"❌ Fehler in _process_audio: {str(e)}")

    async def on_members_added_activity(
            self,
            members_added: List[ChannelAccount],
            turn_context: TurnContext
    ):
        print(f"👋 Neue Mitglieder: {len(members_added)}")
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                print("📝 Sende Willkommensnachricht")
                await turn_context.send_activity(
                    MessageFactory.text("👋 Hallo! Sende mir eine Audio-Nachricht!")
                )