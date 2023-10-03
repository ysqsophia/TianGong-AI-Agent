import os
import time
from datetime import datetime

import streamlit as st
from langchain.callbacks import StreamlitCallbackHandler
from langchain.schema import AIMessage, HumanMessage
from streamlit.web.server.websocket_headers import _get_websocket_headers

import modules.ui.ui_config as ui_config
import modules.ui.utils as utils
from modules.agents.memory.agent_history import xata_chat_history
from modules.agents.st_agent_selector import main_agent
from modules.sensitivity.sensitivity_checker import check_text_sensitivity
from modules.ui.utils import (
    check_password,
    delete_chat_history,
    fetch_chat_history,
    get_xata_db,
    initialize_messages,
    random_email,
)

ui = ui_config.create_ui_from_config()

os.environ["OPENAI_API_KEY"] = st.secrets["openai_api_key"]
os.environ["XATA_API_KEY"] = st.secrets["xata_api_key"]
os.environ["XATA_DATABASE_URL"] = st.secrets["xata_db_url"]

st.set_page_config(page_title=ui.page_title, layout="wide", page_icon=ui.page_icon)

if "username" not in st.session_state:
    if st.secrets["anonymous_allowed"]:
        st.session_state["username"] = random_email()
    else:
        st.session_state["username"] = _get_websocket_headers().get(
            "Username", "unknown@unknown.com"
        )

st.write(st.session_state["username"])

if ui.need_passwd is False:
    auth = True
else:
    auth = check_password()


if auth:
    # if True:
    # 注入CSS style, 修改最上渐变条颜色
    st.markdown(
        ui.page_markdown,
        unsafe_allow_html=True,
    )

    # SIDEBAR
    with st.sidebar:
        st.markdown(
            ui.sidebar_markdown,
            unsafe_allow_html=True,
        )
        col_image, col_text = st.columns([1, 4])
        with col_image:
            st.image(ui.sidebar_image)
        with col_text:
            st.title(ui.sidebar_title)
        st.subheader(ui.sidebar_subheader)

        with st.expander(ui.sidebar_expander_title):
            # txt2audio = st.checkbox(ui.txt2audio_checkbox_label, value=False)
            # chat_memory = st.checkbox(ui.chat_memory_checkbox_label, value=False)
            search_docs = st.toggle(ui.upload_docs_checkbox_label, value=False)

            if search_docs:
                uploaded_files = st.file_uploader(
                    label=ui.sidebar_file_uploader_title,
                    accept_multiple_files=True,
                    type=None,
                )
                if uploaded_files != [] and uploaded_files != st.session_state.get(
                    "uploaded_files"
                ):
                    st.session_state["uploaded_files"] = uploaded_files
                    with st.spinner(ui.sidebar_file_uploader_spinner):
                        st.session_state["xata_db"] = get_xata_db(uploaded_files)

        st.divider()

        col_newchat, col_delete = st.columns([1, 1])
        with col_newchat:
            new_chat = st.button(
                ui.sidebar_newchat_button_label, use_container_width=True
            )
        if new_chat:
            # avoid rerun for new random email,no use clear()
            del st.session_state["selected_chat_id"]
            del st.session_state["timestamp"]
            del st.session_state["first_run"]
            del st.session_state["messages"]
            del st.session_state["xata_history"]
            try:
                del st.session_state["uploaded_files"]
            except:
                pass
            try:
                del st.session_state["xata_db"]
            except:
                pass
            st.rerun()

        with col_delete:
            delete_chat = st.button(
                ui.sidebar_delete_button_label, use_container_width=True
            )
        if delete_chat:
            delete_chat_history(st.session_state["selected_chat_id"])
            # avoid rerun for new random email,no use clear()
            del st.session_state["selected_chat_id"]
            del st.session_state["timestamp"]
            del st.session_state["first_run"]
            del st.session_state["messages"]
            del st.session_state["xata_history"]
            try:
                del st.session_state["uploaded_files"]
            except:
                pass
            try:
                del st.session_state["xata_db"]
            except:
                pass
            st.rerun()

        if "first_run" not in st.session_state:
            timestamp = time.time()
            st.session_state["timestamp"] = timestamp
        else:
            timestamp = st.session_state["timestamp"]

        try:  # fetch chat history from xata
            table_map = fetch_chat_history(st.session_state["username"])

            # add new chat to table_map
            table_map_new = {
                str(timestamp): datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
                + " : New Chat"
            }

            # Merge two dicts
            table_map = table_map_new | table_map
        except:  # if no chat history in xata
            table_map = {
                str(timestamp): datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
                + " : New Chat"
            }

        # Get all keys from table_map into a list
        entries = list(table_map.keys())
        # Check if selected_chat_id exists in session_state, if not set default as the first entry
        if "selected_chat_id" not in st.session_state:
            st.session_state["selected_chat_id"] = entries[0]

        # Update the selectbox with the current selected_chat_id value
        current_chat_id = st.selectbox(
            label=ui.current_chat_title,
            label_visibility="collapsed",
            options=entries,
            format_func=lambda x: table_map[x],
        )

        # Save the selected value back to session state
        st.session_state["selected_chat_id"] = current_chat_id

        if "first_run" not in st.session_state:
            st.session_state["xata_history"] = xata_chat_history(
                _session_id=current_chat_id
            )
            st.session_state["first_run"] = True
        else:
            st.session_state["xata_history"] = xata_chat_history(
                _session_id=current_chat_id
            )
            st.session_state["messages"] = initialize_messages(
                st.session_state["xata_history"].messages
            )

    @utils.enable_chat_history
    def main():
        if user_query := st.chat_input(placeholder=ui.chat_human_placeholder):
            st.chat_message("user", avatar=ui.chat_user_avatar).markdown(user_query)
            st.session_state["messages"].append({"role": "user", "content": user_query})
            human_message = HumanMessage(
                content=user_query,
                additional_kwargs={"id": st.session_state["username"]},
            )
            st.session_state["xata_history"].add_message(human_message)

            # check text sensitivity
            answer = check_text_sensitivity(user_query)["answer"]
            if answer is not None:
                with st.chat_message("assistant", avatar=ui.chat_ai_avatar):
                    st.markdown(answer)
                    st.session_state["messages"].append(
                        {
                            "role": "assistant",
                            "content": answer,
                        }
                    )
                    ai_message = AIMessage(
                        content=answer,
                        additional_kwargs={"id": st.session_state["username"]},
                    )
                    st.session_state["xata_history"].add_message(ai_message)
            else:
                agent, user_prompt = main_agent(user_query)
                with st.chat_message("assistant", avatar=ui.chat_ai_avatar):
                    st_cb = StreamlitCallbackHandler(st.container())
                    response = agent().run(
                        {
                            "input": user_prompt,
                            "chat_history": st.session_state["xata_history"].messages,
                        },
                        callbacks=[st_cb],
                    )
                    st.markdown(response)
                    # if txt2audio:
                    #     utils.show_audio_player(response)
                    st.session_state["messages"].append(
                        {
                            "role": "assistant",
                            "content": response,
                        }
                    )
                    ai_message = AIMessage(
                        content=response,
                        additional_kwargs={"id": st.session_state["username"]},
                    )
                    st.session_state["xata_history"].add_message(ai_message)

            if len(st.session_state["messages"]) == 3:
                st.rerun()

    if __name__ == "__main__":
        main()
