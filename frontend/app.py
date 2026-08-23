import os
import time
import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Meeting Summarizer", page_icon="🗒️", layout="centered")
st.title("🗒️ Meeting Summarizer")
st.caption("Upload meeting audio → get a transcript, key decisions, and action items.")

tab_upload, tab_history = st.tabs(["Upload", "History"])

with tab_upload:
    uploaded_file = st.file_uploader(
        "Upload meeting audio",
        type=["mp3", "wav", "m4a", "mp4", "webm", "flac", "ogg"],
    )

    if uploaded_file and st.button("Transcribe & Summarize", type="primary"):
        with st.spinner("Uploading..."):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
            resp = requests.post(f"{BACKEND_URL}/upload-audio", files=files)

        if resp.status_code != 200:
            st.error(f"Upload failed: {resp.text}")
        else:
            meeting_id = resp.json()["id"]
            status_box = st.empty()
            progress = st.progress(0)

            step_map = {
                "pending": 10,
                "transcribing": 40,
                "summarizing": 75,
                "done": 100,
                "failed": 100,
            }

            while True:
                data = requests.get(f"{BACKEND_URL}/meetings/{meeting_id}").json()
                status = data["status"]
                status_box.info(f"Status: **{status}**")
                progress.progress(step_map.get(status, 10))

                if status == "done":
                    st.success("Done!")
                    st.subheader("Overview")
                    st.write(data["summary"]["overview"])

                    st.subheader("Key Decisions")
                    decisions = data["summary"].get("key_decisions", [])
                    if decisions:
                        for d in decisions:
                            st.markdown(f"- {d}")
                    else:
                        st.write("_No explicit decisions detected._")

                    st.subheader("Action Items")
                    items = data["summary"].get("action_items", [])
                    if items:
                        for item in items:
                            st.markdown(
                                f"- **{item.get('task')}** "
                                f"— Owner: {item.get('owner')} "
                                f"— Due: {item.get('due_date')}"
                            )
                    else:
                        st.write("_No action items detected._")

                    st.subheader("Open Questions")
                    questions = data["summary"].get("open_questions", [])
                    if questions:
                        for q in questions:
                            st.markdown(f"- {q}")
                    else:
                        st.write("_None flagged._")

                    with st.expander("Full transcript"):
                        st.text(data["transcript"])
                    break

                if status == "failed":
                    st.error(f"Processing failed: {data.get('error')}")
                    break

                time.sleep(2)

with tab_history:
    if st.button("Refresh list"):
        st.rerun()

    try:
        meetings = requests.get(f"{BACKEND_URL}/meetings").json()
    except requests.exceptions.ConnectionError:
        st.warning("Backend not reachable. Is it running?")
        meetings = []

    for m in meetings:
        with st.expander(f"#{m['id']} — {m['filename']} ({m['status']})"):
            if st.button("View details", key=f"view_{m['id']}"):
                data = requests.get(f"{BACKEND_URL}/meetings/{m['id']}").json()
                st.json(data)
