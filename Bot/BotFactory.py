from botbuilder.core import ConversationState, UserState, MemoryStorage
from .tel_bot import AudioBot
from .message_bot import RegistrationTextBot
from .services import CustomerService


def create_bot_instances():
 # Factory function for creating bot instances with all required dependencies
    try:
        #  Initialize in-memory state storage for managing conversation and user state
        memory = MemoryStorage()
        conversation_state = ConversationState(memory)
        user_state = UserState(memory)

        # Create an instance of the customer service for handling customer-related logic
        # which is required for passing it to the bots
        customer_service = CustomerService()

        # Instantiate bots
        tele_bot = AudioBot(conversation_state, user_state, customer_service)
        web_bot = RegistrationTextBot(conversation_state, user_state, customer_service)


        # Return a dictionary with all bot instances and related components
        return {
            'tele_bot': tele_bot,
            'web_bot': web_bot,
            'conversation_state': conversation_state,
            'user_state': user_state,
            'customer_service': customer_service
        }

    # Output an error message and re-raise the exception if bot creation fails
    except Exception as e:
        print(f"❌ Fehler bei Bot-Erstellung: {e}")
        raise