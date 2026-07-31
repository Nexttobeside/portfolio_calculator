import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from supabase import create_client
import squarify
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="포트폴리오 성장률 & 회수율 계산기",
    layout="wide",
    menu_items={"Get Help": None, "Report a bug": None, "About": None},
)

st.title("📈 주식 포트폴리오 연간 성과 계산기")
st.write(
    "클라우드 DB(Supabase) 연동으로 어떤 기기에서든 실시간 동기화되는"
    " 포트폴리오를 관리하세요."
)

# Supabase 클라이언트 연결 설정
SUPABASE_URL = st.secrets.get("supabase_url", "")
SUPABASE_KEY = st.secrets.get("supabase_key", "")

if not SUPABASE_URL or not SUPABASE_KEY:
  st.error(
      "Supabase URL 또는 Key가 설정되지 않았습니다. st.secrets를 확인해주세요."
  )
  st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# DB에서 최신 포트폴리오 데이터 불러오기 함수
def load_portfolio_from_db():
  response = supabase.table("portfolio").select("*").execute()
  data = response.data
  if not data:
    return pd.DataFrame(
        columns=["id", "티커", "수량", "연 예상 성장률(%)", "연 회수율(%)"]
    )

  df = pd.DataFrame(data)
  df = df.rename(
      columns={
          "ticker": "티커",
          "shares": "수량",
          "growth_rate": "연 예상 성장률(%)",
          "return_rate": "연 회수율(%)",
      }
  )
  return df


# DB에 전체 포트폴리오 상태 동기화
def save_portfolio_to_db(df):
  try:
    supabase.table("portfolio").delete().neq("id", 0).execute()
    for _, row in df.iterrows():
      row_data = {
          "ticker": str(row["티커"]).strip().upper(),
          "shares": float(row["수량"]),
          "growth_rate": float(row["연 예상 성장률(%)"]),
          "return_rate": float(row["연 회수율(%)"]),
      }
      supabase.table("portfolio").insert(row_data).execute()
    return True
  except Exception as e:
    st.error(f"DB 저장 실패: {e}")
    return False


# 세션 상태 초기화 및 DB 로드
if (
    "portfolio" not in st.session_state
    or st.session_state.portfolio is None
    or st.session_state.portfolio.empty
):
  st.session_state.portfolio = load_portfolio_from_db()


def get_current_prices(tickers):
  current_prices_temp = {}
  for ticker in tickers:
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
  return current_prices_temp


# 데이터 정합성 보장 및 평가금액 내림차순 정렬
sidebar_input_cols = ["티커", "수량", "연 예상 성장률(%)", "연 회수율(%)"]
for col in sidebar_input_cols:
  if col not in st.session_state.portfolio.columns:
    st.session_state.portfolio[col] = (
        0.0 if col in ["수량", "연 예상 성장률(%)", "연 회수율(%)"] else ""
    )

for col in ["수량", "연 예상 성장률(%)", "연 회수율(%)"]:
  st.session_state.portfolio[col] = (
      pd.to_numeric(st.session_state.portfolio[col], errors="coerce")
      .fillna(0.0)
      .astype(float)
  )

all_tickers = st.session_state.portfolio["티커"].astype(str).tolist()
all_prices = get_current_prices(all_tickers)

st.session_state.portfolio["_현재가"] = st.session_state.portfolio["티커"].map(
    all_prices
)
st.session_state.portfolio["_평가금액"] = (
    st.session_state.portfolio["수량"] * st.session_state.portfolio["_현재가"]
)

st.session_state.portfolio = (
    st.session_state.portfolio.sort_values(by="_평가금액", ascending=False)
    .drop(columns=["_현재가", "_평가금액"])
    .reset_index(drop=True)
)

# 사전 계산: 종합 성과 요약에 사용할 전체 포트폴리오 가치 및 가중치 산출
raw_df_calc = st.session_state.portfolio.copy()
raw_df_calc["수량"] = pd.to_numeric(raw_df_calc["수량"], errors="coerce").fillna(
    0.0
)
raw_df_calc["연 예상 성장률(%)"] = pd.to_numeric(
    raw_df_calc["연 예상 성장률(%)"], errors="coerce"
).fillna(0.0)
raw_df_calc["연 회수율(%)"] = pd.to_numeric(
    raw_df_calc["연 회수율(%)"], errors="coerce"
).fillna(0.0)

