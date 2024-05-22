import logging

from hdx.api.configuration import Configuration
from hdx.data.dataset import Dataset
import pandas as pd

logger = logging.getLogger(__name__)

DATASET_SOURCES = [
    'wfp-food-prices-for-afghanistan',
    'wfp-food-prices-for-angola',
    'wfp-food-prices-for-argentina',
    'wfp-food-prices-for-armenia',
    'wfp-food-prices-for-azerbaijan',
    'wfp-food-prices-for-burundi',
    'wfp-food-prices-for-benin',
    'wfp-food-prices-for-burkina-faso',
    'wfp-food-prices-for-bangladesh',
    'wfp-food-prices-for-belarus',
    'wfp-food-prices-for-bolivia-plurinational-state-of',
    'wfp-food-prices-for-bhutan',
    'wfp-food-prices-for-central-african-republic',
    'wfp-food-prices-for-china',
    'wfp-food-prices-for-cote-d-ivoire',
    'wfp-food-prices-for-cameroon',
    'wfp-food-prices-for-democratic-republic-of-the-congo',
    'wfp-food-prices-for-congo',
    'wfp-food-prices-for-colombia',
    'wfp-food-prices-for-cabo-verde',
    'wfp-food-prices-for-costa-rica',
    'wfp-food-prices-for-djibouti',
    'wfp-food-prices-for-dominican-republic',
    'wfp-food-prices-for-algeria',
    'wfp-food-prices-for-ecuador',
    'wfp-food-prices-for-egypt',
    'wfp-food-prices-for-eritrea',
    'wfp-food-prices-for-ethiopia',
    'wfp-food-prices-for-fiji',
    'wfp-food-prices-for-gabon',
    'wfp-food-prices-for-georgia',
    'wfp-food-prices-for-ghana',
    'wfp-food-prices-for-guinea',
    'wfp-food-prices-for-gambia',
    'wfp-food-prices-for-guinea-bissau',
    'wfp-food-prices-for-guatemala',
    'wfp-food-prices-for-honduras',
    'wfp-food-prices-for-haiti',
    'wfp-food-prices-for-indonesia',
    'wfp-food-prices-for-india',
    'wfp-food-prices-for-iran-islamic-republic-of',
    'wfp-food-prices-for-iraq',
    'wfp-food-prices-for-jordan',
    'wfp-food-prices-for-japan',
    'wfp-food-prices-for-kazakhstan',
    'wfp-food-prices-for-kenya',
    'wfp-food-prices-for-kyrgyzstan',
    'wfp-food-prices-for-cambodia',
    'wfp-food-prices-for-lao-people-s-democratic-republic',
    'wfp-food-prices-for-lebanon',
    'wfp-food-prices-for-liberia',
    'wfp-food-prices-for-libya',
    'wfp-food-prices-for-sri-lanka',
    'wfp-food-prices-for-lesotho',
    'wfp-food-prices-for-republic-of-moldova',
    'wfp-food-prices-for-madagascar',
    'wfp-food-prices-for-mexico',
    'wfp-food-prices-for-mali',
    'wfp-food-prices-for-myanmar',
    'wfp-food-prices-for-mongolia',
    'wfp-food-prices-for-mozambique',
    'wfp-food-prices-for-mauritania',
    'wfp-food-prices-for-malawi',
    'wfp-food-prices-for-namibia',
    'wfp-food-prices-for-niger',
    'wfp-food-prices-for-nigeria',
    'wfp-food-prices-for-nicaragua',
    'wfp-food-prices-for-nepal',
    'wfp-food-prices-for-pakistan',
    'wfp-food-prices-for-panama',
    'wfp-food-prices-for-peru',
    'wfp-food-prices-for-philippines',
    'wfp-food-prices-for-paraguay',
    'wfp-food-prices-for-state-of-palestine',
    'wfp-food-prices-for-russian-federation',
    'wfp-food-prices-for-rwanda',
    'wfp-food-prices-for-sudan',
    'wfp-food-prices-for-senegal',
    'wfp-food-prices-for-sierra-leone',
    'wfp-food-prices-for-el-salvador',
    'wfp-food-prices-for-somalia',
    'wfp-food-prices-for-south-sudan',
    'wfp-food-prices-for-eswatini',
    'wfp-food-prices-for-syrian-arab-republic',
    'wfp-food-prices-for-chad',
    'wfp-food-prices-for-togo',
    'wfp-food-prices-for-thailand',
    'wfp-food-prices-for-tajikistan',
    'wfp-food-prices-for-timor-leste',
    'wfp-food-prices-for-turkiye',
    'wfp-food-prices-for-united-republic-of-tanzania',
    'wfp-food-prices-for-uganda',
    'wfp-food-prices-for-ukraine',
    'wfp-food-prices-for-venezuela-bolivarian-republic-of',
    'wfp-food-prices-for-viet-nam',
    'wfp-food-prices-for-yemen',
    'wfp-food-prices-for-south-africa',
    'wfp-food-prices-for-zambia',
    'wfp-food-prices-for-zimbabwe'
]

