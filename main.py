import os
import smtplib
import random
from google import genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import markdown

def generate_opic_content():
    # 새로운 genai SDK 초기화 방식
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    # 1. 확장된 OPIc 주제 풀(Pool) 정의
    topic_pool = {
        "Description": [
            "자신이 사는 동네 및 주변 주거 환경 묘사",
            "가장 좋아하는 방과 가구 배치 (로봇청소기 동선 등 포함)",
            "최근 방문했거나 계획 중인 해외 여행지 (일본 오사카 등)",
            "가족 구성원 소개 및 14개월 된 아이 육아 일상 묘사",
            "자주 사용하는 스마트폰 앱, AI 서비스, 파이썬(Python) 프로그래밍 관련 경험",
            "즐겨 하는 컴퓨터 게임(문명, 세키로, 몬스터 헌터 등) 묘사",
            "자신의 직업이나 전공 (반도체 소자 물리학, 공정 등)",
            "평소 즐겨 입는 옷차림 (특정 브랜드나 니트 가디건 스타일 등)",
            "관심 있는 스포츠 (프로야구 등) 및 특정 경기장 묘사",
            "단골 카페나 식당의 특징 및 분위기"
        ],
        "Role-play": [
            "렌터카 예약 및 차량 결함 문제 해결",
            "해외 여행(일본 등)을 위한 항공권/호텔 예약 및 일정 변경 문의",
            "새로운 전자기기(고성능 노트북 등) 구매 전 성능 문의 및 AS 요청",
            "어린이집/베이비시터에게 아이의 이유식 거부 문제 상담 및 대안 제시",
            "옷 가게에서 특정 의류 재고 문의 및 환불 요청",
            "친구와의 야구장 직관 약속 변경 및 대안 제시",
            "은행/증권사 방문하여 주식/채권 투자 포트폴리오 리밸런싱 상담",
            "테마파크 예약 오류 관련 고객센터 문의 및 해결",
            "회사 동료에게 자동화 스크립트(웹 크롤링 등) 관련 도움 요청",
            "식당 예약 및 메뉴/알레르기 관련 문의"
        ],
        "Unexpected": [
            "재활용 및 환경 오염 문제의 과거와 현재",
            "인공지능 및 기술 발전이 일상과 경제/산업에 미친 영향",
            "반도체 등 특정 기술 분야의 트렌드 변화",
            "아이 양육 방식의 세대 간 차이 (식습관 및 육아 방식)",
            "경제/재테크(주식, 채권 비율 조정 등)에 대한 사람들의 인식 변화",
            "게임 등 여가 생활 및 취미의 트렌드 변화",
            "해외 여행 방식(자유여행 vs 패키지)의 시대별 변화",
            "자동화 기술 도입에 따른 업무 환경의 변화",
            "대중교통 이용 시 발생한 돌발 상황 및 대처 경험",
            "날씨 변화나 자연 재해로 인한 피해 경험"
        ]
    }

    # 2. 오늘의 주제 무작위 추출
    today_desc = random.choice(topic_pool["Description"])
    today_rp = random.choice(topic_pool["Role-play"])
    today_unexp = random.choice(topic_pool["Unexpected"])

    # 3. 프롬프트 구성 (추출된 주제 주입)
    prompt = f"""
    당신은 OPIc AL 등급을 위한 전문 강사입니다. 
    아래에 지정된 3가지 주제를 반드시 사용하여 OPIc 질문과 모범 답안을 생성하십시오.

    [오늘의 지정 주제]
    1. 묘사 (Description): {today_desc}
    2. 롤플레이 (Role-play): {today_rp}
    3. 돌발질문 (Unexpected): {today_unexp}

    다음 조건을 엄격하게 준수하여 답변을 작성하십시오.

    1. 구성: 위 지정된 3가지 주제에 맞춰 각각 하나씩 총 3개의 질문을 생성할 것.
    2. 분량: 각 질문에 대한 모범 답안은 실제 영어로 발화 시 약 2분 30초 분량이 되도록 작성할 것.
    3. 필수 포함 요소:
       - 질문 (영어 및 한국어 번역)
       - AL 레벨의 모범 답안 스크립트
       - 스크립트에 사용된 주요 Vocabulary, 주요 구동사(Phrasal verbs), 숙어(Idioms) 정리 리스트
    4. 서식 및 강조:
       - 답안 스크립트 본문 내에 있는 '주요 구동사'와 '숙어'는 반드시 HTML 태그를 사용하여 <strong style="color:blue;">텍스트</strong> 형태로 작성할 것. (파란색 볼드체 적용)
       - 전체 문서는 Markdown 문법으로 구조화할 것.
    """

    # generate_content 호출
    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=prompt
    )
    return response.text

def update_markdown_file(content, current_time):
    file_path = "opic_study_log.md"
    log_entry = f"\n\n## {current_time} OPIc Study\n\n" + content

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(log_entry)

def send_email(markdown_content, current_time):
    sender_email = os.getenv("EMAIL_SENDER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    receiver_email = "kyksir@gmail.com"

    html_body = markdown.markdown(markdown_content, extensions=['extra'])
    email_content = f"<h2>{current_time} OPIc AL Daily Script</h2>" + html_body

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = f"[OPIc AL] 일일 학습 자료 ({current_time[:10]})"
    msg.attach(MIMEText(email_content, 'html'))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(sender_email, sender_password)
        server.send_message(msg)

def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    content = generate_opic_content()
    update_markdown_file(content, now)
    send_email(content, now)

if __name__ == "__main__":
    main()
