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

# ---------------- PAGE ----------------
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

# ---------------- LANGUAGE ----------------
LANG_CHOICES=[
    ("Hindi","hi"),("Tamil","ta"),("Telugu","te"),("Kannada","kn"),
    ("Malayalam","ml"),("Spanish","es"),("French","fr"),
    ("German","de"),("Japanese","ja"),("English","en")
]
lang_map=dict(LANG_CHOICES)

colA,colB=st.columns(2)
with colA:
    you_lang_name=st.selectbox("Your language",list(lang_map.keys()),index=9)
with colB:
    teammate_lang_name=st.selectbox("Teammate language",list(lang_map.keys()),index=0)

YOU_LANG=lang_map[you_lang_name]
TEAM_LANG=lang_map[teammate_lang_name]

# -------- detect language change (refresh audio) --------
if "lang_version" not in st.session_state:
    st.session_state.lang_version=0

state=f"{YOU_LANG}-{TEAM_LANG}"
if st.session_state.get("last_state")!=state:
    st.session_state.lang_version+=1
    st.session_state.last_state=state

# ---------------- WHISPER ----------------
@st.cache_resource
def load_model():
    return whisper.load_model("tiny")
model=load_model()

# ---------------- SESSION ----------------
if "messages" not in st.session_state:
    st.session_state.messages=[]
if "input_counter" not in st.session_state:
    st.session_state.input_counter={"p1":0,"p2":0}
if "mode_p1" not in st.session_state:
    st.session_state.mode_p1="text"
if "mode_p2" not in st.session_state:
    st.session_state.mode_p2="text"

# ---------------- TRANSLATE ----------------
@st.cache_data(show_spinner=False)
def translate(text,src,tgt):
    if src==tgt:return text
    try:return GoogleTranslator(source=src,target=tgt).translate(text)
    except:return text

# ---------------- SPEECH TO TEXT ----------------
def speech_to_text(audio_bytes):
    with tempfile.NamedTemporaryFile(delete=False,suffix=".wav") as f:
        f.write(audio_bytes);path=f.name
    result=model.transcribe(path,fp16=False)
    os.remove(path)
    return result.get("text","").strip()

# ---------------- TTS ----------------
def generate_tts(text,lang,uid):
    tts=gTTS(text=text,lang=lang)
    with tempfile.NamedTemporaryFile(delete=False,suffix=".mp3") as f:
        tts.save(f.name)
        audio=open(f.name,"rb").read()
    os.remove(f.name)
    return base64.b64encode(audio).decode()

# ---------------- ADD MESSAGE ----------------
def add_message(sender,text,audio_bytes=None):
    sender_lang = YOU_LANG if sender=="p1" else TEAM_LANG
    audio64 = base64.b64encode(audio_bytes).decode() if audio_bytes else None
    st.session_state.messages.append({
        "sender":sender,
        "text":text,
        "lang":sender_lang,
        "audio":audio64,
        "time":time.time()
    })

# ---------------- RENDER CHAT ----------------
def render_chat(viewer):

    html=STYLE+'<div class="chat-container">'

    for msg in st.session_state.messages:

        sender_lang=msg["lang"]
        target_lang=YOU_LANG if viewer=="p1" else TEAM_LANG
        show=translate(msg["text"],sender_lang,target_lang)

        audio_html=""
        if msg.get("audio"):
            uid=str(msg["time"])+viewer+str(st.session_state.lang_version)
            audio_data=generate_tts(show,target_lang,uid)
            audio_html=f'<audio controls src="data:audio/mp3;base64,{audio_data}#v={uid}"></audio>'

        row="msg-right" if msg["sender"]==viewer else "msg-left"
        bubble="green" if msg["sender"]==viewer else "gray"
        t=datetime.fromtimestamp(msg["time"]).strftime("%H:%M")

        html+=f'''
        <div class="msg-row {row}">
            <div class="bubble {bubble}">
                {show}
                {audio_html}
                <div class="time">{t}</div>
            </div>
        </div>
        '''

    html+='</div>'

    components.html(html,height=560,scrolling=True)

# ---------------- INPUT AREA ----------------
def input_area(user):

    mode_key="mode_"+user
    c1,c2,c3,c4=st.columns([1,8,1,1])

    with c1:
        if st.button("🔗",key=f"attach_{user}"):
            st.session_state[mode_key]="attach"

    with c4:
        if st.button("🎙️",key=f"micbtn_{user}"):
            st.session_state[mode_key]="record"

    if st.session_state[mode_key]=="text":
        text_key=f"text_{user}_{st.session_state.input_counter[user]}"

        with c2:
            msg=st.text_input("msg",key=text_key,placeholder="Type message",label_visibility="collapsed")

        with c3:
            send_click=st.button("➤",key=f"send_{user}")

        if msg and (send_click or msg):
            add_message(user,msg)
            st.session_state.input_counter[user]+=1
            st.rerun()

    elif st.session_state[mode_key]=="attach":
        uploaded=st.file_uploader("Upload audio",type=["wav","mp3","m4a"],key=f"upload_{user}")
        if uploaded:
            audio_bytes=uploaded.read()
            text=speech_to_text(audio_bytes)
            add_message(user,text,audio_bytes)
            st.session_state[mode_key]="text"
            st.rerun()

    elif st.session_state[mode_key]=="record":
        audio=audio_recorder(key=f"mic_{user}",pause_threshold=2.0)
        if audio and len(audio)>2000:
            text=speech_to_text(audio)
            add_message(user,text,audio)
            st.session_state[mode_key]="text"
            st.rerun()

# ---------------- LAYOUT ----------------
col1,col2=st.columns(2)

with col1:
    st.subheader("You")
    render_chat("p1")
    input_area("p1")

with col2:
    st.subheader("Teammate")
    render_chat("p2")
    input_area("p2")