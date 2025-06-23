from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import ActivityTypes, Attachment

class VoiceOnlyBot(ActivityHandler):
    async def on_message_activity(self, turn_context: TurnContext):
        activity = turn_context.activity

        is_voice_message = False
        if activity.attachments:
            for attachment in activity.attachments:
                # Telegram Sprachnachrichten kommen als Audio-Attachment
                if attachment.content_type.startswith("audio/ogg"): # Oder nur "audio"
                    is_voice_message = True
                    # Optional: Hier könntest du die Datei-URL des Anhangs bekommen
                    # attachment.contentUrl
                    break

        if is_voice_message:
            # Wenn es eine Sprachnachricht ist, antworte mit "success"
            await turn_context.send_activity("success")
        else:
            # Wenn es keine Sprachnachricht ist, ignoriere oder sende eine andere Nachricht
            await turn_context.send_activity("Ich kann nur Sprachnachrichten verarbeiten. Bitte sende eine Sprachnachricht.")