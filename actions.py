from rasa_sdk import Action
from rasa_sdk.interfaces import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict


class ActionRepeatIntent(Action):
    def name(self):
        return "action_repeat_intent"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict):
        # Fetch the latest intent
        intent_name = tracker.latest_message['intent'].get('name')

        # Fetch entities
        entities = tracker.latest_message['entities']
        entities_info = ', '.join([f"{entity['entity']} = {entity['value']}" for entity in entities])

        # Create the response message
        message = f"The intent was: {intent_name}."
        if entities_info:
            message += f" The entities were: {entities_info}"

        # Send the message
        dispatcher.utter_message(text=message)
        return []
