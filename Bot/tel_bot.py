from botbuilder.core import ActivityHandler, TurnContext

class VoiceOnlyBot(ActivityHandler):
    async def on_message_activity(self, turn_context: TurnContext):
        activity = turn_context.activity

        if activity.attachments:
            content_type = activity.attachments[0].content_type
            if content_type.startswith("audio/") or "voice" in content_type:
                await turn_context.send_activity("Audio erhalten. Danke!")
            else:
                pass  # Keine Antwort auf Text o.Ä.
        else:
            pass  # Keine Anhänge → ignorieren
