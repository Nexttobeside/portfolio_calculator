import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import squarify
import streamlit as st
from supabase import Client, create_client
import yfinance as yf

st.set_page_config(
    page_title="개인별 포트폴리오 성장률 & 회수율 계산기",
    layout="wide",
    menu_items={"Get Help": None, "Report a bug": None, "About": None},
)

# --- [1] Supabase 클라이언트 연결 설정 ---
try:
  SUPABASE_URL = st.secrets["SUPABASE_URL"]
  SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
  supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
  st.error(
      "Supabase 연결 설정(Secrets)을 찾을 수 없습니다. secrets.toml 또는"
      " Streamlit Cloud Secrets 설정을 확인해주세요."
  )
  st.stop()

# 세션 상태 초기화
if "logged_in" not in st.session_state:
  st.session_state.logged_in = False
if "username" not in st.session_state:
  st.session_state.username = ""


# --- [2] 로그인 및 회원가입 화면 ---
if not st.session_state.logged_in:
  st.title("🔐 포트폴리오 계산기 로그인")
  st.write(
      "지인 전용 공간입니다. 로그인을 하시거나 새 계정을 만들어 시작하세요."
  )

  tab_login, tab_register = st.tabs(["로그인", "회원가입"])

  # 1) 로그인 탭
  with tab_login:
    with st.form("login_form"):
      login_id = st.text_input("아이디", key="login_id").strip()
      login_pw = st.text_input(
          "비밀번호", type="password", key="login_pw"
      ).strip()
      submit_login = st.form_submit_button("로그인")

      if submit_login:
        if not login_id or not login_pw:
          st.error("아이디와 비밀번호를 모두 입력해주세요.")
        else:
          try:
            res = (
                supabase.table("users")
                .select("password")
                .eq("username", login_id)
                .execute()
            )
            if res.data:
              stored_pw = str(res.data[0]["password"]).strip()
              if stored_pw == login_pw:
                st.session_state.logged_in = True
                st.session_state.username = login_id
                st.success(f"{login_id}님 환영합니다!")
                st.rerun()
              else:
                st.error("비밀번호가 일치하지 않습니다.")
            else:
              st.error("존재하지 않는 아이디입니다.")
          except Exception as err:
            st.error(f"로그인 중 오류 발생: {err}")

  # 2) 회원가입 탭
  with tab_register:
    with st.form("register_form"):
      reg_id = st.text_input("사용할 아이디", key="reg_id").strip()
      reg_pw = st.text_input(
          "사용할 비밀번호", type="password", key="reg_pw"
      ).strip()
      reg_pw_confirm = st.text_input(
          "비밀번호 확인", type="password", key="reg_pw_confirm"
      ).strip()
      submit_reg = st.form_submit_button("회원가입 하기")

      if submit_reg:
        if not reg_id or not reg_pw:
          st.error("아이디와 비밀번호를 모두 입력해주세요.")
        elif reg_pw != reg_pw_confirm:
          st.error("비밀번호가 서로 일치하지 않습니다.")
        else:
          try:
            # 아이디 중복 확인
            check_res = (
                supabase.table("users")
                .select("username")
                .eq("username", reg_id)
                .execute()
            )
            if check_res.data:
              st.error(
                  "이미 존재하는 아이디입니다. 다른 아이디를 사용해 주세요."
              )
            else:
              # Supabase users 테이블에 계정 추가
              supabase.table("users").insert(
                  {"username": reg_id, "password": reg_pw}
              ).execute()
              st.success(
                  "🎉 회원가입이 완료되었습니다! '로그인' 탭에서 로그인해 주세요."
              )
          except Exception as err:
            st.error(f"회원가입 중 오류 발생: {err}")

  st.stop()


# --- [3] 로그인 이후 메인 앱 로직 (데이터베이스 연동 함수) ---


