import os
import pandas as pd
from supabase import create_client

# 본인의 Supabase 정보 입력 (또는 .env / st.secrets 방식 사용)
SUPABASE_URL = "여기에_URL"
SUPABASE_KEY = "여기에_API_KEY"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 1. 내 기존 포트폴리오 파일 불러오기 (파일명에 맞게 수정)
my_old_file = "portfolio.csv"  # 또는 기존에 쓰던 파일명
if os.path.exists(my_old_file):
  df = pd.read_csv(my_old_file)

  # 내 아이디 지정
  my_username = "admin"  # 본인의 로그인 아이디

  records = []
  for _, row in df.iterrows():
    records.append({
        "username": my_username,
        "ticker": str(row["티커"]).strip().upper(),
        "shares": float(row["수량"]),
        "growth_rate": float(
            row.get("연 예상 성장률(%)", 10.0)
        ),  # 컬럼명에 맞게 조절
        "return_rate": float(row.get("연 회수율(%)", 0.0)),
    })

  # Supabase에 데이터 밀어넣기
  if records:
    supabase.table("portfolios").insert(records).execute()
    print("✨ 기존 포트폴리오 데이터가 Supabase로 성공적으로 옮겨졌습니다!")
else:
  print("기존 파일을 찾지 못했습니다.")
