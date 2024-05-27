import logging
from typing import Any, Text, Dict, List
from googletrans import Translator
from rasa.engine.graph import GraphComponent, ExecutionContext
from rasa.engine.recipes.default_recipe import DefaultV1Recipe
from rasa.engine.storage.resource import Resource
from rasa.engine.storage.storage import ModelStorage
from rasa.shared.nlu.training_data.message import Message
from rasa.shared.nlu.training_data.training_data import TrainingData

logger = logging.getLogger(__name__)


def get_nested_value(d, key_string: str, default: str):
    keys = key_string.split('.')
    current_value = d
    for key in keys:
        current_value = current_value.get(key, None)
        if current_value is None:
            return default

    return current_value


@DefaultV1Recipe.register(component_types=DefaultV1Recipe.ComponentType.MESSAGE_FEATURIZER, is_trainable=False)
class TranslationComponent(GraphComponent):
    name = 'components.language_detection.TranslationComponent'

    def __init__(self, config: Dict[Text, Any]):
        self.src_lang = config.get('src_lang', 'auto')
        self.dest_lang = config.get('dest_lang', 'auto')
        self.type = config['type']  # text or response

        if self.src_lang == self.dest_lang == 'auto':
            raise ValueError('At least one of src_lang and dest_lang must be specified!')

        self.translator = Translator()

        logger.info(f'{self.name} {self.type}: {self.src_lang} -> {self.dest_lang} initialized.')

    @staticmethod
    def required_packages() -> List[Text]:
        return ['googletrans']

    @classmethod
    def create(
            cls,
            config: Dict[Text, Any],
            model_storage: ModelStorage,
            resource: Resource,
            execution_context: ExecutionContext,
    ) -> GraphComponent:
        return cls(config)

    def process(self, messages: List[Message]) -> List[Message]:
        for message in messages:
            text = get_nested_value(message, self.type, '')

            if not len(text):
                logger.info('Skipped empty message!')
                continue

            src_lang = self.src_lang
            if src_lang == 'auto':
                src_lang = message.get('language', 'auto')  # Assume language is already detected

            dest_lang = self.dest_lang
            if dest_lang == 'auto':
                dest_lang = message.get('language', 'auto')  # Assume language is already detected

            if src_lang != dest_lang:
                translated = self.translator.translate(text, src=src_lang, dest=dest_lang)

                logger.info(f'Translated {self.type} from "{text}" ({src_lang}) to "{translated.text}" ({dest_lang})')
                message.set(self.type, translated.text)

        return messages

    def process_training_data(self, training_data: TrainingData) -> TrainingData:
        self.process(training_data.training_examples)
        return training_data
