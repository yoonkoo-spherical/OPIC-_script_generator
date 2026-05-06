import streamlit as st
import os
import random
import json
import re
from google import genai
from google.genai import types

# Streamlit 페이지 기본 설정
st.set_page_config(page_title="OPIc Study Dashboard", layout="centered")

def parse_log_file():
    """md 파일을 읽어 '## ' 태그를 기준으로 날짜(제목)와 스크립트 본문을 분리하여 반환합니다."""
    file_path = "opic_study_log.md"
    if not os.path.exists(file_path):
        return []
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # '## '로 시작하는 줄을 기준으로 텍스트 분할
    raw_entries = re.split(r'^##\s+', content, flags=re.MULTILINE)
    
    parsed_entries = []
    for entry in raw_entries:
        if not entry.strip():
            continue
        
        # 첫 번째 줄은 제목(날짜), 나머지는 본문 내용으로 분리
        parts = entry.split('\n', 1)
        title = parts[0].strip()
        body = parts[1].strip() if len(parts) > 1 else ""
        
        parsed_entries.append({
            "title": title,
            "content": body,
            "raw": entry # Gemini 모델에 전달할 전체 텍스트
        })
        
    # 최신 날짜가 위로 오도록 정렬 (선택 사항)
    parsed_entries.sort(key=lambda x: x["title"], reverse=True)
    return parsed_entries

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
    5. 3개의 예문 및 영어 단락은 서로 다른, 유사하지 않은 주제들을 다루어야 합니다.
    6. 생성된 영어 예문 및 영어 단락에 대한 한국어 해석은 절대 포함하지 마십시오.

    [OPIc 스크립트]
    {entry_text}
    """

    try:
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
st.title("OPIc Study Dashboard")

# 탭 생성
tab1, tab2 = st.tabs(["Expression Builder", "Study Log Viewer"])

# 데이터 로드
entries = parse_log_file()

# --- Tab 1: Expression Builder ---
with tab1:
    if "vocab_data" not in st.session_state:
        st.session_state.vocab_data = None

    if st.button("새로고침") or st.session_state.vocab_data is None:
        if not entries:
            st.error("`opic_study_log.md` 파일을 찾을 수 없거나 내용이 없습니다.")
        else:
            with st.spinner("스크립트에서 표현을 선정하고 문맥을 생성 중입니다..."):
                random_entry = random.choice(entries)
                data = generate_vocab_content(random_entry["raw"])
                if data:
                    st.session_state.vocab_data = data

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


# --- Tab 2: Study Log Viewer ---
with tab2:
    st.header("Daily OPIc Scripts")
    
    if not entries:
        st.info("현재 저장된 학습 스크립트가 없습니다.")
    else:
        # 파싱된 항목들을 반복하며 expander 생성
        for entry in entries:
            with st.expander(f"📅 {entry['title']}"):
                # Markdown 형식 그대로 렌더링
                st.markdown(entry["content"])
