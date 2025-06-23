from botbuilder.core import ActivityHandler, TurnContext

class VoiceOnlyBot(ActivityHandler):
    async def on_message_activity(self, turn_context: TurnContext):
        # Nur auf Sprachnachrichten reagieren – keine Antwort senden
        activity = turn_context.activity

        if activity.attachments:
            for attachment in activity.attachments:
                if attachment.content_type.startswith("audio"):
                    # Optionale Weiterverarbeitung hier möglich
                    return  # Keine Antwort, einfach still verarbeiten

        # Optional ignorieren, auch keine Antwort senden
        return