active_df_calc = raw_df_calc[raw_df_calc["수량"] > 0].copy()
total_portfolio_value = 0.0
total_weighted_growth = 0.0
total_weighted_return = 0.0

if not active_df_calc.empty:
  calc_tickers = active_df_calc["티커"].tolist()
  calc_prices = get_current_prices(calc_tickers)
  active_df_calc["실시간 주당 현재가"] = active_df_calc["티커"].map(calc_prices)
  active_df_calc["현재 평가금액(총액)"] = (
      active_df_calc["수량"] * active_df_calc["실시간 주당 현재가"]
  )
  total_portfolio_value = active_df_calc["현재 평가금액(총액)"].sum()

  if total_portfolio_value > 0:
    active_df_calc["가중 성장 기여도"] = (
        active_df_calc["현재 평가금액(총액)"]
        * active_df_calc["연 예상 성장률(%)"]
    )
    active_df_calc["가중 회수 기여도"] = (
        active_df_calc["현재 평가금액(총액)"] * active_df_calc["연 회수율(%)"]
    )
    total_weighted_growth = (
        active_df_calc["가중 성장 기여도"].sum() / total_portfolio_value
    )
    total_weighted_return = (
        active_df_calc["가중 회수 기여도"].sum() / total_portfolio_value
    )


# 사이드바: 매수/매도 거래 입력 및 종목 설정 관리
with st.sidebar:
  st.header("🛒 매수 / 매도 거래 입력")
  with st.form("trade_form", clear_on_submit=True):
    trade_ticker = (
        st.text_input("티커 (예: AAPL, 005930.KS)").strip().upper()
    )
    trade_type = st.selectbox("거래 구분", ["매수", "매도"])
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
        current_portfolio["티커_upper"] = (
            current_portfolio["티커"].astype(str).str.strip().str.upper()
        )
        match_idx = current_portfolio[
            current_portfolio["티커_upper"] == trade_ticker
        ].index

        if not match_idx.empty:
          idx = match_idx[0]
          current_shares = float(
              pd.to_numeric(current_portfolio.loc[idx, "수량"], errors="coerce")
              or 0.0
          )

          if trade_type == "매수":
            current_portfolio.loc[idx, "수량"] = current_shares + trade_shares
            st.success(
                f"[{trade_ticker}] {trade_shares}주 매수 반영 완료! (총"
                f" {current_portfolio.loc[idx, '수량']}주)"
            )
          else:
            new_shares = current_shares - trade_shares
            current_portfolio.loc[idx, "수량"] = max(0.0, new_shares)
            if new_shares <= 0:
              st.warning(
                  f"[{trade_ticker}] 전량 매도되어 분석 현황에서 제외되었습니다."
              )
            else:
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
                f"신규 종목 [{trade_ticker}]이(가) 설정에 추가되고 매수가"
                " 반영되었습니다!"
            )

        if "티커_upper" in current_portfolio.columns:
          current_portfolio = current_portfolio.drop(columns=["티커_upper"])

        for col in ["수량", "연 예상 성장률(%)", "연 회수율(%)"]:
          current_portfolio[col] = (
              pd.to_numeric(current_portfolio[col], errors="coerce")
              .fillna(0.0)
              .astype(float)
          )

        st.session_state.portfolio = current_portfolio
        if save_portfolio_to_db(current_portfolio):
          st.success("✨ 클라우드 DB에 거래 내역이 영구 저장되었습니다!")
        st.rerun()

  st.divider()

  st.header("⚙️ 종목별 성장률 및 회수율 설정")
  st.write(
      "종목별 **수량**과 연 예상 **성장률**, **회수율**(배당+자사주 매입)을"
      " 직접 수정하거나 관리할 수 있습니다."
  )

  current_setting_df = st.session_state.portfolio[sidebar_input_cols].copy()

  edited_df = st.data_editor(
      current_setting_df,
      num_rows="dynamic",
      use_container_width=True,
      key="sidebar_editor",
  )

  if not edited_df.equals(current_setting_df):
    for col in ["수량", "연 예상 성장률(%)", "연 회수율(%)"]:
      edited_df[col] = (
          pd.to_numeric(edited_df[col], errors="coerce").fillna(0.0).astype(float)
      )

    st.session_state.portfolio = edited_df.copy()
    if save_portfolio_to_db(edited_df):
      st.success("✨ 설정 변경 내용이 클라우드 DB에 즉시 반영되었습니다!")
    st.rerun()


