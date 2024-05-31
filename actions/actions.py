import glob
import logging
import os
import re
import tempfile
from datetime import timedelta, datetime
from pathlib import Path
from typing import Any, Text, Dict, List, Optional, Tuple, Iterable

import dateparser
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt
from rasa_sdk import Action, FormValidationAction
from rasa_sdk.events import UserUtteranceReverted, FollowupAction, ActiveLoop
from rasa_sdk.interfaces import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from rasa_sdk.types import DomainDict

from text2digits import text2digits

T2D = text2digits.Text2Digits()

logger = logging.getLogger(__name__)

# this will load the latest version of the datasets
load_from_hdx = os.getenv('UPDATE_HDX_DATASETS', 'False').lower() in ['true', '1', 'yes']
if load_from_hdx:
    from datasets.update import update_datasets

    update_datasets()

COUNTRIES_DATASETS = {
    Path(path).stem: pd.read_csv(path)
    for path in glob.glob('datasets/data/*.csv')
}

logger.info(f'Loaded datasets for the following countries: {", ".join(sorted(COUNTRIES_DATASETS.keys()))}')

ALL_COMMODITIES = set()
for d in COUNTRIES_DATASETS.values():
    ALL_COMMODITIES.update(d.commodity.unique())

logger.info(f'The following commodities are supported: {", ".join(sorted(ALL_COMMODITIES))}')

DATE_FORMAT = '%Y-%m-%d'
REGEX_RELATIVE_DATE = re.compile(r'(recent|latest|last|past|previous|current)'
                                 r'(\s+(.*))?'  # [2] capture group is number days/weeks etc.
                                 r'\s+(year|month|quarter|week|day|decade)(s)?')  # [3] capture group will is a period

PERIOD2LENGTH = {
    'year': 365,
    'month': 30,
    'quarter': 91,
    'week': 7,
    'day': 1,
    'decade': 3650
}

NATURAL2INT = {
    'couple': 2,
    'few': 3,
    'several': 4,
    'dozen': 12,
    'half-dozen': 6,
}


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


class ActionShowTable(Action):

    def name(self) -> Text:
        return "action_show_table"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: DomainDict) -> List[Dict[Text, Any]]:

        countries: list[str] = tracker.get_slot('countries') or []  # noqa
        commodities: list[str] = tracker.get_slot('commodities')  or []  # noqa
        start_date = tracker.get_slot('start_date') or '1900-01-01'
        end_date = tracker.get_slot('end_date') or '2100-12-31'

        start_date, end_date = dateparser.parse(start_date), dateparser.parse(end_date)

        relevant_datasets = []
        commodities_for_analysis = set()

        # if no countries are selected, choose all possible countries
        skip_match = False
        if not len(countries):
            countries = list(COUNTRIES_DATASETS.keys())
            skip_match = True

        for country in countries:
            if not skip_match:
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
            possible_commodities = dataset.commodity.unique()

            target_commodities = [] if len(commodities) else possible_commodities
            for commodity in commodities:
                best_commodity, score = select_best_match(
                    commodity.lower().strip().replace(' ', ''),
                    possible_commodities
                )

                if best_commodity is not None and (score > 0.2 or commodity.lower() in best_commodity.lower()):
                    target_commodities.append(best_commodity)

                # extend not only with the best match, but also with other possible matches
                for possible_commodity in possible_commodities:
                    if commodity.lower()[:-1] in possible_commodity.lower():
                        target_commodities.append(possible_commodity)

            commodities_for_analysis.update(target_commodities)

            dataset_filtered = dataset[(dataset['commodity'].isin(target_commodities)) &
                                       (dataset['date'] >= start_date) &
                                       (dataset['date'] <= end_date)].reset_index()

            dataset_filtered['country'] = country
            relevant_datasets.append(dataset_filtered)

        filtered_df = pd.concat(relevant_datasets, ignore_index=True)

        if not len(filtered_df):
            dispatcher.utter_message(text=f'No data found for the period from {start_date.strftime("%Y-%m-%d")} '
                                          f'to {end_date.strftime("%Y-%m-%d")}')
            return []

        # Prepare table data
        table_data = {
            "columns": ["Country", "Commodity", "Start date", "End date"],
            "data": []
        }

        grouped = filtered_df.groupby(['country', 'commodity'])
        for (country, commodity), group in grouped:
            start_date = group['date'].min().strftime('%Y-%m-%d')
            end_date = group['date'].max().strftime('%Y-%m-%d')
            table_data['data'].append([country, commodity, start_date, end_date])

        # Send the table data as a custom message
        dispatcher.utter_message(json_message={"table": table_data})

        return []


