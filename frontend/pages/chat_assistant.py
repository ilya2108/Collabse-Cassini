import streamlit as st
from groq import Groq
from config import GROQ_API_KEY

def ask_question(user_question):
    st.title("ESG + CSR Chat Assistant")
    client = Groq(
        api_key = GROQ_API_KEY,
    )

    if user_question:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": f"Answer the question: {user_question}. If it's not related to ESG or CSR topic - say that the question should be related to those topics.",
                }
            ],
            model="llama3-8b-8192",
        )
        st.success(chat_completion.choices[0].message.content)
    else:
        st.warning("Please enter a question.")

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

    response = ask_question(user_input)
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})

    # Display assistant response in chat
    with st.chat_message("assistant"):
        st.markdown(response)