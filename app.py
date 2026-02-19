import time
import base64
import tempfile
import os
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components
from audio_recorder_streamlit import audio_recorder
import whisper
from deep_translator import GoogleTranslator
from gtts import gTTS

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="Live Chat Translator", page_icon="💬", layout="wide")
st.title("💬 Live Chat Translator")

# ---------------- STYLE ----------------
STYLE = """
<style>
body {background-color:#0b141a;font-family:sans-serif;}
.chat-container{
    background-color:#ece5dd;
    padding:15px;
    height:520px;
    overflow-y:auto;
}
.msg-row{display:flex;margin:8px 0;}
.msg-right{justify-content:flex-end;}
.msg-left{justify-content:flex-start;}
.bubble{
    max-width:65%;
    padding:10px 14px;
    border-radius:10px;
    font-size:14px;
    color:white;
}
.green{background:#005c4b;border-top-right-radius:2px;}
.gray{background:#202c33;border-top-left-radius:2px;}
.time{font-size:10px;opacity:.7;text-align:right;margin-top:4px;}
audio{width:100%;margin-top:6px;}
</style>
"""

# ---------------- LANGUAGES ----------------
LANG_CHOICES = [
    ("Hindi","hi"),("Tamil","ta"),("Telugu","te"),("Kannada","kn"),
    ("Malayalam","ml"),("Spanish","es"),("French","fr"),
    ("German","de"),("Japanese","ja"),("English","en")
]
lang_map = dict(LANG_CHOICES)

colA, colB = st.columns(2)
with colA:
    you_lang_name = st.selectbox("Your language", list(lang_map.keys()), index=9)
with colB:
    teammate_lang_name = st.selectbox("Teammate language", list(lang_map.keys()), index=0)

YOU_LANG = lang_map[you_lang_name]
TEAM_LANG = lang_map[teammate_lang_name]

# ---------------- LOAD WHISPER ----------------
@st.cache_resource
def load_model():
    # medium gives much better Indian language accuracy
    return whisper.load_model("medium")

model = load_model()

# ---------------- SESSION INIT ----------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "mode_p1" not in st.session_state:
    st.session_state.mode_p1 = "text"

if "mode_p2" not in st.session_state:
    st.session_state.mode_p2 = "text"

if "mic_counter" not in st.session_state:
    st.session_state.mic_counter = {"p1": 0, "p2": 0}

if "text_counter" not in st.session_state:
    st.session_state.text_counter = {"p1": 0, "p2": 0}

# ---------------- UTILITIES ----------------

def translate_text(text, target_lang):
    if target_lang == "en":
        return text
    try:
        return GoogleTranslator(source="en", target=target_lang).translate(text)
    except:
        return text


