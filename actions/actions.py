import tempfile
from typing import Any, Text, Dict, List

import dateparser
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt
from rasa_sdk import Action, Tracker
from rasa_sdk.events import UserUtteranceReverted
from rasa_sdk.interfaces import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from rasa_sdk.types import DomainDict

PAKISTAN_DATA = pd.read_csv('datasets/pakistan.csv')
PAKISTAN_DATA.date = pd.to_datetime(PAKISTAN_DATA.date)
PAKISTAN_DATA.price = PAKISTAN_DATA.price.astype(float)


class ActionRepeatIntent(Action):
    def name(self):
        return "action_repeat_intent"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
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


class ActionAnalyzePrices(Action):

    def name(self) -> Text:
        return "action_analyze_prices"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        country = tracker.get_slot('country').lower()
        commodity = tracker.get_slot('commodity').lower()
        start_date = tracker.get_slot('start_date').lower()
        end_date = tracker.get_slot('end_date').lower()

        if country != 'pakistan':
            dispatcher.utter_message(text=f'The country {country} is not supported yet. Sorry!')
            return []

        dates = [start_date, end_date]
        dates_absolute = sorted(map(dateparser.parse, dates))

        start_date, end_date = dates_absolute
        filtered_df = PAKISTAN_DATA[(PAKISTAN_DATA['commodity'] == commodity) &
                                    (PAKISTAN_DATA['date'] >= start_date) &
                                    (PAKISTAN_DATA['date'] <= end_date)].reset_index()

        if not len(filtered_df):
            dispatcher.utter_message(text=f'No data found for the period from {start_date} to {end_date}')
            return []

        start_price = float(filtered_df.price[0])
        end_price = float(filtered_df.price[len(filtered_df) - 1])

        # Plotting the price dynamic using seaborn
        plt.figure(figsize=(10, 6))
        sns.lineplot(data=filtered_df, x='date', y='price', marker='o')

        # Customizing the plot
        plt.title(f'Price Dynamics for {commodity.capitalize()}')
        plt.xlabel('Date')
        plt.ylabel('Price')
        plt.xticks(rotation=45)
        plt.grid(True)

        trend = 'up' if end_price > start_price else 'down'

        # Save the plot to a temporary file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            plt.savefig(f.name)
            image_path = f.name

        # Set slots with analysis result
        return [
            SlotSet('start_price', start_price),
            SlotSet('end_price', end_price),
            SlotSet('country', country),
            SlotSet('commodity', commodity),
            SlotSet('start_date', start_date.strftime("%Y-%m-%d")),
            SlotSet('end_date', end_date.strftime("%Y-%m-%d")),
            SlotSet('trend', trend),
            SlotSet('image_path', image_path)
        ]


class ActionFallback(Action):
    def name(self):
        return "action_fallback"

    def run(self, dispatcher, tracker, domain):
        dispatcher.utter_message(text="I'm sorry, I didn't quite understand that. Can you rephrase?")

        # Optionally, you can use the UserUtteranceReverted event to forget the last user message
        return [UserUtteranceReverted()]
