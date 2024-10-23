import os
import requests
import streamlit as st

# API endpoint for completions
COMPLETIONS_URL = os.getenv("COMPLETIONS_URL", "http://127.0.0.1:8000/llm/completions")

# Example Bearer Token (if needed)
# USER_BEARER_TOKEN = "your_default_bearer_token_here"

# Initialize session state for messages
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar with About and Example Questions
with st.sidebar:
    st.header("About")
    st.markdown(
        """
        This chatbot interacts with a local Language Model API to generate responses based on your input.
        Simply enter your message, and the assistant will reply accordingly.
        """
    )

    st.header("Örnek Sorular")
    st.markdown("- Bugün hangi konuları çalışmalıyım?")
    st.markdown("- Yarın sınav var, hangi konulara çalışmalıyım?")
    st.markdown("- Ders çalışırken nasıl daha verimli olabilirim?")

# Main chatbot section
st.title("LLM Assistant Chatbot")
st.info(
    """Ask me anything, and I'll do my best to assist you!"""
)

# Display chat messages
for message in st.session_state.messages:
    if message["role"] == "user":
        with st.chat_message("user"):
            st.markdown(message["content"])
    else:
        with st.chat_message("assistant"):
            st.markdown(message["content"])
            if message.get("intermediate_steps"):
                with st.expander("Intermediate Steps"):
                    st.write(message["intermediate_steps"])

# User input
if prompt := st.chat_input("What do you want to know?"):
    # Display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Prepare the payload
    payload = {
        "input": prompt
    }

    # Set the headers
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }

    # Send the POST request to the API
    with st.spinner("Generating response..."):
        try:
            response = requests.post(COMPLETIONS_URL, headers=headers, json=payload)
            response.raise_for_status()  # Raise an error for bad status codes
            data = response.json()

            # Extract output and intermediate steps
            output = data.get("output", "No response received.")
            intermediate_steps = data.get("intermediate_steps", [])

            # Append assistant's response to messages
            st.session_state.messages.append({
                "role": "assistant",
                "content": output,
                "intermediate_steps": intermediate_steps
            })

            # Display assistant's response
            with st.chat_message("assistant"):
                st.markdown(output)
                if intermediate_steps:
                    with st.expander("Intermediate Steps"):
                        for step in intermediate_steps:
                            st.write(step)

        except requests.exceptions.HTTPError as http_err:
            error_message = f"HTTP error occurred: {http_err}"
            st.error(error_message)
            st.session_state.messages.append({
                "role": "assistant",
                "content": error_message
            })
        except requests.exceptions.ConnectionError:
            error_message = "Could not connect to the API. Is it running?"
            st.error(error_message)
            st.session_state.messages.append({
                "role": "assistant",
                "content": error_message
            })
        except requests.exceptions.Timeout:
            error_message = "The request timed out."
            st.error(error_message)
            st.session_state.messages.append({
                "role": "assistant",
                "content": error_message
            })
        except requests.exceptions.RequestException as err:
            error_message = f"An error occurred: {err}"
            st.error(error_message)
            st.session_state.messages.append({
                "role": "assistant",
                "content": error_message
            })
        except ValueError:
            error_message = "Failed to parse the response from the API."
            st.error(error_message)
            st.session_state.messages.append({
                "role": "assistant",
                "content": error_message
            })