def speech_to_english(audio_bytes):
    """
    Let Whisper auto-detect language
    and translate everything to English.
    This is more stable for Indian languages.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        f.write(audio_bytes)
        path = f.name

    result = model.transcribe(
        path,
        task="translate",  # 🔥 Always convert speech → English
        fp16=False
    )

    os.remove(path)
    return result.get("text", "").strip()


def generate_tts(text, lang):
    try:
        tts = gTTS(text=text, lang=lang)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            tts.save(f.name)
            audio = open(f.name, "rb").read()
        os.remove(f.name)
        return base64.b64encode(audio).decode()
    except:
        return None


# ---------------- ADD MESSAGE ----------------
def add_message(sender, original_english_text, audio_bytes=None):

    receiver_lang = TEAM_LANG if sender == "p1" else YOU_LANG

    translated_text = translate_text(original_english_text, receiver_lang)

    tts_audio = None
    if audio_bytes:  # Only generate TTS if original message was voice
        tts_audio = generate_tts(translated_text, receiver_lang)


    audio64 = base64.b64encode(audio_bytes).decode() if audio_bytes else None

    st.session_state.messages.append({
        "sender": sender,
        "english": original_english_text,
        "translated": translated_text,
        "tts": tts_audio,
        "audio": audio64,
        "time": time.time()
    })


# ---------------- RENDER CHAT ----------------
def render_chat(viewer):

    html = STYLE + '<div class="chat-container">'

    for msg in st.session_state.messages:

        is_sender = msg["sender"] == viewer

        # Sender sees English (internal format)
        # Receiver sees translated version
        show_text = msg["english"] if is_sender else msg["translated"]

        audio_html = ""
        # Show original audio to sender
        if is_sender and msg.get("audio"):
            audio_html += f'<audio controls src="data:audio/wav;base64,{msg["audio"]}"></audio>'
            
        if not is_sender and msg.get("tts"):
            audio_html = f'<audio controls src="data:audio/mp3;base64,{msg["tts"]}"></audio>'

        row = "msg-right" if is_sender else "msg-left"
        bubble = "green" if is_sender else "gray"
        t = datetime.fromtimestamp(msg["time"]).strftime("%H:%M")

        html += f'''
        <div class="msg-row {row}">
            <div class="bubble {bubble}">
                {show_text}
                {audio_html}
                <div class="time">{t}</div>
            </div>
        </div>
        '''

    html += "</div>"

    html += """
    <script>
    var chat = window.parent.document.querySelector('.chat-container');
    if(chat){chat.scrollTop = chat.scrollHeight;}
    </script>
    """

    components.html(html, height=560, scrolling=True)


# ---------------- INPUT AREA ----------------
def input_area(user):

    mode_key = "mode_" + user
    c1, c2, c3, c4 = st.columns([1,8,1,1])

    with c1:
        if st.button("🔗", key=f"attach_{user}"):
            st.session_state[mode_key] = "attach"

    with c4:
        if st.button("🎙️", key=f"micbtn_{user}"):
            st.session_state[mode_key] = "record"

    # -------- TEXT MODE --------
    if st.session_state[mode_key] == "text":

        msg = st.text_input(
            "msg",
            key=f"text_{user}_{st.session_state.text_counter[user]}",
            placeholder="Type message",
            label_visibility="collapsed"
        )

        send_click = st.button("➤", key=f"send_{user}")

        if msg and send_click:
            # Text input assumed English
            add_message(user, msg)
            st.session_state.text_counter[user] += 1
            st.rerun()

    # -------- FILE UPLOAD --------
    elif st.session_state[mode_key] == "attach":

        uploaded = st.file_uploader(
            "Upload audio",
            type=["wav","mp3","m4a"],
            key=f"upload_{user}"
        )

        if uploaded:
            with st.spinner("Processing audio..."):
                audio_bytes = uploaded.read()
                english_text = speech_to_english(audio_bytes)

            add_message(user, english_text, audio_bytes)
            st.session_state[mode_key] = "text"
            st.rerun()

    # -------- RECORD MODE --------
    elif st.session_state[mode_key] == "record":

        audio = audio_recorder(
            key=f"mic_{user}_{st.session_state.mic_counter[user]}",
            pause_threshold=2.0
        )

        if audio and len(audio) > 2000:
            with st.spinner("Processing audio..."):
                english_text = speech_to_english(audio)

            add_message(user, english_text, audio)

            st.session_state.mic_counter[user] += 1
            st.session_state[mode_key] = "text"
            st.rerun()


# ---------------- CLEAR CHAT ----------------
if st.button("🗑️ Clear Chat"):
    st.session_state.messages = []
    st.session_state.mic_counter = {"p1": 0, "p2": 0}
    st.session_state.text_counter = {"p1": 0, "p2": 0}
    st.rerun()


# ---------------- LAYOUT ----------------
col1, col2 = st.columns(2)

with col1:
    st.subheader("You")
    render_chat("p1")
    input_area("p1")

with col2:
    st.subheader("Teammate")
    render_chat("p2")
    input_area("p2")
