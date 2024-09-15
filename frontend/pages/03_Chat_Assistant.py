"""
# Chat Assistant
Ask questions about ESG and get instant answers.
"""

import streamlit as st
from groq import Groq
from config import GROQ_API_KEY

st.set_page_config(
    page_title="Chat Assistant",
    page_icon="💬",
    layout="wide",
)

# Initialize session state for messages if it doesn't exist
if "messages" not in st.session_state:
    st.session_state.messages = []

def ask_question(user_question):
    client = Groq(api_key=GROQ_API_KEY)

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are an AI assistant specialized in ESG (Environmental, Social, and Governance) and CSR (Corporate Social Responsibility) topics. Provide accurate and helpful information on these subjects."
                },
                {
                    "role": "user",
                    "content": f"Answer the question: {user_question}. If it's not related to ESG or CSR topics, politely inform that the question should be related to those topics and provide a brief explanation of what ESG and CSR are."
                }
            ],
            model="llama3-8b-8192",
            temperature=0.5,
            max_tokens=500
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"An error occurred: {str(e)}"

st.title("ESG + CSR Chat Assistant")

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Prompt for user input and store it
if user_input := st.chat_input("You:"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Display user message in chat
    with st.chat_message("user"):
        st.markdown(user_input)

    # Get AI response
    with st.spinner("Thinking..."):
        response = ask_question(user_input)

    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})

    # Display assistant response in chat
    with st.chat_message("assistant"):
        st.markdown(response)

# Add a button to clear chat history
if st.button("Clear Chat History"):
    st.session_state.messages = []
    st.experimental_rerun()

# Display a brief explanation of ESG and CSR
st.sidebar.title("About ESG and CSR")
st.sidebar.info("""
ESG stands for Environmental, Social, and Governance. It refers to the three central factors in measuring the sustainability and societal impact of an investment in a company or business.

CSR stands for Corporate Social Responsibility. It is a self-regulating business model that helps a company be socially accountable to itself, its stakeholders, and the public.

Feel free to ask any questions related to these topics!
""")