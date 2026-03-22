import streamlit as st
import os
import json
import csv
import time
from google import genai
import pypdf

# --- 1. CONFIG & CONSTANTS ---
st.set_page_config(page_title="PhishGuard AI", page_icon="🛡️")
TRACKER_FILE = "master_tracker.csv"
TOKEN_LIMIT_CHARS = 50000  # Approx 15k-20k tokens to stay safe under 250k limit

# --- 2. USER LOGIN & VISIT TRACKING ---
if "user_info" not in st.session_state:
    st.title("🛡️ PhishGuard-AI Access")
    with st.form("login_form"):
        st.markdown("### Please identify yourself to access the Cyber Mentor")
        name = st.text_input("Full Name*")
        email = st.text_input("Email Address (Optional)")
        purpose = st.selectbox("I am here for:", ["Learning", "Security Research", "Code Audit"])
        submit = st.form_submit_button("Enter Chatbot")
        
        if submit and name:
            user_id = name.lower().replace(" ", "_")
            st.session_state.user_info = {"name": name, "email": email, "id": user_id}
            
            # Record visit in background
            file_exists = os.path.isfile(TRACKER_FILE)
            with open(TRACKER_FILE, "a", newline="") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Timestamp", "Name", "Email", "Purpose"])
                writer.writerow([time.ctime(), name, email, purpose])
            
            st.rerun()
        elif submit:
            st.warning("Please enter your name to continue.")
    st.stop()

# --- 3. PRIVATE HISTORY LOGIC ---
USER_ID = st.session_state.user_info["id"]
HISTORY_FILE = f"history_{USER_ID}.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_history(messages):
    with open(HISTORY_FILE, "w") as f:
        json.dump(messages, f, indent=4)

# --- 4. SIDEBAR TOOLS & FILE PROCESSING ---
st.sidebar.header(f"👋 Welcome, {st.session_state.user_info['name']}")
st.sidebar.markdown("---")

if st.sidebar.button("🗑️ Clear My Chat"):
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
    st.session_state.messages = []
    st.rerun()

st.sidebar.subheader("📁 Security Analysis")
uploaded_file = st.sidebar.file_uploader("Upload logs or code", type=['txt', 'pdf', 'py', 'json'])

file_content = ""
if uploaded_file is not None:
    try:
        if uploaded_file.type == "application/pdf":
            reader = pypdf.PdfReader(uploaded_file)
            # Limit to first 15 pages to save tokens
            for page in reader.pages[:15]:
                file_content += page.extract_text()
        else:
            file_content = uploaded_file.read().decode("utf-8")
        
        # PREVENT 429 ERROR: Truncate large files
        if len(file_content) > TOKEN_LIMIT_CHARS:
            file_content = file_content[:TOKEN_LIMIT_CHARS] + "\n\n[NOTICE: File truncated to stay within AI limits.]"
            st.sidebar.warning("⚠️ File too large. Analyzing first 50k characters.")
        else:
            st.sidebar.success("✅ File context loaded!")
            
    except Exception as e:
        st.sidebar.error(f"Error reading file: {e}")

# --- 5. MAIN CHAT INTERFACE ---
st.title("🛡️ PhishGuard-AI Security Agent")

api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    st.error("🔑 API Key Missing! Please add 'GEMINI_API_KEY' in Space Settings > Secrets.")
else:
    client = genai.Client(api_key=api_key)

    if "messages" not in st.session_state:
        st.session_state.messages = load_history()

    # Display History
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat Input
    if prompt := st.chat_input("Ask a security question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Contextual Logic
        combined_input = prompt
        if file_content:
            combined_input = f"CONTEXT FROM UPLOADED FILE:\n{file_content}\n\nUSER QUESTION: {prompt}"

        with st.chat_message("assistant"):
            with st.spinner("🛡️ Analyzing..."):
                try:
                    # Using Gemini 3 Flash Stable ID
                    response = client.models.generate_content(
                        model="gemini-3-flash-preview", 
                        contents=f"""
                        You are PhishGuard, a professional Cybersecurity Mentor. 
                        Provide expert advice based on this request: {combined_input}
                        """
                    )
                    ai_reply = response.text
                    st.markdown(ai_reply)
                    
                    st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                    save_history(st.session_state.messages)
                    
                except Exception as e:
                    if "429" in str(e):
                        st.error("⚠️ Server Busy (Quota Reached). Please wait 30 seconds and try again.")
                    else:
                        st.error(f"⚠️ AI Error: {e}")