# Initialize HDX configuration
Configuration.create(hdx_site='prod', user_agent='hdx', hdx_read_only=True)


def load_dataset(dataset_id: str):
    # Fetch the dataset
    dataset = Dataset.read_from_hdx(dataset_id)

    # Get the list of resources (files) in the dataset
    resources = dataset.get_resources()

    # Download the first resource (you may need to adjust this if there are multiple resources)
    resource = resources[0]
    file_path = resource.download()[1]

    # Load the dataset into a pandas DataFrame
    df = pd.read_csv(file_path, dtype=object)
    df = df[1:].reset_index(drop=True)  # remove the first description row

    df.price = df.price.astype(float)
    df.usdprice = df.usdprice.astype(float)

    unit_alias = ['packet', 'sack', 'package', 'course', 'head', 'bunch', 'box', 'bar', 'pcs', 'brush', 'loaf', 'pair']

    # normalize units
    for unit_str in df.unit.unique():
        if (unit_str.lower() in [
                    'unit', 'libra', 'day', 'month', 'kg', 'g', 'mt', 'l', 'pound', 'cuartilla', 'gallon', 'marmite', 'kwh',
                    'cylinder',
                    *unit_alias
                ]
                or unit_str.lower().startswith('usd/')):
            continue  # Day, KG, MT, L, Unit, etc

        if unit_str.lower() == 'cubic meter':
            df.loc[df.unit == unit_str, 'price'] /= 1000
            df.loc[df.unit == unit_str, 'usdprice'] /= 1000
            df.loc[df.unit == unit_str, 'unit'] = 'L'
            continue

        if unit_str.lower() == 'dozen':
            df.loc[df.unit == unit_str, 'price'] /= 12
            df.loc[df.unit == unit_str, 'usdprice'] /= 12
            df.loc[df.unit == unit_str, 'unit'] = 'Unit'
            continue

        try:
            n, unit = unit_str.split()
        except Exception:
            logger.error('Unit not recognized: ' + unit_str)
            continue

        n = float(n)

        df.loc[df.unit == unit_str, 'price'] /= n
        df.loc[df.unit == unit_str, 'usdprice'] /= n
        df.loc[df.unit == unit_str, 'unit'] = unit

    df.loc[df.unit == 'MT', 'price'] /= 1000
    df.loc[df.unit == 'MT', 'usdprice'] /= 1000
    df.loc[df.unit == 'MT', 'unit'] = 'KG'

    df.loc[df.unit == 'G', 'price'] *= 1000
    df.loc[df.unit == 'G', 'usdprice'] *= 1000
    df.loc[df.unit == 'G', 'unit'] = 'KG'

    df.loc[df.unit == 'Libra', 'price'] /= 0.3289
    df.loc[df.unit == 'Libra', 'usdprice'] /= 0.3289
    df.loc[df.unit == 'Libra', 'unit'] = 'KG'

    df.loc[df.unit == 'Pound', 'price'] /= 0.45359237
    df.loc[df.unit == 'Pound', 'usdprice'] /= 0.45359237
    df.loc[df.unit == 'Pound', 'unit'] = 'KG'

    df.loc[df.unit == 'Cuartilla', 'price'] /= 2.875575
    df.loc[df.unit == 'Cuartilla', 'usdprice'] /= 2.875575
    df.loc[df.unit == 'Cuartilla', 'unit'] = 'KG'

    df.loc[df.unit == 'ML', 'price'] *= 1000
    df.loc[df.unit == 'ML', 'usdprice'] *= 1000
    df.loc[df.unit == 'ML', 'unit'] = 'L'

    df.loc[df.unit == 'Gallon', 'price'] /= 3.78541
    df.loc[df.unit == 'Gallon', 'usdprice'] /= 3.78541
    df.loc[df.unit == 'Gallon', 'unit'] = 'L'

    df.loc[df.unit == 'Month', 'price'] /= 30
    df.loc[df.unit == 'Month', 'usdprice'] /= 30
    df.loc[df.unit == 'Month', 'unit'] = 'Day'

    df.loc[df.unit == 'Marmite', 'price'] /= 2.445
    df.loc[df.unit == 'Marmite', 'usdprice'] /= 2.445
    df.loc[df.unit == 'Marmite', 'unit'] = 'KG'

    for alias in unit_alias:
        df.loc[df.unit == alias.capitalize(), 'unit'] = 'Unit'

    df.to_csv(f'datasets/{dataset_id.replace("wfp-food-prices-for-", "")}.csv', index=False)


def update_datasets():
    for dataset_id in DATASET_SOURCES:
        logger.info(f'Loading {dataset_id} dataset from HDX')
        load_dataset(dataset_id)
