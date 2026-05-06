import streamlit as st
import os
import random
import json
import re
from collections import defaultdict
from google import genai
from google.genai import types

# Streamlit 페이지 기본 설정 (3열 배치를 위해 wide 모드 적용)
st.set_page_config(page_title="OPIc Study Dashboard", layout="wide")

def clean_html_tags(text):
    """HTML 색상 태그를 Streamlit 네이티브 마크다운 문법으로 변환합니다."""
    # <strong style="color:blue;">텍스트</strong> -> :blue[**텍스트**]
    text = re.sub(
        r'<(?:strong|span|b)[^>]*color:\s*blue[^>]*>(.*?)</(?:strong|span|b)>', 
        r':blue[**\1**]', 
        text, 
        flags=re.IGNORECASE | re.DOTALL
    )
    return text

def parse_log_file():
    """
    md 파일을 읽어 날짜별로 그룹화하고, 
    인사말 제거 및 문제/답안/어휘를 하나의 온전한 세트로 파싱합니다.
    """
    file_path = "opic_study_log.md"
    if not os.path.exists(file_path):
        return []
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # '## YYYY-MM-DD' 형식의 날짜 블록을 기준으로 텍스트 1차 분할
    raw_entries = re.split(r'^##\s+(?=\d{4}-\d{2}-\d{2})', content, flags=re.MULTILINE)
    parsed_entries = []
    
    for entry in raw_entries:
        if not entry.strip():
            continue
        
        parts = entry.split('\n', 1)
        title_line = parts[0].strip()
        body = parts[1].strip() if len(parts) > 1 else ""
        
        # 날짜 추출 (YYYY-MM-DD)
        date_match = re.search(r'^(\d{4}-\d{2}-\d{2})', title_line)
        if not date_match:
            continue
        date_str = date_match.group(1)
        
        # 1. '---' 구분선을 기준으로 개별 문제 블록 분할 (질문+답안+어휘가 묶이도록 보장)
        blocks = re.split(r'\n\s*---\s*\n', body.strip())
        
        # '---' 구분선이 없을 경우를 대비한 예비 분할 로직 (### 묘사 등 기준)
        if len(blocks) <= 1:
            blocks = re.split(r'\n(?=###\s*(?:묘사|롤플레이|돌발|Description|Role-?play|Unexpected))', '\n' + body, flags=re.I)
            
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            
            # 'Q:' 또는 'Question'이 포함되지 않은 블록(인사말 등) 필터링
            if not re.search(r'Q:|Question', block, re.I):
                continue
            
            # HTML 파란색 태그를 마크다운으로 변환하여 깨짐 방지
            block = clean_html_tags(block)
            
            # 2. 제목 줄을 찾아 유형(Type)과 주제(Topic) 추출
            lines = block.split('\n')
            header_clean = ""
            
            # 상위 5줄 내에서 제목이 될 만한 헤더 찾기
            for line in lines[:5]:
                clean_line = re.sub(r'^#+\s*|\*+|\[|\]', '', line).strip()
                if re.search(r'(묘사|롤플레이|돌발|Description|Role-?play|Unexpected)', clean_line, re.I):
                    header_clean = clean_line
                    break
            
            # 못 찾았다면 첫 번째 줄을 헤더로 간주
            if not header_clean:
                header_clean = re.sub(r'^#+\s*|\*+|\[|\]', '', lines[0]).strip()
            
            # 문제 유형(Type) 추출
            type_str = "기타"
            if re.search(r'description|묘사', header_clean, re.I): type_str = "묘사"
            elif re.search(r'role-?play|롤플레이', header_clean, re.I): type_str = "롤플레이"
            elif re.search(r'unexpected|issue|돌발', header_clean, re.I): type_str = "돌발"
            
            # 주제(Topic) 추출
            topic_str = ""
            if ':' in header_clean:
                topic_str = header_clean.split(':', 1)[1].strip()
            elif '-' in header_clean:
                topic_str = header_clean.split('-', 1)[1].strip()
            else:
                topic_str = re.sub(r'(묘사|롤플레이|돌발|Description|Role-?play|Unexpected)', '', header_clean, flags=re.I).strip()
            
            topic_str = re.sub(r'\(|\)', '', topic_str).strip()
            
            # 추출된 주제가 빈칸이거나 무의미할 경우, Q: 질문 내용에서 일부분 발췌
            if not topic_str or topic_str.lower() in ['question', 'q', '기타']:
                for line in lines:
                    clean_line = re.sub(r'^#+\s*|\*+|\[|\]', '', line).strip()
                    if re.search(r'[a-zA-Z가-힣]', clean_line) and not re.search(r'Question|Q:|묘사|롤플레이|돌발', clean_line, re.I):
                        topic_str = clean_line[:35] + "..." if len(clean_line) > 35 else clean_line
                        break
                        
            if not topic_str:
                topic_str = "주제 생략"
                
            parsed_entries.append({
                "date": date_str,
                "type": type_str,
                "topic": topic_str,
                "content": block,
                "raw": block
            })
            
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
    5. 도출된 3개의 예문과 각각의 영어 단락은 서로 다른 주제를 다루도록 하십시오.
    6. 생성된 영어 예문 및 영어 단락에 대한 한국어 해석은 절대 포함하지 마십시오.

    [OPIc 스크립트]
    {entry_text}
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite", # 가장 빠르고 안정적인 모델 적용
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

# 데이터 파싱 및 로드
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
        st.markdown(clean_html_tags(data['original_sentence']))
        with st.expander("단락 보기 (Context Paragraph)"):
            st.markdown(clean_html_tags(data['paragraph_original']))

        st.markdown("### 2. New Example 1")
        st.markdown(clean_html_tags(data['new_sentence_1']))
        with st.expander("단락 보기 (Context Paragraph)"):
            st.markdown(clean_html_tags(data['paragraph_1']))

        st.markdown("### 3. New Example 2")
        st.markdown(clean_html_tags(data['new_sentence_2']))
        with st.expander("단락 보기 (Context Paragraph)"):
            st.markdown(clean_html_tags(data['paragraph_2']))

# --- Tab 2: Study Log Viewer ---
with tab2:
    if not entries:
        st.info("현재 저장된 학습 스크립트가 없습니다.")
    else:
        # 1. 날짜별로 데이터 그룹화
        grouped_entries = defaultdict(list)
        for entry in entries:
            grouped_entries[entry['date']].append(entry)
            
        # 2. 최신 날짜순 정렬
        sorted_dates = sorted(grouped_entries.keys(), reverse=True)
        
        # 3. 화면 렌더링 (날짜별 3열 구조)
        for date in sorted_dates:
            st.subheader(f"📅 {date}")
            items = grouped_entries[date]
            
            # 3개 단위로 잘라서 Row(행) 생성
            for i in range(0, len(items), 3):
                cols = st.columns(3)
                row_items = items[i:i+3]
                
                for j, entry in enumerate(row_items):
                    with cols[j]:
                        # 요청하신 "YYYY-MM-DD (문제유형) : 주제" 포맷 적용
                        title = f"{entry['date']} ({entry['type']}) : {entry['topic']}"
                        with st.expander(title):
                            # clean_html_tags 덕분에 파란색 글씨가 깔끔한 텍스트로 보입니다.
                            st.markdown(entry["content"])
            st.divider()
