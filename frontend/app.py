import streamlit as st
import requests

st.set_page_config(page_title="Blostem Vernacular Advisor", page_icon="🏦")

st.title("🏦 Vernacular Financial Advisor")
st.write("Ask questions about FD, savings, and taxes in English, Hindi, or Hinglish.")

# Sidebar
st.sidebar.header("Settings")
language = st.sidebar.selectbox(
    "Preferred Language",
    ["Hinglish", "Hindi", "English"]
)
api_url = st.sidebar.text_input("API URL", "http://localhost:8000/ask")

# Chat UI
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("E.g., FD pe TDS kab katega?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        try:
            response = requests.post(
                api_url,
                json={"query": prompt, "language": language}
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "No answer found.")
                sources = data.get("sources", [])
                
                # Format response
                full_response = f"{answer}\n\n**Sources:**\n"
                for i, src in enumerate(sources):
                    title = src.get("title", "Unknown Source")
                    full_response += f"{i+1}. {title}\n"
                
                message_placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
                # Show detailed chunks in expander
                if sources:
                    with st.expander("View Source Snippets"):
                        for src in sources:
                            st.write(f"**{src.get('title')}**")
                            st.info(src.get('text'))
            else:
                error_msg = f"Error {response.status_code}: {response.text}"
                message_placeholder.markdown(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Connection error: {e}. Is the FastAPI server running?"
            message_placeholder.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
