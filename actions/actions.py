import glob
import logging
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Text, Dict, List, Optional, Tuple, Iterable

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

from datasets.update import update_datasets

logger = logging.getLogger(__name__)

# this will load the latest version of the datasets
update_datasets()

COUNTRIES_DATASETS = {
    Path(path).stem: pd.read_csv(path)
    for path in glob.glob('datasets/*.csv')
}

logger.info(f'Loaded datasets for the following countries: {", ".join(sorted(COUNTRIES_DATASETS.keys()))}')

ALL_COMMODITIES = set()
for d in COUNTRIES_DATASETS.values():
    ALL_COMMODITIES.update(d.commodity.unique())

logger.info(f'The following commodities are supported: {", ".join(sorted(ALL_COMMODITIES))}')


def match_score(d1: str, d2: str) -> float:
    def strip_chars(s: str) -> str:
        return (s.strip().lower()
                .replace(' ', '')
                .replace('(', '')
                .replace(')', '')
                .replace('-', ''))

    d1 = strip_chars(d1)
    d2 = strip_chars(d2)
    end = 0
    for end in reversed(range(len(d1) + 1)):
        substr = d1[:end]
        if substr in d2:
            break

    return (1 - (len(d1) - end) / len(d1)) * (len(d1) / len(d2))


def select_best_match(target: str, candidates: Iterable[str]) -> Tuple[Optional[str], float]:
    best_match = 0.0
    best_matched_candidate = None

    for candidate in candidates:
        curr_match = match_score(target, candidate)
        if curr_match > best_match:
            best_match = curr_match
            best_matched_candidate = candidate

    return best_matched_candidate, best_match


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


class MapEntitiesToSlotsAction(Action):
    def name(self):
        return "action_map_entities_to_slots"

    def run(self, dispatcher, tracker, domain):
        # Extract entities from the tracker
        entities = tracker.latest_message['entities']

        # Create a list of SlotSet events
        events = []

        for entity in entities:
            entity_name = entity['entity']
            slot_value = entity['value']

            if entity_name == 'date':
                events.append(SlotSet('start_date', dateparser.parse(slot_value, settings={
                    'PREFER_DAY_OF_MONTH': 'first',
                    'PREFER_MONTH_OF_YEAR': 'first'
                }).strftime('%Y-%m-%d')))
                events.append(SlotSet('end_date', dateparser.parse(slot_value, settings={
                    'PREFER_DAY_OF_MONTH': 'last',
                    'PREFER_MONTH_OF_YEAR': 'last'
                }).strftime('%Y-%m-%d')))

            if entity_name == 'start_date':
                events.append(SlotSet('start_date', dateparser.parse(slot_value, settings={
                    'PREFER_DAY_OF_MONTH': 'first',
                    'PREFER_MONTH_OF_YEAR': 'first'
                }).strftime('%Y-%m-%d')))

            if entity_name == 'end_date':
                events.append(SlotSet('end_date', dateparser.parse(slot_value, settings={
                    'PREFER_DAY_OF_MONTH': 'last',
                    'PREFER_MONTH_OF_YEAR': 'last'
                }).strftime('%Y-%m-%d')))

        return events


class ActionAnalyzePrices(Action):

    def name(self) -> Text:
        return "action_analyze_prices"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        countries: list[str] = tracker.get_slot('countries')  # noqa
        commodities: list[str] = tracker.get_slot('commodities')  # noqa
        start_date = tracker.get_slot('start_date')
        end_date = tracker.get_slot('end_date')

        logger.info(f'Filled slots:'
                    f'\n\tcountries={countries}'
                    f'\n\tcommodities={commodities}'
                    f'\n\tstart_date={start_date}'
                    f'\n\tend_date={end_date}')

        start_date, end_date = dateparser.parse(start_date), dateparser.parse(end_date)

        relevant_datasets = []

        for country in countries:
            best_match, score = select_best_match(
                country.lower().strip().replace(' ', ''),
                COUNTRIES_DATASETS.keys()
            )
            if score < 0.2:
                dispatcher.utter_message(text=f'The country {country} is not supported yet. Sorry!')
                return []

            country = best_match
            dataset = COUNTRIES_DATASETS[country]

            dataset['date'] = pd.to_datetime(dataset['date'])
            dataset['price'] = dataset['price'].astype(float)
            dataset['usdprice'] = dataset['usdprice'].astype(float)

            possible_commodities = dataset.commodity.unique()

            target_commodities = []
            for commodity in commodities:
                best_commodity, score = select_best_match(
                    commodity.lower().strip().replace(' ', ''),
                    possible_commodities
                )

                if best_commodity is not None and (score > 0.2 or commodity.lower() in best_commodity.lower()):
                    target_commodities.append(best_commodity)

            logger.info(f'target commodities for {country}: {target_commodities}')

            dataset_filtered = dataset[(dataset['commodity'].isin(target_commodities)) &
                                       (dataset['date'] >= start_date) &
                                       (dataset['date'] <= end_date)].reset_index()

            logger.info(f'dataset size for {country}: {len(dataset_filtered)}')

            dataset_filtered['country'] = country
            relevant_datasets.append(dataset_filtered)

        filtered_df = pd.concat(relevant_datasets, ignore_index=True)

        if not len(filtered_df):
            dispatcher.utter_message(text=f'No data found for the period from {start_date.strftime("%Y-%m-%d")} '
                                          f'to {end_date.strftime("%Y-%m-%d")}')
            return []

        price_column = 'price' if len(countries) < 2 else 'usdprice'
        currency = filtered_df.currency.unique()[0] if len(countries) < 2 else 'USD'

        wholesale_df = filtered_df[filtered_df.pricetype == 'Wholesale']
        retail_df = filtered_df[filtered_df.pricetype == 'Retail']

        image_paths = []

        if len(wholesale_df):
            # Plotting the price dynamic using seaborn
            plt.figure(figsize=(10, 6))
            sns.lineplot(
                data=wholesale_df,
                x='date',
                y=price_column,
                hue='commodity',
                style='country'
            )

            # Customizing the plot
            plt.title(f'Price Dynamics (Wholesale)')
            plt.xlabel('Date')
            plt.ylabel(f'Price ({currency})')
            plt.xticks(rotation=45)
            plt.grid(True)

            # Save the plot to a temporary file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                plt.savefig(f.name)
                image_paths.append(f.name)

            plt.clf()

        if len(retail_df):
            # Plotting the price dynamic using seaborn
            plt.figure(figsize=(10, 6))
            sns.lineplot(
                data=retail_df,
                x='date',
                y=price_column,
                hue='commodity',
                style='country'
            )

            # Customizing the plot
            plt.title(f'Price Dynamics (Retail)')
            plt.xlabel('Date')
            plt.ylabel(f'Price ({currency})')
            plt.xticks(rotation=45)
            plt.grid(True)

            # Save the plot to a temporary file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                plt.savefig(f.name)
                image_paths.append(f.name)

            plt.clf()

        # Set slots with analysis result
        return [
            SlotSet('image_paths', image_paths)
        ]


class ActionFallback(Action):
    def name(self):
        return "action_fallback"

    def run(self, dispatcher, tracker, domain):
        dispatcher.utter_message(text="I'm sorry, I didn't quite understand that. Can you rephrase?")

        # Optionally, you can use the UserUtteranceReverted event to forget the last user message
        return [UserUtteranceReverted()]
