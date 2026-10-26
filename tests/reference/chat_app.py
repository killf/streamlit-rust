"""Reference fixture: chat elements on 1.66.1.

Driven by the m5 chat probe (target/checks/m5-chat-pyref): two chat
messages with different avatars, and the chat input widget committed with
Enter.
"""
import streamlit as st

with st.chat_message("user"):
    st.write("hello from user")

with st.chat_message("assistant", avatar=":material/robot:"):
    st.write("hello from assistant")

prompt = st.chat_input("Say something")
if prompt:
    st.write(f"echo: {prompt}")