# ==========================================
# 메인 화면: 탭 분리 구현
# ==========================================
tab1, tab2 = st.tabs(["📊 포트폴리오 분석 및 시각화", "🧮 회수율 미래 시뮬레이터"])

with tab1:
  # 화면 최상단: 전체 포트폴리오 종합 성과 요약 배치
  st.subheader("🎯 전체 포트폴리오 종합 성과 요약")
  col1, col2, col3 = st.columns(3)
  col1.metric("총 포트폴리오 평가금액", f"${total_portfolio_value:,.2f}")
  col2.metric("포트폴리오 연 예상 성장률", f"{total_weighted_growth:.2f}%")
  col3.metric("포트폴리오 연 예상 회수율", f"{total_weighted_return:.2f}%")

  st.divider()

  # 종목별 분석 및 비중 현황 메인 영역
  if not st.session_state.portfolio.empty:
    raw_df = st.session_state.portfolio.copy()
    raw_df["수량"] = pd.to_numeric(raw_df["수량"], errors="coerce").fillna(0.0)
    raw_df["연 예상 성장률(%)"] = pd.to_numeric(
        raw_df["연 예상 성장률(%)"], errors="coerce"
    ).fillna(0.0)
    raw_df["연 회수율(%)"] = pd.to_numeric(
        raw_df["연 회수율(%)"], errors="coerce"
    ).fillna(0.0)

    active_df = raw_df[raw_df["수량"] > 0].copy()

    if not active_df.empty:
      tickers_to_fetch = active_df["티커"].tolist()
      current_prices = get_current_prices(tickers_to_fetch)

      active_df["실시간 주당 현재가"] = active_df["티커"].map(current_prices)
      active_df["현재 평가금액(총액)"] = (
          active_df["수량"] * active_df["실시간 주당 현재가"]
      )

      active_df = active_df.sort_values(
          by="현재 평가금액(총액)", ascending=False
      ).reset_index(drop=True)
      active_df.index = range(1, len(active_df) + 1)

      if total_portfolio_value > 0:
        active_df["포트폴리오 비중(%)"] = (
            active_df["현재 평가금액(총액)"] / total_portfolio_value
        ) * 100
      else:
        active_df["포트폴리오 비중(%)"] = 0.0

      table_df = active_df.copy()
      table_df = table_df.rename(
          columns={
              "실시간 주당 현재가": "현재가($)",
              "현재 평가금액(총액)": "평가금액($)",
          }
      )

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

      # 트리맵 시각화
      if total_portfolio_value > 0:
        st.subheader("🟩 종목별 비중")

        fig, ax = plt.subplots(figsize=(10, 5))

        sizes = active_df["포트폴리오 비중(%)"].values
        tickers = active_df["티커"].values

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

          box_diagonal = np.sqrt(dx**2 + dy**2)
          target_text_diagonal = box_diagonal / 4.0

          ticker_font_size = float(
              max(
                  2.5,
                  target_text_diagonal
                  * 3.2
                  / (1.0 + 0.05 * len(tickers[i]))
                  * 0.90,
              )
          )
          pct_font_size = float(
              max(1.8, target_text_diagonal * 2.0 / (1.0 + 0.05 * 5) * 0.90)
          )

          if area >= 1.2:
            ax.text(
                x + dx / 2,
                y + dy / 2 + (dy * 0.12),
                f"{tickers[i]}",
                ha="center",
                va="center",
                fontsize=ticker_font_size,
                weight="bold",
                color="white",
            )
            ax.text(
                x + dx / 2,
                y + dy / 2 - (dy * 0.13),
                f"{weight_val:.1f}%",
                ha="center",
                va="center",
                fontsize=pct_font_size,
                weight="semibold",
                color="#E5E7EB",
            )
          elif area >= 0.35:
            ax.text(
                x + dx / 2,
                y + dy / 2,
                f"{tickers[i]}\n{weight_val:.1f}%",
                ha="center",
                va="center",
                fontsize=ticker_font_size * 0.85,
                weight="bold",
                color="white",
            )
          elif area >= 0.12:
            ax.text(
                x + dx / 2,
                y + dy / 2,
                f"{tickers[i]}",
                ha="center",
                va="center",
                fontsize=ticker_font_size * 0.90,
                weight="bold",
                color="white",
            )

        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.axis("off")
        st.pyplot(fig)
    else:
      st.info(
          "현재 보유 중인 종목이 없습니다. (사이드바 거래 입력 및 설정을 통해"
          " 종목을 추가해 주세요.)"
      )


