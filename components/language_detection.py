import logging
from collections import defaultdict
from typing import Any, Text, Dict, List
from rasa.engine.graph import GraphComponent, ExecutionContext
from rasa.engine.recipes.default_recipe import DefaultV1Recipe
from rasa.engine.storage.resource import Resource
from rasa.engine.storage.storage import ModelStorage

import fasttext
from rasa.shared.nlu.training_data.message import Message
from rasa.shared.nlu.training_data.training_data import TrainingData

logger = logging.getLogger(__name__)


@DefaultV1Recipe.register(component_types=DefaultV1Recipe.ComponentType.MESSAGE_FEATURIZER, is_trainable=False)
class LanguageDetector(GraphComponent):
    name = 'components.language_detection.LanguageDetector'

    def __init__(self, config: Dict[Text, Any]):
        logger.info(f'{self.name} initialized.')
        self.model = fasttext.load_model(config['model_file'])
        self.confidence_threshold = config.get('confidence_threshold', 0.9)
        self.default = config.get('default', 'en')
        self.past_predictions = defaultdict(int)  # a bit of a hack, but will work for demo

    @staticmethod
    def required_packages() -> List[Text]:
        return ['fasttext']

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
            text = message.get('text', '')

            if not len(text):
                message.set('language', self.default)
                continue

            try:
                predictions = self.model.predict(text, k=1)  # Predict top language
                lang = predictions[0][0].split('__')[-1]  # Extract language code
                confidence = predictions[1][0]
                logger.info(f'Detected language: {lang} ({confidence:.2f})')
            except Exception as e:
                logger.warning(f'Failed to determine the language of the message: {text}', exc_info=e)
                lang = self.default
                confidence = 0.0

            if confidence > self.confidence_threshold:
                self.past_predictions[lang] += 1
            elif len(self.past_predictions):
                lang = max(self.past_predictions, key=self.past_predictions.get)
            else:
                lang = self.default

            message.set('language', lang, add_to_output=True)

        return messages

    def process_training_data(self, training_data: TrainingData) -> TrainingData:
        self.process(training_data.training_examples)
        return training_data
