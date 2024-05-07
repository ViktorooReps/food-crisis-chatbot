# Food Crisis ChatBot

## Requirements

- Python 3.8

## Setup

Install required Python packages: 
```bash
pip install -r requirements.txt
```

Run Rasa training (it will take a few minutes):

```bash
rasa train
```

Load model endpoint:

```bash
rasa run
```

Set up actions server:

```bash
rasa run actions
```

Interact with chatbot either with shell:

```bash
rasa shell
```

Or with streamlit application:
```bash 
streamlit run streamlit_app.py
```