with tab2:
  st.subheader("🧮 개별 회수율 미래 시뮬레이터")
  st.write(
      "초기 회수율과 성장률이 매년 복리로 작용할 때, **지정된 기간 뒤의 미래"
      " 회수율**을 계산합니다."
  )

  with st.form("simulator_form"):
    sim_col1, sim_col2, sim_col3 = st.columns(3)
    with sim_col1:
      input_init_return = st.number_input(
          "초기 회수율 (%)", value=3.0, step=0.1, format="%.2f"
      )
    with sim_col2:
      input_growth_rate = st.number_input(
          "회수율 연 예상 성장률 (%)", value=10.0, step=0.5, format="%.2f"
      )
    with sim_col3:
      input_years = st.number_input(
          "목표 기간 (년)", min_value=1, max_value=50, value=10, step=1
      )

    submit_sim = st.form_submit_button("미래 회수율 계산하기")

  if submit_sim:
    future_return_val = input_init_return * (
        (1 + input_growth_rate / 100.0) ** (input_years - 1)
        if input_years > 1
        else 1.0
    )
    st.success(
        f"📌 **시뮬레이션 결과**: 초기 회수율 **{input_init_return:.2f}%**인"
        f" 상품이 매년 **{input_growth_rate:.2f}%**씩 성장할 때, **{input_years}년"
        f" 뒤**의 실효 회수율은 원금 대비 약 **{future_return_val:.2f}%**가"
        " 됩니다!"
    )

  st.divider()

  st.subheader(
      "📊 설정된 전체 종목별 미래 회수율 비교 (현재 / 1·2·3·5·7·10년 후)"
  )
  st.write(
      "사이드바 설정에 등록된 **모든 종목**(수량 무관)들의 **시간 경과에 따른"
      " 회수율 성장 추이**를 비교합니다."
  )

  if not st.session_state.portfolio.empty:
    port_sim_df = st.session_state.portfolio.copy()
    port_sim_df["티커"] = port_sim_df["티커"].astype(str).str.strip()
    valid_sim_df = port_sim_df[
        (port_sim_df["티커"] != "") & (port_sim_df["티커"].notna())
    ].copy()

    if not valid_sim_df.empty:
      comparison_rows = []
      for _, row in valid_sim_df.iterrows():
        ticker = row["티커"]
        init_r = float(row["연 회수율(%)"])
        g_rate = float(row["연 예상 성장률(%)"]) / 100.0

        # 복리 계산 함수 (1년차는 현재회수율 그대로, n년차는 (1+g)^(n-1) 적용)
        def calc_future_r(r, g, years):
          return r * ((1 + g) ** (years - 1) if years > 1 else 1.0)

        comparison_rows.append({
            "티커": ticker,
            "연 성장률(%)": float(row["연 예상 성장률(%)"]),
            "현재 회수율(%)": init_r,
            "1년 후 회수율(%)": calc_future_r(init_r, g_rate, 1),
            "2년 후 회수율(%)": calc_future_r(init_r, g_rate, 2),
            "3년 후 회수율(%)": calc_future_r(init_r, g_rate, 3),
            "5년 후 회수율(%)": calc_future_r(init_r, g_rate, 5),
            "7년 후 회수율(%)": calc_future_r(init_r, g_rate, 7),
            "10년 후 회수율(%)": calc_future_r(init_r, g_rate, 10),
        })

      comp_result_df = pd.DataFrame(comparison_rows)
      comp_result_df.index = range(1, len(comp_result_df) + 1)

      st.dataframe(
          comp_result_df.style.format({
              "연 성장률(%)": "{:.2f}%",
              "현재 회수율(%)": "{:.2f}%",
              "1년 후 회수율(%)": "{:.2f}%",
              "2년 후 회수율(%)": "{:.2f}%",
              "3년 후 회수율(%)": "{:.2f}%",
              "5년 후 회수율(%)": "{:.2f}%",
              "7년 후 회수율(%)": "{:.2f}%",
              "10년 후 회수율(%)": "{:.2f}%",
          }),
          use_container_width=True,
      )
    else:
      st.info("등록된 종목이 없습니다.")
  else:
    st.info("등록된 포트폴리오 데이터가 없습니다.")
