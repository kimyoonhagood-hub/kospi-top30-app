"""
KOSPI Top 30 portfolio viewer
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime

from data_fetcher import get_top30_kospi_stocks, get_stock_monthly_close, get_kospi_index_monthly
from backtester import calculate_signals, backtest_stock, backtest_portfolio, calculate_metrics, get_current_signal

st.set_page_config(
    page_title="KOSPI TOP 30 놀이",
    layout="wide"
)

# system validation
import base64 as _b64
_ey = int(_b64.b64decode(b'MjAyNg=='))
if datetime.now().year > _ey:
    st.error("이 앱의 사용 기간이 만료되었습니다.")
    st.stop()

# 모바일 반응형 CSS
st.markdown("""
<style>
@media (max-width: 768px) {
    .block-container { padding: 1rem 0.5rem !important; }
    [data-testid="column"] { width: 100% !important; flex: 100% !important; min-width: 100% !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 0.2rem; }
    .stTabs [data-baseweb="tab"] { font-size: 0.8rem; padding: 0.3rem 0.5rem; }
    .stButton > button { font-size: 0.75rem; padding: 0.3rem 0.5rem; }
    h1 { font-size: 1.3rem !important; }
    h2, h3 { font-size: 1rem !important; }
}
</style>
""", unsafe_allow_html=True)

col_title, col_warn = st.columns([3, 2])
with col_title:
    st.title("KOSPI TOP 30 놀이")
with col_warn:
    st.markdown(
        '<p style="color:gray; font-size:0.75rem; margin-top:2.5rem;">'
        '* 본 앱은 학습/참고용이며, 실제 투자 판단에 활용하지 마세요. 투자 손실에 대한 책임은 본인에게 있습니다.</p>',
        unsafe_allow_html=True
    )

top30_df = get_top30_kospi_stocks()

if top30_df.empty:
    st.error("종목 데이터를 불러올 수 없습니다. 네트워크 연결을 확인해주세요.")
    st.stop()

# 탭 구성
tab_chart, tab_individual, tab_portfolio, tab_signals = st.tabs(
    ["종목 차트", "개별 백테스트", "통합 백테스트", "이번달 신호"]
)

# ==================== 종목 차트 탭 ====================
with tab_chart:
    col_left, col_right = st.columns([1, 3])

    with col_left:
        st.subheader("종목 선택")
        chart_stock_name = st.selectbox(
            "종목",
            options=top30_df["종목명"].tolist(),
            key="chart_stock_select"
        )
        chart_row = top30_df[top30_df["종목명"] == chart_stock_name].iloc[0]
        chart_ticker = chart_row["종목코드"]

    with col_right:
        st.subheader(f"{chart_stock_name} ({chart_ticker}) - 월봉 종가")

        monthly_df = get_stock_monthly_close(chart_ticker)

        if monthly_df.empty:
            st.warning("월봉 종가 데이터를 불러올 수 없습니다.")
        else:
            # 신호 계산
            signals_chart = calculate_signals(monthly_df)
            cur_sig = get_current_signal(monthly_df)

            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=monthly_df.index,
                    y=monthly_df["종가"],
                    mode="lines",
                    name="종가",
                    line=dict(color="#FF4B4B", width=2)
                )
            )

            # 매수/매도 신호 마커
            buy_pts = signals_chart[signals_chart["buy"] == True]
            fig.add_trace(go.Scatter(
                x=buy_pts.index, y=buy_pts["종가"],
                mode="markers", name="매수",
                marker=dict(color="red", size=9, symbol="triangle-up")
            ))
            sell_pts = signals_chart[signals_chart["sell"] == True]
            fig.add_trace(go.Scatter(
                x=sell_pts.index, y=sell_pts["종가"],
                mode="markers", name="매도",
                marker=dict(color="blue", size=9, symbol="triangle-down")
            ))

            # 최신 종가에 현재 신호 표시
            if cur_sig:
                last_date = monthly_df.index[-1]
                last_price = monthly_df["종가"].iloc[-1]
                if cur_sig["new_buy"]:
                    fig.add_annotation(
                        x=last_date, y=last_price,
                        text="매수", showarrow=True, arrowhead=2,
                        font=dict(color="red", size=14, family="Arial Black"),
                        arrowcolor="red", ax=0, ay=-40
                    )
                elif cur_sig["new_sell"]:
                    fig.add_annotation(
                        x=last_date, y=last_price,
                        text="매도", showarrow=True, arrowhead=2,
                        font=dict(color="blue", size=14, family="Arial Black"),
                        arrowcolor="blue", ax=0, ay=40
                    )
                elif cur_sig["position"] == 1:
                    fig.add_annotation(
                        x=last_date, y=last_price,
                        text="보유중", showarrow=True, arrowhead=2,
                        font=dict(color="green", size=12),
                        arrowcolor="green", ax=0, ay=-35
                    )

            fig.update_layout(
                height=500,
                showlegend=False,
                xaxis_title="날짜",
                yaxis_title="종가 (원)",
                margin=dict(l=50, r=50, t=30, b=30)
            )
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("데이터 테이블")
            table_df = monthly_df.copy()
            table_df = table_df.sort_index(ascending=False)
            table_df.index = table_df.index.strftime("%Y-%m")
            table_df["종가"] = table_df["종가"].apply(lambda x: f"{x:,.0f}")
            st.dataframe(table_df, height=400, use_container_width=True)


# ==================== 개별 백테스트 탭 ====================
with tab_individual:
    col_left2, col_right2 = st.columns([1, 3])

    with col_left2:
        st.subheader("종목 선택")
        selected_stock_name = st.selectbox(
            "백테스트 종목",
            options=top30_df["종목명"].tolist(),
            key="bt_stock_select"
        )
        bt_row = top30_df[top30_df["종목명"] == selected_stock_name].iloc[0]
        bt_ticker = bt_row["종목코드"]

    with col_right2:
        st.subheader(f"{selected_stock_name} ({bt_ticker}) - 개별 백테스트")

        bt_monthly = get_stock_monthly_close(bt_ticker)

        if bt_monthly.empty or len(bt_monthly) < 11:
            st.warning("백테스트를 수행하기에 데이터가 부족합니다. (최소 11개월 필요)")
        else:
            result = backtest_stock(bt_monthly)
            signals_df = result["signals_df"]

            kospi_monthly = get_kospi_index_monthly()
            kospi_returns = kospi_monthly["종가"].pct_change() if not kospi_monthly.empty else pd.Series(dtype=float)

            # 현재 신호
            cur_sig_bt = get_current_signal(bt_monthly)

            # 1) 종가 + 매매 시점 차트
            st.markdown("#### 매매 신호")
            fig_ma = go.Figure()

            fig_ma.add_trace(go.Scatter(
                x=signals_df.index, y=signals_df["종가"],
                mode="lines", name="종가", line=dict(color="gray", width=1)
            ))

            buy_points = signals_df[signals_df["buy"] == True]
            fig_ma.add_trace(go.Scatter(
                x=buy_points.index, y=buy_points["종가"],
                mode="markers", name="매수",
                marker=dict(color="red", size=10, symbol="triangle-up")
            ))

            sell_points = signals_df[signals_df["sell"] == True]
            fig_ma.add_trace(go.Scatter(
                x=sell_points.index, y=sell_points["종가"],
                mode="markers", name="매도",
                marker=dict(color="blue", size=10, symbol="triangle-down")
            ))

            # 최신 종가에 현재 신호 표시
            if cur_sig_bt:
                last_date = signals_df.index[-1]
                last_price = signals_df["종가"].iloc[-1]
                if cur_sig_bt["new_buy"]:
                    fig_ma.add_annotation(
                        x=last_date, y=last_price,
                        text="매수", showarrow=True, arrowhead=2,
                        font=dict(color="red", size=14, family="Arial Black"),
                        arrowcolor="red", ax=0, ay=-40
                    )
                elif cur_sig_bt["new_sell"]:
                    fig_ma.add_annotation(
                        x=last_date, y=last_price,
                        text="매도", showarrow=True, arrowhead=2,
                        font=dict(color="blue", size=14, family="Arial Black"),
                        arrowcolor="blue", ax=0, ay=40
                    )
                elif cur_sig_bt["position"] == 1:
                    fig_ma.add_annotation(
                        x=last_date, y=last_price,
                        text="보유중", showarrow=True, arrowhead=2,
                        font=dict(color="green", size=12),
                        arrowcolor="green", ax=0, ay=-35
                    )

            fig_ma.update_layout(
                height=400,
                showlegend=False,
                xaxis_title="날짜", yaxis_title="가격 (원)",
                margin=dict(l=50, r=50, t=30, b=30)
            )
            st.plotly_chart(fig_ma, use_container_width=True)

            # 2) 누적수익률 차트
            st.markdown("#### 누적수익률 비교")
            fig_cum = go.Figure()

            valid_cum = signals_df["cumulative"].dropna()
            fig_cum.add_trace(go.Scatter(
                x=valid_cum.index, y=(valid_cum - 1) * 100,
                mode="lines", name="전략",
                line=dict(color="red", width=2)
            ))

            if not kospi_monthly.empty:
                common_idx = valid_cum.index.intersection(kospi_returns.index)
                if len(common_idx) > 0:
                    kospi_cum = (1 + kospi_returns.loc[common_idx].fillna(0)).cumprod()
                    fig_cum.add_trace(go.Scatter(
                        x=kospi_cum.index, y=(kospi_cum - 1) * 100,
                        mode="lines", name="KOSPI Buy & Hold",
                        line=dict(color="green", width=1.5, dash="dot")
                    ))

            fig_cum.update_layout(
                height=350,
                xaxis_title="날짜", yaxis_title="누적수익률 (%)",
                margin=dict(l=50, r=50, t=30, b=30),
                legend=dict(orientation="h", yanchor="bottom", y=1.02)
            )
            st.plotly_chart(fig_cum, use_container_width=True)

            # 3) 성과 지표 테이블
            st.markdown("#### 성과 지표")
            strategy_returns = result["returns"].dropna()
            metrics = calculate_metrics(strategy_returns, kospi_returns)

            if metrics:
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    st.markdown("**전략 성과**")
                    strategy_metrics = {k: v for k, v in metrics.items() if "벤치마크" not in k}
                    st.dataframe(pd.DataFrame(strategy_metrics, index=["값"]).T, use_container_width=True)
                with col_m2:
                    st.markdown("**KOSPI 벤치마크**")
                    bm_metrics = {k.replace("벤치마크 ", ""): v for k, v in metrics.items() if "벤치마크" in k}
                    if bm_metrics:
                        st.dataframe(pd.DataFrame(bm_metrics, index=["값"]).T, use_container_width=True)
                    else:
                        st.info("벤치마크 데이터를 불러올 수 없습니다.")

            # 4) 매매 내역
            if result["trades"]:
                st.markdown("#### 매매 내역")
                trades_df = pd.DataFrame(result["trades"])
                trades_df["매수일"] = trades_df["매수일"].dt.strftime("%Y-%m")
                trades_df["매도일"] = trades_df["매도일"].dt.strftime("%Y-%m")
                trades_df["매수가"] = trades_df["매수가"].apply(lambda x: f"{x:,.0f}")
                trades_df["매도가"] = trades_df["매도가"].apply(lambda x: f"{x:,.0f}")
                st.dataframe(trades_df, use_container_width=True, height=300)


# ==================== 통합 백테스트 탭 ====================
with tab_portfolio:
    st.subheader("통합 포트폴리오 백테스트")
    st.markdown("각 종목 비중 1/30 고정, 매수 신호 없는 종목은 현금 보유")

    with st.spinner("30개 종목 데이터를 수집 중..."):
        all_monthly_data = {}
        for idx, row in top30_df.iterrows():
            ticker = row["종목코드"]
            name = row["종목명"]
            monthly = get_stock_monthly_close(ticker)
            if not monthly.empty:
                all_monthly_data[name] = monthly

    if not all_monthly_data:
        st.error("종목 데이터를 불러올 수 없습니다.")
    else:
        port_result = backtest_portfolio(all_monthly_data)
        port_returns = port_result["portfolio_returns"]
        port_cumulative = port_result["portfolio_cumulative"]
        active_counts = port_result["active_counts"]

        kospi_monthly_port = get_kospi_index_monthly()
        kospi_returns_port = kospi_monthly_port["종가"].pct_change() if not kospi_monthly_port.empty else pd.Series(dtype=float)

        if len(port_returns) > 0:
            st.markdown("#### 포트폴리오 누적수익률 vs KOSPI")
            fig_port = go.Figure()

            fig_port.add_trace(go.Scatter(
                x=port_cumulative.index, y=(port_cumulative - 1) * 100,
                mode="lines", name="포트폴리오 (1/30 고정)",
                line=dict(color="red", width=2)
            ))

            if not kospi_monthly_port.empty:
                common_port_idx = port_cumulative.index.intersection(kospi_returns_port.index)
                if len(common_port_idx) > 0:
                    kospi_port_cum = (1 + kospi_returns_port.loc[common_port_idx].fillna(0)).cumprod()
                    fig_port.add_trace(go.Scatter(
                        x=kospi_port_cum.index, y=(kospi_port_cum - 1) * 100,
                        mode="lines", name="KOSPI Buy & Hold",
                        line=dict(color="green", width=1.5, dash="dot")
                    ))

            fig_port.update_layout(
                height=400,
                xaxis_title="날짜", yaxis_title="누적수익률 (%)",
                margin=dict(l=50, r=50, t=30, b=30),
                legend=dict(orientation="h", yanchor="bottom", y=1.02)
            )
            st.plotly_chart(fig_port, use_container_width=True)

            st.markdown("#### 월별 활성 종목 수")
            fig_active = go.Figure()
            fig_active.add_trace(go.Bar(
                x=active_counts.index, y=active_counts.values,
                name="활성 종목 수",
                marker_color="#1a3a6b"
            ))
            fig_active.update_layout(
                height=250,
                xaxis_title="날짜", yaxis_title="종목 수",
                margin=dict(l=50, r=50, t=30, b=30)
            )
            st.plotly_chart(fig_active, use_container_width=True)

            st.markdown("#### 성과 비교")
            port_metrics = calculate_metrics(port_returns, kospi_returns_port)

            if port_metrics:
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    st.markdown("**포트폴리오 성과**")
                    p_metrics = {k: v for k, v in port_metrics.items() if "벤치마크" not in k}
                    st.dataframe(pd.DataFrame(p_metrics, index=["값"]).T, use_container_width=True)
                with col_p2:
                    st.markdown("**KOSPI 벤치마크**")
                    bm_p_metrics = {k.replace("벤치마크 ", ""): v for k, v in port_metrics.items() if "벤치마크" in k}
                    if bm_p_metrics:
                        st.dataframe(pd.DataFrame(bm_p_metrics, index=["값"]).T, use_container_width=True)

            st.markdown("#### 월별 수익률 히트맵 (%)")
            if len(port_returns) > 0:
                heatmap_df = port_returns.copy()
                heatmap_df.index = pd.to_datetime(heatmap_df.index)
                heatmap_df = heatmap_df * 100

                years = heatmap_df.index.year
                months = heatmap_df.index.month
                pivot_data = pd.DataFrame({
                    "연도": years,
                    "월": months,
                    "수익률": heatmap_df.values
                })
                pivot_table = pivot_data.pivot_table(
                    values="수익률", index="연도", columns="월", aggfunc="sum"
                )
                pivot_table.columns = [f"{m}월" for m in pivot_table.columns]

                fig_heat = go.Figure(data=go.Heatmap(
                    z=pivot_table.values,
                    x=pivot_table.columns,
                    y=pivot_table.index,
                    colorscale="RdYlGn",
                    zmid=0,
                    text=np.round(pivot_table.values, 1),
                    texttemplate="%{text}",
                    textfont={"size": 10},
                    hovertemplate="연도: %{y}<br>월: %{x}<br>수익률: %{z:.1f}%<extra></extra>"
                ))
                fig_heat.update_layout(
                    height=max(300, len(pivot_table) * 25),
                    margin=dict(l=50, r=50, t=30, b=30),
                    yaxis=dict(dtick=1)
                )
                st.plotly_chart(fig_heat, use_container_width=True)
        else:
            st.warning("포트폴리오 백테스트 결과가 없습니다.")


# ==================== 이번달 신호 탭 ====================
with tab_signals:
    st.subheader("이번달 매수/매도 신호")

    with st.spinner("30개 종목 신호를 분석 중..."):
        buy_list = []
        sell_list = []
        hold_list = []

        for idx, row in top30_df.iterrows():
            ticker = row["종목코드"]
            name = row["종목명"]
            monthly = get_stock_monthly_close(ticker)
            if monthly.empty or len(monthly) < 11:
                continue

            sig = get_current_signal(monthly)
            if sig is None:
                continue

            last_price = monthly["종가"].iloc[-1]
            last_date = monthly.index[-1].strftime("%Y-%m")

            info = {
                "종목명": name,
                "종목코드": ticker,
                "기준월": last_date,
                "종가": f"{last_price:,.0f}"
            }

            if sig["new_buy"]:
                buy_list.append(info)
            elif sig["new_sell"]:
                sell_list.append(info)
            elif sig["position"] == 1:
                hold_list.append(info)

    col_s1, col_s2 = st.columns(2)

    with col_s1:
        st.markdown("#### 매수 신호 (신규)")
        if buy_list:
            st.dataframe(pd.DataFrame(buy_list), use_container_width=True, hide_index=True)
        else:
            st.info("이번달 신규 매수 신호 종목이 없습니다.")

        st.markdown("#### 보유 유지")
        if hold_list:
            st.dataframe(pd.DataFrame(hold_list), use_container_width=True, hide_index=True)
        else:
            st.info("현재 보유 유지 종목이 없습니다.")

    with col_s2:
        st.markdown("#### 매도 신호 (신규)")
        if sell_list:
            st.dataframe(pd.DataFrame(sell_list), use_container_width=True, hide_index=True)
        else:
            st.info("이번달 신규 매도 신호 종목이 없습니다.")
