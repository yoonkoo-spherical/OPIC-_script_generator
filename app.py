import streamlit as st
import os
import random
import json
from google import genai
from google.genai import types

# Streamlit 페이지 기본 설정
st.set_page_config(page_title="OPIc Expression Builder", layout="centered")

def load_log_entries():
    """md 파일을 읽어 날짜(##) 기준으로 분리된 로그 리스트를 반환합니다."""
    file_path = "opic_study_log.md"
    if not os.path.exists(file_path):
        return []
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # "## "를 기준으로 텍스트를 나누어 개별 학습 기록 추출
    entries = content.split("\n## ")
    # 빈 항목 제외
    valid_entries = [e for e in entries if e.strip()]
    return valid_entries

def generate_vocab_content(entry_text):
    """Gemini API를 호출하여 예문과 단락을 JSON 형태로 생성합니다."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        st.error("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
        return None

    client = genai.Client(api_key=api_key)

    prompt = f"""
    당신은 제공된 OPIc 학습 로그에서 어휘나 표현을 추출하여 학습 자료를 생성하는 시스템입니다.
    다음 OPIc 스크립트 텍스트에서 어휘, 구동사, 또는 이디엄 중 하나를 선정하십시오.
    
    요구사항:
    1. 선정된 어휘의 의미를 한국어로 제공하십시오.
    2. 스크립트 본문에 포함된 기존 문장 1개를 찾아 예문으로 제공하십시오.
    3. 해당 어휘를 사용한 완전히 새로운 예문 2개를 생성하십시오.
    4. 위에서 도출된 3개의 예문 각각에 대해, 해당 예문이 포함된 자연스러운 문맥의 영어 단락(paragraph) 3개를 생성하십시오.
    5. 생성된 영어 예문 및 영어 단락에 대한 한국어 해석은 절대 포함하지 마십시오.

    [OPIc 스크립트]
    {entry_text}
    """

    try:
        # JSON 형태로 강제 반환하도록 Response Schema 설정
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "selected_word": {"type": "STRING", "description": "선정된 어휘 또는 표현"},
                        "meaning": {"type": "STRING", "description": "선정된 어휘의 한국어 의미"},
                        "original_sentence": {"type": "STRING", "description": "스크립트에 포함된 기존 예문"},
                        "new_sentence_1": {"type": "STRING", "description": "새로운 예문 1"},
                        "new_sentence_2": {"type": "STRING", "description": "새로운 예문 2"},
                        "paragraph_original": {"type": "STRING", "description": "original_sentence가 포함된 단락"},
                        "paragraph_1": {"type": "STRING", "description": "new_sentence_1이 포함된 단락"},
                        "paragraph_2": {"type": "STRING", "description": "new_sentence_2가 포함된 단락"}
                    },
                    "required": ["selected_word", "meaning", "original_sentence", "new_sentence_1", "new_sentence_2", "paragraph_original", "paragraph_1", "paragraph_2"]
                }
            )
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"콘텐츠 생성 중 오류가 발생했습니다: {e}")
        return None

# --- UI 렌더링 ---
st.title("OPIc Expression Builder")

# 세션 상태 초기화
if "vocab_data" not in st.session_state:
    st.session_state.vocab_data = None

# 새로고침 버튼 또는 초기 로드 시 동작
if st.button("새로고침") or st.session_state.vocab_data is None:
    entries = load_log_entries()
    if not entries:
        st.error("`opic_study_log.md` 파일을 찾을 수 없거나 내용이 없습니다. 파일 위치를 확인하십시오.")
    else:
        with st.spinner("스크립트에서 표현을 선정하고 문맥을 생성 중입니다..."):
            random_entry = random.choice(entries)
            data = generate_vocab_content(random_entry)
            if data:
                st.session_state.vocab_data = data

# 데이터가 존재할 경우 화면에 출력
if st.session_state.vocab_data:
    data = st.session_state.vocab_data
    
    st.subheader(f"**{data['selected_word']}** : {data['meaning']}")
    st.divider()

    st.markdown("### 1. Original Example (From Script)")
    st.write(data['original_sentence'])
    with st.expander("단락 보기 (Context Paragraph)"):
        st.write(data['paragraph_original'])

    st.markdown("### 2. New Example 1")
    st.write(data['new_sentence_1'])
    with st.expander("단락 보기 (Context Paragraph)"):
        st.write(data['paragraph_1'])

    st.markdown("### 3. New Example 2")
    st.write(data['new_sentence_2'])
    with st.expander("단락 보기 (Context Paragraph)"):
        st.write(data['paragraph_2'])