class MapEntitiesToSlotsAction(Action):
    def name(self):
        return 'action_map_entities_to_slots'

    def run(self, dispatcher, tracker, domain):
        # Extract entities from the tracker
        entities = tracker.latest_message['entities']

        # Create a list of SlotSet events
        events = [SlotSet('image_paths', [])]
        first_settings = {
            'PREFER_DAY_OF_MONTH': 'first',
            'PREFER_MONTH_OF_YEAR': 'first'
        }
        last_settings = {
            'PREFER_DAY_OF_MONTH': 'last',
            'PREFER_MONTH_OF_YEAR': 'last'
        }

        def parse_date(relative_date_str):
            today = datetime.today()

            # assume relative date
            match = REGEX_RELATIVE_DATE.findall(relative_date_str)

            if len(match):
                match = match[0]
            else:
                match = [''] * 5

            n_periods = match[2].lower()
            period = match[3].lower()
            is_multiple = (match[4] == 's')

            logger.info(f'Parsed date: {relative_date_str} -> '
                        f'n_periods: {n_periods}, '
                        f'period: {period}, '
                        f'is_multiple: {is_multiple}')

            if period in PERIOD2LENGTH:
                logger.info('Parsing as a relative date with period')

                n_periods = NATURAL2INT.get(n_periods, n_periods)
                try:
                    n_periods = int(n_periods)
                except (ValueError, TypeError):
                    # recent years vs recent year
                    n_periods = 3 if is_multiple else 1  # FIXME

                delta_days = n_periods * PERIOD2LENGTH[period]
                start_date = today - timedelta(days=delta_days)
                end_date = today
            elif 'late' in relative_date_str or 'recent' in relative_date_str or 'current' in relative_date_str:
                logger.info('Parsing as a simple relative date')

                # lately, latest, recently, most recent, currently, etc.
                start_date = today - timedelta(days=365)
                end_date = today
            else:
                logger.info('Parsing as an absolute date')

                # absolute date
                start_date = dateparser.parse(relative_date_str, settings=first_settings)
                end_date = dateparser.parse(relative_date_str, settings=last_settings)

            return start_date.strftime(DATE_FORMAT), end_date.strftime(DATE_FORMAT)

        dates = []

        for entity in entities:
            entity_name = entity['entity']
            slot_value = entity['value']

            if entity_name == 'date':
                dates.append(slot_value)

        if len(dates) == 1:
            start_date, end_date = parse_date(dates[0])
            events.append(SlotSet('start_date', start_date))
            events.append(SlotSet('end_date', end_date))
        elif len(dates) > 1:
            sorted_dates = sorted(dates, key=lambda x: dateparser.parse(x))

            start_date = dateparser.parse(sorted_dates[0], settings=first_settings).strftime(DATE_FORMAT)
            events.append(SlotSet('start_date', start_date))

            end_date = dateparser.parse(sorted_dates[-1], settings=last_settings).strftime(DATE_FORMAT)
            events.append(SlotSet('end_date', end_date))

        return events


class ValidateAnalyzeForm(FormValidationAction):
    def name(self) -> Text:
        return 'validate_analyze_form'

    def validate_commodities(
            self,
            slot_value: Any,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        if not slot_value:
            dispatcher.utter_message(response='utter_ask_commodities')
            return {'commodities': None}
        return {'commodities': slot_value}

    def validate_countries(
            self,
            slot_value: Any,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        if not slot_value:
            dispatcher.utter_message(response='utter_ask_countries')
            return {'countries': None}
        return {'countries': slot_value}

    def validate_start_date(
            self,
            slot_value: Any,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        if not slot_value:
            dispatcher.utter_message(response='utter_ask_start_date')
            return {'start_date': None}
        return {'start_date': slot_value}

    def validate_end_date(
            self,
            slot_value: Any,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        if not slot_value:
            dispatcher.utter_message(response='utter_ask_end_date')
            return {'end_date': None}
        return {'end_date': slot_value}


class ActionAnalyzePrices(Action):

    def name(self) -> Text:
        return 'action_analyze_prices'

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
        commodities_for_analysis = set()

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
            commodities_for_analysis.update(target_commodities)

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

        image_paths = []

        for sales_type in ['Wholesale', 'Retail']:
            df = filtered_df[filtered_df.pricetype == sales_type]
            if len(df):
                # Plotting the price dynamic using seaborn
                plt.figure(figsize=(10, 6))
                sns.lineplot(
                    data=df,
                    x='date',
                    y=price_column,
                    hue='commodity',
                    style='country'
                )

                # Customizing the plot
                plt.title(f'Price Dynamics ({sales_type})')
                plt.xlabel('Date')
                plt.ylabel(f'Price ({currency})')
                plt.xticks(rotation=45)
                plt.grid(True)

                # Save the plot to a temporary file
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                    plt.savefig(f.name)
                    image_paths.append(f.name)

                plt.clf()

        dispatcher.utter_message(text=f'Showing the price trend '
                                      f'for {", ".join(commodities_for_analysis)} '
                                      f'in {", ".join(countries)} countries '
                                      f'for {start_date.strftime(DATE_FORMAT)} - {end_date.strftime(DATE_FORMAT)} '
                                      f'time period', image=f'{image_paths}')

        # Set slots with analysis result
        return []


class ActionDeactivateLoop(Action):
    def name(self) -> str:
        return "action_deactivate_loop"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            ActiveLoop(None),
            SlotSet("countries", None),
            SlotSet("commodities", None),
            SlotSet("start_date", None),
            SlotSet("end_date", None)
        ]


class ActionGreetAndHelp(Action):

    def name(self) -> str:
        return 'action_greet_and_help'

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict) -> list:

        greet_messages = [event for event in tracker.events if
                          event.get('event') == 'action' and event.get('name') == 'action_greet_and_help']

        if not len(greet_messages):
            dispatcher.utter_message(response='utter_greet')
            return [UserUtteranceReverted(), FollowupAction('utter_help_message')]
        else:
            dispatcher.utter_message(response='utter_greet_again')
            return []


class ActionFallback(Action):
    def name(self):
        return 'action_fallback'

    def run(self, dispatcher, tracker, domain):
        dispatcher.utter_message(response='utter_fallback')
        return []
