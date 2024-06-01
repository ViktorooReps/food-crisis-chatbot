# Food Crisis ChatBot

Built with Streamlit and Rasa.

![Screenshot 2024-05-27 222417](https://github.com/ViktorooReps/food-crisis-chatbot/assets/56936206/740816f2-2f59-427c-9e52-2538d6e52034)
![Screenshot 2024-05-27 222458](https://github.com/ViktorooReps/food-crisis-chatbot/assets/56936206/9eeef9ae-1def-4968-a83f-21a1b7723b39)

## Features
* Analyze food prices across multiple countries on a given time period.
* Display available commodities/countries/periods for comparison for given countries/dates/commodities.
* Automatic translation to any language with Google Translate integration
## Requirements

- Python 3.8

## Setup

1. Install required Python packages and SpaCy model:
    ```bash
    pip install -r requirements.txt
    ```

2. Download SpaCy model for English language:
    ```bash
    python -m spacy download en_core_web_md
    ```

3. Download fasttext language detection model (126MB):
    ```bash
    curl -o .\lid.176.bin https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin
    ```

4. Load HDX datasets and set up actions server:
    ```bash
    UPDATE_HDX_DATASETS=True rasa run actions
    ```
5. (optional) Update lookup tables for country names and commodities:
   ```bash
   python datasets/collect_lookup_tables.py
   ```

6. Run Rasa training (it will take a few minutes):
    ```bash
    rasa train
    ```

7. Load model endpoint:
    ```bash
    rasa run
    ```

Interact with chatbot either with shell:

```bash
rasa shell
```

Or with streamlit application:

```bash 
streamlit run streamlit_app.py
```
