import os
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="포트폴리오 성장률 & 회수율 계산기", layout="wide"
)

st.title("📈 주식 포트폴리오 연간 성과 계산기")
st.write(
    "종목 거래를 관리하고 실시간 주가 반영된 전체 포트폴리오의 종합 성과를"
    " 확인하세요."
)

DATA_FILE = "portfolio.csv"

# 1. 파일이 존재하면 읽어오고, 없으면 기본값으로 파일 생성 후 읽기
if not os.path.exists(DATA_FILE):
  default_df = pd.DataFrame({
      "티커": ["AAPL", "TSLA", "MSFT"],
      "수량": [10.0, 5.0, 8.0],
      "연 예상 성장률(%)": [12.0, 20.0, 15.0],
      "연 회수율(%)": [0.5, 0.0, 0.7],
  })
  default_df.to_csv(DATA_FILE, index=False)

# 항상 CSV 파일에서 최신 데이터를 불러와 세션 상태의 기본값으로 사용
saved_df = pd.read_csv(DATA_FILE)

if "portfolio" not in st.session_state:
  st.session_state.portfolio = saved_df


# 실시간 현재가를 가져와서 모든 단계에서 일관되게 평가금액 기준 정렬을 수행하는 함수 정의
def get_sorted_portfolio(df):
  if df.empty:
    return df

  temp_df = df.copy()
  current_prices_temp = {}
  for ticker in temp_df["티커"]:
    ticker_raw = str(ticker).strip()
    price = 0.0
    if ticker_raw:
      try:
        stock = yf.Ticker(ticker_raw)
        if hasattr(stock, "fast_info") and "lastPrice" in stock.fast_info:
          price = float(stock.fast_info["lastPrice"])
        else:
          hist = stock.history(period="1d")
          if not hist.empty:
            price = float(hist["Close"].iloc[-1])
      except Exception:
        price = 0.0
    current_prices_temp[ticker_raw] = price

  temp_df["실시간 주당 현재가"] = temp_df["티커"].map(current_prices_temp)
  temp_df["수량"] = pd.to_numeric(temp_df["수량"], errors="coerce").fillna(0.0)
  temp_df["현재 평가금액(총액)"] = temp_df["수량"] * temp_df["실시간 주당 현재가"]

  # 평가금액 기준 내림차순 정렬 후 인덱스 재정렬
  temp_df = temp_df.sort_values(
      by="현재 평가금액(총액)", ascending=False
  ).reset_index(drop=True)

  return temp_df


# 세션 상태의 포트폴리오를 항상 정렬된 상태로 관리
sorted_session_df = get_sorted_portfolio(st.session_state.portfolio)

# 사이드바 설정창용 데이터프레임 (입력 컬럼만 추출)
input_cols = ["티커", "수량", "연 예상 성장률(%)", "연 회수율(%)"]
display_input_df = sorted_session_df[input_cols]


# ⭐️ 사이드바 생성
with st.sidebar:
  st.header("⚙️ 포트폴리오 설정")
  st.write(
      "종목별 **연 예상 성장률**과 **회수율(배당 등)**을 수정하거나 종목을"
      " 직접 관리할 수 있습니다."
      " (현재 평가금액 큰 순서로 정렬됨)"
  )

  edited_df = st.data_editor(
      display_input_df,
      num_rows="dynamic",
      use_container_width=True,
      key="sidebar_editor",
  )

  # 사이드바 표 내용이 수정되면 곧바로 CSV 파일에 자동 덮어쓰기 저장
  if not edited_df.equals(display_input_df):
    edited_df.to_csv(DATA_FILE, index=False)
    st.session_state.portfolio = edited_df
    st.rerun()


# ⭐️ 메인 화면: 매수/매도 거래 입력
st.subheader("🛒 매수 / 매도 거래 입력")
with st.form("trade_form", clear_on_submit=True):
  col_t1, col_t2, col_t3 = st.columns([1, 1, 1])
  with col_t1:
    trade_ticker = (
        st.text_input("티커 (예: AAPL, 005930.KS)").strip().upper()
    )
  with col_t2:
    trade_type = st.selectbox("거래 구분", ["매수", "매도"])
  with col_t3:
    trade_shares = st.number_input(
        "수량", min_value=0.0001, step=1.0, format="%.4f"
    )

  submit_trade = st.form_submit_button("거래 반영하기")

  if submit_trade:
    if not trade_ticker:
      st.error("티커를 입력해주세요.")
    else:
      current_portfolio = st.session_state.portfolio.copy()

      match_idx = current_portfolio[
          current_portfolio["티커"].str.upper() == trade_ticker
      ].index

      if not match_idx.empty:
        idx = match_idx[0]
        current_shares = float(current_portfolio.loc[idx, "수량"])

        if trade_type == "매수":
          current_portfolio.loc[idx, "수량"] = current_shares + trade_shares
          st.success(
              f"[{trade_ticker}] {trade_shares}주 매수 반영 완료! (총"
              f" {current_portfolio.loc[idx, '수량']}주)"
          )
        else:
          new_shares = current_shares - trade_shares
          if new_shares <= 0:
            current_portfolio = current_portfolio.drop(idx).reset_index(
                drop=True
            )
            st.warning(
                f"[{trade_ticker}] 전량 매도되어 포트폴리오에서 제거되었습니다."
            )
          else:
            current_portfolio.loc[idx, "수량"] = new_shares
            st.success(
                f"[{trade_ticker}] {trade_shares}주 매도 반영 완료! (잔여"
                f" {new_shares}주)"
            )
      else:
        if trade_type == "매도":
          st.error(
              "보유하고 있지 않은 종목은 매도할 수 없습니다. 티커를 확인해주세요."
          )
        else:
          new_row = pd.DataFrame({
              "티커": [trade_ticker],
              "수량": [trade_shares],
              "연 예상 성장률(%)": [10.0],
              "연 회수율(%)": [0.0],
          })
          current_portfolio = pd.concat(
              [current_portfolio, new_row], ignore_index=True
          )
          st.success(
              f"신규 종목 [{trade_ticker}]이(가) 추가되고 {trade_shares}주 매수가"
              " 반영되었습니다!"
          )

      current_portfolio.to_csv(DATA_FILE, index=False)
      st.session_state.portfolio = current_portfolio
      st.rerun()

