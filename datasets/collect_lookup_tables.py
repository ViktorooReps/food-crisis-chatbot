import glob
import logging
from pathlib import Path

import pandas as pd
from ruamel.yaml import YAML

from unidecode import unidecode

yaml = YAML()
yaml.preserve_quotes = True

logger = logging.getLogger(__name__)

COUNTRIES_DATASETS = {
    Path(path).stem.replace('-', ' '): pd.read_csv(path)
    for path in glob.glob('datasets/data/*.csv')
}

ALL_COMMODITIES = set()
for d in COUNTRIES_DATASETS.values():
    ALL_COMMODITIES.update(d.commodity.unique())

if __name__ == '__main__':
    with open('data/nlu.yml', 'r') as file:
        yaml_content = yaml.load(file)

    new_lookup_tables = {
        'lookup': {
            'country': sorted(unidecode(c) for c in COUNTRIES_DATASETS.keys()),
            'commodity': sorted(unidecode(c) for c in ALL_COMMODITIES)
        }
    }

    yaml_content.update(new_lookup_tables)

    with open('data/nlu.yml', 'w') as file:
        yaml.dump(yaml_content, file)

    print(f'Added {len(new_lookup_tables["lookup"]["country"])} countries '
          f'and {len(new_lookup_tables["lookup"]["commodity"])} commodities')
