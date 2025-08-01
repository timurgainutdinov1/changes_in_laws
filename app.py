import logging
import os
import uuid

import streamlit as st
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_community.chat_models import GigaChat


def load_template(type):
    """
    Загружает текст запроса для LLM.
    """
    if type == "changes":
        with open("prompt_changes.txt", "r", encoding="utf-8") as file:
            template = file.read()
    else:
        with open("prompt_new_federal_law.txt", "r", encoding="utf-8") as file:
            template = file.read()

    return template


def get_model(model_name: str) -> str:
    """
    Возвращает модель GigaChat в зависимости от выбранного имени модели.

    Args:
        model_name (str): Имя модели GigaChat.

    Returns:
        str: Имя модели API GigaChat.
    """
    models = {
        "GigaChat-2": "GigaChat-2",
        "GigaChat-2-Pro": "GigaChat-2-Pro",
        "GigaChat-2-Max": "GigaChat-2-Max",
    }
    return models[model_name]


def create_files_upload_section():
    """
    Создает секцию загрузки файлов и выбора модели/версии API.
    """
    # Добавляем поле для ввода API ключа GigaChat
    api_key = st.text_input(
        "🔑 API ключ GigaChat", type="password", help="Введите ваш API ключ GigaChat"
    )
    st.session_state.api_key = api_key

    # Выбор модели
    model_name = st.selectbox(
        "Выберите модель GigaChat",
        [
            "GigaChat-2 ⚡",
            "GigaChat-2-Pro ⚡⚡",
            "GigaChat-2-Max ⚡⚡⚡",
        ],
        index=0,
    )
    # Приводим к ключу для get_model
    model_key = model_name.split(" ")[0]
    st.session_state.model = get_model(model_key)

    # Выбор scope
    scope = st.selectbox(
        "Выберите версию API",
        [
            "GIGACHAT_API_PERS (для физических лиц)",
            "GIGACHAT_API_CORP (для юридических лиц)",
            "GIGACHAT_API_B2B (для бизнеса)",
        ],
        index=0,
    ).split(" ")[0]
    st.session_state.scope = scope

    changes = st.file_uploader(
        "📄 Загрузите изменения закона (старая и новая версии)", ["pdf", "docx"]
    )
    new_federal_law = st.file_uploader(
        "📝 Загрузите обновленный закон РФ", ["pdf", "docx"]
    )
    region_law = st.file_uploader(
        "📝 Загрузите закон Курганской области", ["pdf", "docx"]
    )
    return changes, new_federal_law, region_law


def save_file(file, name=None):
    """
    Сохраняет загруженный файл с уникальным идентификатором.
    """
    unique_id = str(uuid.uuid4())
    file_name = f"{unique_id}_{name if name else file.name}"
    with open(file_name, "wb") as f:
        f.write(file.getbuffer())
    return file_name


def save_uploaded_files(files_to_save):
    """
    Сохраняет загруженные файлы.
    """
    saved_files = {}
    for key, file in files_to_save.items():
        if file:
            saved_files[key] = save_file(file)
    return saved_files


def delete_files(files):
    """
    Удаляет загруженные файлы.
    """
    try:
        for file in files:
            if file:
                os.remove(file)
    except Exception as e:
        logging.error(f"Ошибка при удалении файлов: {str(e)}")


def extract_text_from_file(uploaded_file: str) -> str:
    """
    Извлекает текстовое содержимое из файлов PDF, DOCX.
    """
    try:
        if uploaded_file.endswith(".docx"):
            return Docx2txtLoader(uploaded_file).load()[0].page_content
        elif uploaded_file.endswith(".pdf"):
            return PyPDFLoader(uploaded_file, mode="single").load()[0].page_content
        return ""  # Возвращаем пустую строку для неподдерживаемых форматов
    except Exception as e:
        logging.error(f"Ошибка при чтении файла {uploaded_file}: {str(e)}")
        st.error(f"Ошибка при чтении файла {uploaded_file}")
        return ""  # Возвращаем пустую строку в случае ошибки


def main():
    logging.basicConfig(level=logging.INFO)

    st.title("Ассистент для анализа изменений в законах")

    changes, new_federal_law, region_law = create_files_upload_section()

    start_check = st.button("🔍 Выполнить анализ изменений")

    if start_check:
        # Проверяем наличие API ключа
        if not st.session_state.get("api_key"):
            st.error("⚠️ Пожалуйста, введите API ключ GigaChat")
            return

        if (changes or new_federal_law) and region_law:
            # Сохранение загруженных файлов
            files_to_save = {
                "changes": changes,
                "new_federal_law": new_federal_law,
                "region_law": region_law,
            }
            saved_files = save_uploaded_files(files_to_save)

            # Извлечение текста из файлов
            changes_text = (
                extract_text_from_file(saved_files.get("changes", ""))
                if changes
                else ""
            )
            new_federal_law_text = (
                extract_text_from_file(saved_files.get("new_federal_law", ""))
                if new_federal_law
                else ""
            )
            region_law_text = (
                extract_text_from_file(saved_files.get("region_law", ""))
                if region_law
                else ""
            )

            # Загрузка текста запроса для LLM
            if changes_text:
                prompt = PromptTemplate.from_template(load_template("changes"))
                input_dict = {"changes": changes_text, "region_law": region_law_text}
            else:
                prompt = PromptTemplate.from_template(load_template("new_federal_law"))
                input_dict = {
                    "new_federal_law": new_federal_law_text,
                    "region_law": region_law_text,
                }

            llm = GigaChat(
                model=st.session_state.model,
                credentials=st.session_state.api_key,
                scope=st.session_state.scope,
                verify_ssl_certs=False,
                temperature=0,
                timeout=500,
                streaming=True,
            )

            chain = prompt | llm | StrOutputParser()

            output_spot = st.empty()
            partial = ""

            try:
                with st.spinner("Выполняется анализ изменений..."):
                    for chunk in chain.stream(input_dict):
                        partial += chunk
                        output_spot.markdown(partial)
                st.header("Результаты анализа", divider=True)
            except Exception as e:
                logging.error(f"При анализе возникла ошибка: {str(e)}")
                st.error("При анализе возникла ошибка. Пожалуйста попробуйте снова.")

            finally:
                delete_files(saved_files.values())

        # Обработка случаев, когда необходимые файлы не загружены
        elif region_law:
            msg = "⚠️ Перед запуском необходимо загрузить изменения закона или новый закон РФ"
            logging.error(msg)
            st.error(msg)
        elif changes or new_federal_law:
            msg = "⚠️ Перед запуском необходимо загрузить закон Курганской области"
            logging.error(msg)
            st.error(msg)
        else:
            msg = "⚠️ Перед запуском необходимо загрузить изменения закона или новый закон РФ, а также закон Курганской области"
            logging.error(msg)
            st.error(msg)


if __name__ == "__main__":
    main()
