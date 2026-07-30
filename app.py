import os
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import squarify
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

saved_df = pd.read_csv(DATA_FILE)

if "portfolio" not in st.session_state:
  st.session_state.portfolio = saved_df


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

  # 내부 연산을 위해 임시 컬럼명 유지 후, 출력 시점에 변경
  temp_df["실시간 주당 현재가"] = temp_df["티커"].map(current_prices_temp)
  temp_df["수량"] = pd.to_numeric(temp_df["수량"], errors="coerce").fillna(0.0)
  temp_df["현재 평가금액(총액)"] = temp_df["수량"] * temp_df["실시간 주당 현재가"]

  temp_df = temp_df.sort_values(
      by="현재 평가금액(총액)", ascending=False
  ).reset_index(drop=True)

  return temp_df


sorted_session_df = get_sorted_portfolio(st.session_state.portfolio)

input_cols = ["티커", "수량", "연 예상 성장률(%)", "연 회수율(%)"]
display_input_df = sorted_session_df[input_cols]

# ⭐️ 사이드바 설정
with st.sidebar:
  st.header("⚙️ 포트폴리오 설정")
  st.write(
      "종목별 **연 예상 성장률**과 **회수율(배당 등)**을 수정하거나 종목을"
      " 관리할 수 있습니다."
  )

  edited_df = st.data_editor(
      display_input_df,
      num_rows="dynamic",
      use_container_width=True,
      key="sidebar_editor",
  )

  if not edited_df.equals(display_input_df):
    edited_df.to_csv(DATA_FILE, index=False)
    st.session_state.portfolio = edited_df
    st.rerun()

# ⭐️ 매수 / 매도 거래 입력
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
        "수량", min_value=0, value=0, step=1, format="%d"
    )

  submit_trade = st.form_submit_button("거래 반영하기")

  if submit_trade:
    if not trade_ticker:
      st.error("티커를 입력해주세요.")
    elif trade_shares <= 0:
      st.error("수량은 0보다 커야 합니다.")
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
          st.error("보유하고 있지 않은 종목은 매도할 수 없습니다.")
        else:
          new_row = pd.DataFrame({
              "티커": [trade_ticker],
              "수량": [float(trade_shares)],
              "연 예상 성장률(%)": [10.0],
              "연 회수율(%)": [0.0],
          })
          current_portfolio = pd.concat(
              [current_portfolio, new_row], ignore_index=True
          )
          st.success(
              f"신규 종목 [{trade_ticker}]이(가) 추가되고 매수가 반영되었습니다!"
          )

      current_portfolio.to_csv(DATA_FILE, index=False)
      st.session_state.portfolio = current_portfolio
      st.rerun()

st.divider()