st.divider()

if not edited_df.empty:
  result_df = sorted_session_df.copy()

  # 숫자로 안전하게 변환
  result_df["수량"] = pd.to_numeric(result_df["수량"], errors="coerce").fillna(
      0.0
  )
  result_df["연 예상 성장률(%)"] = pd.to_numeric(
      result_df["연 예상 성장률(%)"], errors="coerce"
  ).fillna(0.0)
  result_df["연 회수율(%)"] = pd.to_numeric(
      result_df["연 회수율(%)"], errors="coerce"
  ).fillna(0.0)

  # 총 평가금액 합산
  total_portfolio_value = result_df["현재 평가금액(총액)"].sum()

  if total_portfolio_value > 0:
    # 자산 비중 계산 (%)
    result_df["포트폴리오 비중(%)"] = (
        result_df["현재 평가금액(총액)"] / total_portfolio_value
    ) * 100

    # 가중 평균 계산을 위한 기여도 산출
    result_df["가중 성장 기여도"] = (
        result_df["현재 평가금액(총액)"] * result_df["연 예상 성장률(%)"]
    )
    result_df["가중 회수 기여도"] = (
        result_df["현재 평가금액(총액)"] * result_df["연 회수율(%)"]
    )

    total_weighted_growth = (
        result_df["가중 성장 기여도"].sum() / total_portfolio_value
    )
    total_weighted_return = (
        result_df["가중 회수 기여도"].sum() / total_portfolio_value
    )
  else:
    result_df["포트폴리오 비중(%)"] = 0.0
    total_weighted_growth = 0.0
    total_weighted_return = 0.0

  # 결과 화면 출력
  st.subheader("📊 종목별 분석 및 비중 현황")
  display_df = result_df[
      [
          "티커",
          "수량",
          "실시간 주당 현재가",
          "현재 평가금액(총액)",
          "포트폴리오 비중(%)",
          "연 예상 성장률(%)",
          "연 회수율(%)",
      ]
  ]

  st.dataframe(
      display_df.style.format({
          "실시간 주당 현재가": "{:,.2f}",
          "현재 평가금액(총액)": "{:,.2f}",
          "포트폴리오 비중(%)": "{:.2f}%",
          "연 예상 성장률(%)": "{:.2f}%",
          "연 회수율(%)": "{:.2f}%",
      }),
      use_container_width=True,
  )

  # ⭐️ 모바일에서도 비중과 종목명이 그래프 위에 바로 보이도록 수정된 원형(도넛) 그래프
  if total_portfolio_value > 0 and not result_df.empty:
    st.subheader("🥧 종목별 포트폴리오 비중")
    import altair as alt

    chart_data = result_df[["티커", "포트폴리오 비중(%)"]].copy()
    tickers_sorted = chart_data["티커"].tolist()

    # 표시용 포맷팅 컬럼 추가 (예: "AAPL: 45.2%")
    chart_data["비중_라벨"] = (
        chart_data["티커"]
        + ": "
        + chart_data["포트폴리오 비중(%)"].map("{:.1f}%".format)
    )

    base = alt.Chart(chart_data).encode(
        theta=alt.Theta(
            field="포트폴리오 비중(%)",
            type="quantitative",
            sort=tickers_sorted,
        ),
        color=alt.Color(
            field="티커", type="nominal", sort=tickers_sorted, legend=None
        ),
    )

    # 도넛 차트 조각
    pie = base.mark_arc(innerRadius=65, outerRadius=115, stroke="#fff").encode(
        order=alt.Order("포트폴리오 비중(%)", sort="descending"),
        tooltip=["티커", alt.Tooltip("포트폴리오 비중(%)", format=".2f")],
    )

    # 각 조각 위에 텍스트(종목명 + 비중)를 항상 표시하도록 설정
    text = base.mark_text(radius=135, size=12, fontWeight="bold").encode(
        text="비중_라벨",
        order=alt.Order("포트폴리오 비중(%)", sort="descending"),
    )

    st.altair_chart(pie + text, use_container_width=True)

  # 전체 포트폴리오 요약 지표 출력
  st.divider()
  st.subheader("🎯 전체 포트폴리오 종합 성과 요약")
  col1, col2, col3 = st.columns(3)
  col1.metric("총 포트폴리오 평가금액", f"${total_portfolio_value:,.2f}")
  col2.metric("포트폴리오 연 예상 성장률", f"{total_weighted_growth:.2f}%")
  col3.metric("포트폴리오 연 예상 회수율", f"{total_weighted_return:.2f}%")
