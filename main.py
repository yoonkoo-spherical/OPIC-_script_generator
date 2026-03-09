import os
import smtplib
from google import genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import markdown

def generate_opic_content():
    # 새로운 genai SDK 초기화 방식
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    
    prompt = """
    당신은 OPIc AL 등급을 위한 전문 강사입니다. 매일 새로운 질문을 무작위로 생성하십시오.
    다음 조건을 엄격하게 준수하여 답변을 작성하십시오.

    1. 구성: 묘사, 롤플레이, 돌발질문 등 서로 다른 유형의 OPIc 질문 3개를 생성할 것. (어제와 겹치지 않는 새로운 주제)
    2. 분량: 각 질문에 대한 모범 답안은 실제 영어로 발화 시 약 2분 30초 분량이 되도록 작성할 것.
    3. 필수 포함 요소:
       - 질문 (영어 및 한국어 번역)
       - AL 레벨의 모범 답안 스크립트
       - 스크립트에 사용된 주요 Vocabulary, 주요 구동사(Phrasal verbs), 숙어(Idioms) 정리 리스트
    4. 서식 및 강조:
       - 답안 스크립트 본문 내에 있는 '주요 구동사'와 '숙어'는 반드시 HTML 태그를 사용하여 <strong style="color:blue;">텍스트</strong> 형태로 작성할 것. (파란색 볼드체 적용)
       - 전체 문서는 Markdown 문법으로 구조화할 것.
    """
    
    # generate_content 호출 방식 변경
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