def load_user_portfolio(username):
  try:
    res = (
        supabase.table("portfolios")
        .select("ticker, shares, growth_rate, return_rate")
        .eq("username", username)
        .execute()
    )
    data = res.data
    if not data:
      return pd.DataFrame(
          columns=["티커", "수량", "연 예상 성장률(%)", "연 회수율(%)"]
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
  except Exception:
    return pd.DataFrame(
        columns=["티커", "수량", "연 예상 성장률(%)", "연 회수율(%)"]
    )


def save_user_portfolio(username, df):
  try:
    # 기존 해당 유저 데이터 전부 삭제 후 최신 상태로 덮어쓰기 (가장 안정적)
    supabase.table("portfolios").delete().eq("username", username).execute()

    active_rows = df[df["수량"] > 0]
    if not active_rows.empty:
      records = []
      for _, row in active_rows.iterrows():
        records.append({
            "username": username,
            "ticker": str(row["티커"]).strip().upper(),
            "shares": float(row["수량"]),
            "growth_rate": float(row["연 예상 성장률(%)"]),
            "return_rate": float(row["연 회수율(%)"]),
        })
      if records:
        supabase.table("portfolios").insert(records).execute()
  except Exception as e:
    st.error(f"데이터 저장 중 오류가 발생했습니다: {e}")


# 상단 헤더 및 로그아웃 버튼
top_col1, top_col2 = st.columns([8, 2])
with top_col1:
  st.title("📈 주식 포트폴리오 연간 성과 계산기")
  st.write(
      f"👤 현재 접속 계정: **{st.session_state.username}**님 | 종목 거래를"
      " 관리하고 포트폴리오 성과를 확인하세요."
  )
with top_col2:
  if st.button("로그아웃"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.portfolio = None
    st.rerun()

st.divider()

sidebar_input_cols = ["티커", "수량", "연 예상 성장률(%)", "연 회수율(%)"]

if (
    "portfolio" not in st.session_state
    or st.session_state.portfolio is None
    or st.session_state.get("current_user") != st.session_state.username
):
  st.session_state.portfolio = load_user_portfolio(st.session_state.username)
  st.session_state.current_user = st.session_state.username


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


# 데이터 정합성 보장
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

# 수량이 0 이상인 항목들에 대해 현재가 조회 및 정렬
if not st.session_state.portfolio.empty:
  all_tickers = st.session_state.portfolio["티커"].astype(str).tolist()
  all_prices = get_current_prices(all_tickers)
  st.session_state.portfolio["_현재가"] = st.session_state.portfolio[
      "티커"
  ].map(all_prices)
  st.session_state.portfolio["_평가금액"] = (
      st.session_state.portfolio["수량"] * st.session_state.portfolio["_현재가"]
  )
  st.session_state.portfolio = (
      st.session_state.portfolio.sort_values(by="_평가금액", ascending=False)
      .drop(columns=["_현재가", "_평가금액"])
      .reset_index(drop=True)
  )

# 사전 계산: 종합 성과 요약 산출
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


# 1. 화면 최상단: 전체 포트폴리오 종합 성과 요약 배치
st.subheader("🎯 전체 포트폴리오 종합 성과 요약")
col1, col2, col3 = st.columns(3)
col1.metric("총 포트폴리오 평가금액", f"${total_portfolio_value:,.2f}")
col2.metric("포트폴리오 연 예상 성장률", f"{total_weighted_growth:.2f}%")
col3.metric("포트폴리오 연 예상 회수율", f"{total_weighted_return:.2f}%")

st.divider()


# ⭐️ 사이드바: 매수/매도 거래 입력 및 종목별 설정 배치
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
                f"신규 종목 [{trade_ticker}]이(가) 추가되고 매수가 반영되었습니다!"
            )

        if "티커_upper" in current_portfolio.columns:
          current_portfolio = current_portfolio.drop(columns=["티커_upper"])

        current_portfolio["수량"] = (
            pd.to_numeric(current_portfolio["수량"], errors="coerce")
            .fillna(0.0)
            .astype(float)
        )
        current_portfolio["연 예상 성장률(%)"] = (
            pd.to_numeric(
                current_portfolio["연 예상 성장률(%)"], errors="coerce"
            )
            .fillna(0.0)
            .astype(float)
        )
        current_portfolio["연 회수율(%)"] = (
            pd.to_numeric(current_portfolio["연 회수율(%)"], errors="coerce")
            .fillna(0.0)
            .astype(float)
        )

        save_user_portfolio(st.session_state.username, current_portfolio)
        st.session_state.portfolio = current_portfolio
        st.rerun()

  st.divider()

  st.header("⚙️ 종목별 성장률 및 회수율 설정")
  st.write(
      "종목별 **연 예상 성장률**과 **회수율(배당+자사주 매입 등)**을 직접"
      " 수정하거나 관리할 수 있습니다."
  )

  current_setting_df = st.session_state.portfolio[sidebar_input_cols].copy()

  edited_df = st.data_editor(
      current_setting_df,
      num_rows="dynamic",
      use_container_width=True,
      key="sidebar_editor",
  )

  if not edited_df.equals(current_setting_df):
    st.session_state.portfolio = edited_df.copy()
    save_user_portfolio(st.session_state.username, edited_df)
    st.rerun()


# ⭐️ 메인 영역: 종목별 분석 및 비중 현황
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
        x, y, dx, dy = rect["x"], rect["y"], rect["dx"], rect["dy"]
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
        "💡 등록된 종목이 없습니다. 사이드바의 **[매수 / 매도 거래 입력]**을 통해"
        " 첫 종목을 추가해 보세요!"
    )
else:
  st.info(
      "💡 등록된 종목이 없습니다. 사이드바의 **[매수 / 매도 거래 입력]**을 통해"
      " 첫 종목을 추가해 보세요!"
  )
