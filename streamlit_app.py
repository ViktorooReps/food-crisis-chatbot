import uuid

import streamlit as st
import requests
from googletrans import Translator
import pandas as pd
import os


# Initialize translator
translator = Translator()

# Path to the CSV file where translations will be cached
TRANSLATIONS_FILE = 'translations_cache.csv'


# Function to load translations from CSV
def load_translations():
    if os.path.exists(TRANSLATIONS_FILE):
        return pd.read_csv(TRANSLATIONS_FILE)
    return pd.DataFrame(columns=['text', 'language', 'translation'])


# Function to save translations to CSV
def save_translations(df):
    df.to_csv(TRANSLATIONS_FILE, index=False)


# Load existing translations
translations_cache = load_translations()


# Function to translate text and cache the result
@st.cache_data(show_spinner=False)
def translate_text(text, dest_language):
    global translations_cache

    # Check if the translation is already cached
    cached_translation = translations_cache[
        (translations_cache['text'] == text) & (translations_cache['language'] == dest_language)
        ]
    if not cached_translation.empty:
        return cached_translation['translation'].values[0]

    with st.spinner():
        # Translate and cache the result
        translation = translator.translate(text, dest=dest_language).text
        new_translation = pd.DataFrame([[text, dest_language, translation]], columns=['text', 'language', 'translation'])

        translations_cache = pd.concat([translations_cache, new_translation], ignore_index=True)
        save_translations(translations_cache)

        return translation


# Function to update conversation on the screen
def update_conversation(user_message, bot_message, image_paths=None, table_data=None):
    # Check if 'conversation' is already in the state
    if 'conversation' not in st.session_state:
        st.session_state.conversation = []

    # Append user and bot responses to the conversation history
    st.session_state.conversation.append((user_message, bot_message, image_paths, table_data))


if "sender_id" not in st.session_state:
    st.session_state.sender_id = str(uuid.uuid4())

# Title of your web application
st.title('Price Watch')

# Language selection dropdown
languages = {
    'English': 'en',
    'Spanish': 'es',
    'French': 'fr',
    'German': 'de',
    'Chinese': 'zh-cn',
    'Japanese': 'ja',
    'Russian': 'ru',
    'Hindi': 'hi',
    'Persian': 'fa'
}

# Initialize selected language in session state if not already set
if 'selected_language' not in st.session_state:
    st.session_state.selected_language = 'English'

with st.expander(translate_text('Settings', languages[st.session_state.selected_language]), expanded=False):
    # Language selection dropdown
    choices = sorted(languages.keys())
    selected_language = st.selectbox(
        translate_text('Select Language', languages[st.session_state.selected_language]),
        choices,
        index=choices.index(st.session_state.selected_language)
    )

    # Update selected language in session state
    if selected_language != st.session_state.selected_language:
        st.session_state.selected_language = selected_language
        st.rerun()

    # Clear conversation history button
    if st.button(
            translate_text('Clear Conversation', languages[st.session_state.selected_language]),
            type='primary'
    ):
        if 'conversation' in st.session_state:
            st.session_state.conversation = []
            st.rerun()

chat_container = st.container()

with chat_container:
    # Display message history
    if 'conversation' in st.session_state:
        conversation = []
        for i, (message_user, message_bot, image_paths, table_data) in enumerate(st.session_state.conversation):
            if message_user:
                with st.chat_message('user'):
                    st.markdown(message_user)

            with st.chat_message('assistant'):
                if message_bot:
                    translated_message = translate_text(message_bot, languages[st.session_state.selected_language])
                    st.markdown(translated_message)
                if image_paths:
                    for path in image_paths:
                        st.image(path)
                if table_data:
                    st.dataframe(pd.DataFrame(**table_data).astype(str), hide_index=True, use_container_width=True)

if prompt := st.chat_input(translate_text(
        "Type your message:",
        languages[st.session_state.selected_language])
):
    if len(prompt):
        with chat_container:
            with st.chat_message('user'):
                st.markdown(prompt)

        with st.spinner(translate_text(
                'Getting response from chatbot...',
                languages[st.session_state.selected_language]
        )):
            # Rasa server URL where the Rasa server is running
            rasa_server_url = 'http://localhost:5005/webhooks/rest/webhook'
            # Define the payload
            payload = {
                "sender": st.session_state.sender_id,
                "message": prompt
            }
            # POST request to send the message to the Rasa server
            response = requests.post(rasa_server_url, json=payload)

            # Get bot response and update the conversation in session state
            if response.status_code == 200:
                response_json = response.json()
                print(response_json)

                bot_responses = []
                images = []
                table_data = None

                for bot_response in response_json:
                    if 'text' in bot_response:
                        bot_responses.append(bot_response['text'])  # Adjust based on response structure

                    if 'image' in bot_response:
                        images.extend(eval(bot_response['image']))

                    if 'table' in bot_response.get('custom', {}):
                        table_data = bot_response['custom']['table']

                first_response = bot_responses[0] if len(bot_responses) else None

                # assign all images and table data to the first response
                update_conversation(prompt.strip(), first_response, images, table_data)

                # all responses except the first one are without images
                for bot_response in bot_responses[1:]:
                    update_conversation(None, bot_response, [])

                st.rerun()
            else:
                error_message = translate_text(
                    "Failed to get response from the bot.",
                    languages[st.session_state.selected_language]
                )
                update_conversation(prompt, error_message)
                st.rerun()