if not edited_df.empty:
  result_df = sorted_session_df.copy()

  result_df["수량"] = pd.to_numeric(result_df["수량"], errors="coerce").fillna(
      0.0
  )
  result_df["연 예상 성장률(%)"] = pd.to_numeric(
      result_df["연 예상 성장률(%)"], errors="coerce"
  ).fillna(0.0)
  result_df["연 회수율(%)"] = pd.to_numeric(
      result_df["연 회수율(%)"], errors="coerce"
  ).fillna(0.0)

  total_portfolio_value = result_df["현재 평가금액(총액)"].sum()

  if total_portfolio_value > 0:
    result_df["포트폴리오 비중(%)"] = (
        result_df["현재 평가금액(총액)"] / total_portfolio_value
    ) * 100
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

  # 컬럼명을 사용자 요청대로 변경하기 위한 복사본 생성
  table_df = result_df.copy()
  table_df = table_df.rename(
      columns={
          "실시간 주당 현재가": "현재가($)",
          "현재 평가금액(총액)": "평가금액($)",
      }
  )

  # 결과 테이블 출력
  st.subheader("📊 종목별 분석 및 비중 현황")
  display_df = table_df[
      [
          "티커",
          "수량",
          "현재가($)",
          "평가금액($)",
          "포트폴리오 비중(%)",
          "연 예상 성장률(%)",
          "연 회수율(%)",
      ]
  ]

  st.dataframe(
      display_df.style.format({
          "수량": "{:,.0f}",
          "현재가($)": "{:,.2f}",
          "평가금액($)": "{:,.2f}",
          "포트폴리오 비중(%)": "{:.2f}%",
          "연 예상 성장률(%)": "{:.2f}%",
          "연 회수율(%)": "{:.2f}%",
      }),
      use_container_width=True,
  )

  # 트리맵 시각화 (사용자 가이드 적용: 텍스트 사각형 대각선 = 박스 대각선의 1/4)
  if total_portfolio_value > 0 and not result_df.empty:
    st.subheader("🟩 종목별 비중")

    fig, ax = plt.subplots(figsize=(10, 5))

    sizes = result_df["포트폴리오 비중(%)"].values
    tickers = result_df["티커"].values

    normed_values = squarify.normalize_sizes(sizes, 100, 100)
    rects = squarify.squarify(normed_values, 0, 0, 100, 100)

    bright_distinct_palette = [
        "#3B82F6",
        "#10B981",
        "#F59E0B",
        "#EF4444",
        "#8B5CF6",
        "#06B6D4",
        "#EC4899",
        "#14B8A6",
        "#6366F1",
        "#84CC16",
    ]

    for i, rect in enumerate(rects):
      x = rect["x"]
      y = rect["y"]
      dx = rect["dx"]
      dy = rect["dy"]

      ax.bar(
          x=x,
          height=dy,
          width=dx,
          bottom=y,
          align="edge",
          color=bright_distinct_palette[i % len(bright_distinct_palette)],
          edgecolor="#FFFFFF",
          linewidth=2.5,
          alpha=0.92,
      )

      area = dx * dy
      weight_val = sizes[i]

      # ⭐️ 사용자 제시 로직 반영:
      # 1. 종목 박스의 대각선 길이 계산: sqrt(dx^2 + dy^2)
      box_diagonal = np.sqrt(dx**2 + dy**2)

      # 2. 텍스트를 감싸는 사각형의 대각선 길이는 박스 대각선의 1/4
      target_text_diagonal = box_diagonal / 4.0

      # 3. 텍스트 내용물(티커 + 퍼센트)의 글자 수와 줄바꿈을 고려한 종횡비 추정치 기반 폰트 크기 환산 (소수점 단위)
      # matplotlib 폰트 크기 단위(pt)로 변환하기 위한 계수 적용
      # 텍스트 사각형의 대각선 비율을 만족하도록 폰트 크기를 float 소수점으로 정밀 계산
      ticker_font_size = float(
          max(3.0, target_text_diagonal * 3.6 / (1.0 + 0.05 * len(tickers[i])))
      )
      pct_font_size = float(max(2.5, ticker_font_size * 0.72))

      if area >= 1.2:
        # 충분히 공간이 있는 박스: 티커와 비중을 소수점 개별 크기로 2줄 배치
        ax.text(
            x + dx / 2,
            y + dy / 2 + (dy * 0.08),
            f"{tickers[i]}",
            ha="center",
            va="center",
            fontsize=ticker_font_size,
            weight="bold",
            color="white",
        )
        ax.text(
            x + dx / 2,
            y + dy / 2 - (dy * 0.10),
            f"{weight_val:.1f}%",
            ha="center",
            va="center",
            fontsize=pct_font_size,
            weight="semibold",
            color="#E5E7EB",
        )
      elif area >= 0.35:
        # 다소 작은 박스: 소수점 폰트로 한 줄 압축 표시
        ax.text(
            x + dx / 2,
            y + dy / 2,
            f"{tickers[i]}\n{weight_val:.1f}%",
            ha="center",
            va="center",
            fontsize=ticker_font_size * 0.9,
            weight="bold",
            color="white",
        )
      elif area >= 0.12:
        # 작은 박스: 비중 생략하고 티커만 소수점 폰트로 표시
        ax.text(
            x + dx / 2,
            y + dy / 2,
            f"{tickers[i]}",
            ha="center",
            va="center",
            fontsize=ticker_font_size * 0.95,
            weight="bold",
            color="white",
        )
      # 극도로 작고 납작한 박스는 생략

    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    st.pyplot(fig)

  # 종합 성과 요약
  st.divider()
  st.subheader("🎯 전체 포트폴리오 종합 성과 요약")
  col1, col2, col3 = st.columns(3)
  col1.metric("총 포트폴리오 평가금액", f"${total_portfolio_value:,.2f}")
  col2.metric("포트폴리오 연 예상 성장률", f"{total_weighted_growth:.2f}%")
  col3.metric("포트폴리오 연 예상 회수율", f"{total_weighted_return:.2f}%")
