import streamlit as st
import os
import random
import json
import re
from collections import defaultdict
from google import genai
from google.genai import types

# Streamlit 페이지 기본 설정 (와이드 모드 적용 권장)
st.set_page_config(page_title="OPIc Study Dashboard", layout="wide")

def parse_log_file():
    """
    md 파일을 읽어 날짜별로 그룹화하고, 
    인사말 제거, 문제/답안/어휘를 하나의 세트로 묶어 파싱합니다.
    (LLM 토큰 소모가 없는 100% 로컬 텍스트 처리 함수입니다.)
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
        
        # '### ' 또는 '## 1.' 등으로 시작하는 문제 단락을 기준으로 본문 분할
        # (이때 #### 인 단어장(Vocab) 부분은 잘리지 않고 문제와 한 덩어리로 유지됨)
        blocks = re.split(r'\n(?=###\s|##\s\d\.)', '\n' + body)
        
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            
            # 'Q:' 또는 'Question'이 포함된 블록만 추출 (인사말 필터링)
            if not re.search(r'Q:|Question', block, re.I):
                continue
            
            # 끝부분에 남아있는 불필요한 '---' 구분선 제거
            block = re.sub(r'\n---+[\s]*$', '', block).strip()
            
            lines = block.split('\n')
            header_raw = lines[0]
            header_clean = re.sub(r'^#+\s*|\*+|\[|\]', '', header_raw).strip()
            
            # 1. 문제 유형 추출
            type_str = "기타"
            if re.search(r'description|묘사', header_clean, re.I): type_str = "묘사"
            elif re.search(r'role-?play|롤플레이', header_clean, re.I): type_str = "롤플레이"
            elif re.search(r'unexpected|issue|돌발', header_clean, re.I): type_str = "돌발"
            
            # 2. 주제 추출
            topic_str = ""
            if ':' in header_clean:
                topic_str = header_clean.split(':', 1)[1].strip()
            elif '-' in header_clean:
                topic_str = header_clean.split('-', 1)[1].strip()
            topic_str = re.sub(r'\(|\)', '', topic_str).strip()
            
            ignore_topics = ['묘사', 'roleplay', 'role-play', 'unexpected', 'description', '롤플레이', '돌발', 'issue', '']
            
            # 주제가 추출되지 않았을 경우 Q: 줄에서 발췌
            if not topic_str or topic_str.lower() in ignore_topics:
                for line in lines:
                    if re.match(r'^\*?\*?Q:', line.strip()):
                        clean_q = re.sub(r'^\*?\*?Q:\s*', '', line.strip())
                        clean_q = re.sub(r'\*+', '', clean_q)
                        topic_str = clean_q[:35] + "..." if len(clean_q) > 35 else clean_q
                        break
                        
            if not topic_str or topic_str.lower() in ignore_topics:
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

        # HTML 태그 렌더링이 필요할 수 있으므로 unsafe_allow_html=True 적용
        st.markdown("### 1. Original Example (From Script)")
        st.markdown(data['original_sentence'], unsafe_allow_html=True)
        with st.expander("단락 보기 (Context Paragraph)"):
            st.markdown(data['paragraph_original'], unsafe_allow_html=True)

        st.markdown("### 2. New Example 1")
        st.markdown(data['new_sentence_1'], unsafe_allow_html=True)
        with st.expander("단락 보기 (Context Paragraph)"):
            st.markdown(data['paragraph_1'], unsafe_allow_html=True)

        st.markdown("### 3. New Example 2")
        st.markdown(data['new_sentence_2'], unsafe_allow_html=True)
        with st.expander("단락 보기 (Context Paragraph)"):
            st.markdown(data['paragraph_2'], unsafe_allow_html=True)

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
                        # 요청하신 " (문제유형) : 주제 " 포맷 적용
                        title = f"({entry['type']}) : {entry['topic']}"
                        with st.expander(title):
                            # unsafe_allow_html=True 로 파란색 글씨 정상 출력
                            st.markdown(entry["content"], unsafe_allow_html=True)
            st.divider()
