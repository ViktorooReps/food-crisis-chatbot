import streamlit as st
import requests


# Function to update conversation on the screen
def update_conversation(user_message, bot_message, image_path=None):
    # Check if 'conversation' is already in the state
    if 'conversation' not in st.session_state:
        st.session_state.conversation = []

    # Append user and bot responses to the conversation history
    st.session_state.conversation.append((user_message, bot_message, image_path))


# Title of your web application
st.title('Rasa Chatbot')

# Display message history
if 'conversation' in st.session_state:
    conversation = []
    for i, (message_user, message_bot, image_path) in enumerate(st.session_state.conversation):
        st.markdown('**' + message_user + '**')
        with st.container(border=True):
            st.markdown(message_bot)
            if image_path:
                st.image(image_path)

# Text input for user message
user_input = st.text_input("Type your message:")

# Button to send the message
if st.button("Send"):
    if user_input:
        # Rasa server URL where the Rasa server is running
        rasa_server_url = 'http://localhost:5005/webhooks/rest/webhook'
        # Define the payload
        payload = {
            "sender": "user",
            "message": user_input
        }
        # POST request to send the message to the Rasa server
        response = requests.post(rasa_server_url, json=payload)

        # Get bot response and update the conversation in session state
        if response.status_code == 200:
            response_json = response.json()
            bot_response = response_json[0]['text']  # Adjust based on response structure
            image_path = response_json[1].get('image')
            update_conversation(user_input, bot_response, image_path)
            st.rerun()
        else:
            error_message = "Failed to get response from the bot."
            update_conversation(user_input, error_message)
            st.rerun()
    else:
        st.warning('Please enter some text to send.')

# Clear conversation history
if st.button("Clear Conversation"):
    if 'conversation' in st.session_state:
        st.session_state.conversation = []
        st.rerun()
