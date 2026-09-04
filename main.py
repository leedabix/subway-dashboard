import re

import pandas as pd
import plotly.express as px
import streamlit as st


# ---------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="서울 지하철 데이터 대시보드",
    page_icon="🚇",
    layout="wide",
)

PAY_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/subway_pay.csv"
TIME_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/subway_time.csv"


# ---------------------------------------------------------
# 데이터 불러오기
# ---------------------------------------------------------
@st.cache_data
def load_data():
    pay = pd.read_csv(PAY_URL)
    time = pd.read_csv(TIME_URL)

    return pay, time


pay, time = load_data()


# ---------------------------------------------------------
# 공통 데이터 정리
# ---------------------------------------------------------
def clean_station_name(name):
    """
    역 이름 뒤의 괄호 내용을 제거합니다.
    예: '신촌(지하)' → '신촌'
    """
    name = str(name)
    name = re.sub(r"\([^)]*\)", "", name)
    return name.strip()


def normalize_line_name(value):
    """
    호선명을 '1호선' ~ '9호선' 형태로 정리합니다.
    """
    value = str(value).strip()

    match = re.search(r"([1-9])호선", value)

    if match:
        return f"{match.group(1)}호선"

    return value


def find_column(df, candidates):
    """
    데이터에서 후보 이름과 일치하는 열을 찾습니다.
    """
    for candidate in candidates:
        if candidate in df.columns:
            return candidate

    raise ValueError(
        f"다음 열을 찾을 수 없습니다: {candidates}\n"
        f"현재 데이터의 열: {list(df.columns)}"
    )


# 사용월 / 호선 / 역명 열 찾기
pay_month_col = find_column(
    pay,
    ["사용월", "사용일자", "년월"],
)

pay_line_col = find_column(
    pay,
    ["호선명", "호선"],
)

pay_station_col = find_column(
    pay,
    ["지하철역", "역명", "역명(역번호)"],
)

time_month_col = find_column(
    time,
    ["사용월", "사용일자", "년월"],
)

time_line_col = find_column(
    time,
    ["호선명", "호선"],
)

time_station_col = find_column(
    time,
    ["지하철역", "역명", "역명(역번호)"],
)


# 역 이름과 호선 정리
pay["역명_정리"] = pay[pay_station_col].apply(clean_station_name)
time["역명_정리"] = time[time_station_col].apply(clean_station_name)

pay["호선_정리"] = pay[pay_line_col].apply(normalize_line_name)
time["호선_정리"] = time[time_line_col].apply(normalize_line_name)


# 1~9호선만 사용
valid_lines = [f"{i}호선" for i in range(1, 10)]

pay = pay[pay["호선_정리"].isin(valid_lines)].copy()
time = time[time["호선_정리"].isin(valid_lines)].copy()


# 사용월 숫자로 변환
pay["사용월_정리"] = pd.to_numeric(
    pay[pay_month_col],
    errors="coerce",
)

time["사용월_정리"] = pd.to_numeric(
    time[time_month_col],
    errors="coerce",
)


# ---------------------------------------------------------
# 제목
# ---------------------------------------------------------
st.title("🚇 서울 지하철 데이터 대시보드")

st.write(
    """
    서울 지하철 1~9호선의 데이터를 이용해  
    **무임 승하차 비율**, **시간대별 승하차**, **월별 유동 인구**를 살펴봅니다.
    """
)


# ---------------------------------------------------------
# 탭 만들기
# ---------------------------------------------------------
tab1, tab2, tab3 = st.tabs(
    [
        "👴 무임 비율 순위",
        "⏰ 시간대별 승하차",
        "📈 월별 유동 인구",
    ]
)


# =========================================================
# TAB 1. 무임 비율 순위
# =========================================================
with tab1:

    st.subheader("👴 무임 승하차 비율이 높은 역은 어디일까?")

    latest_pay_month = pay["사용월_정리"].max()

    latest_pay = pay[
        pay["사용월_정리"] == latest_pay_month
    ].copy()

    # 필요한 열 찾기
    paid_in_col = find_column(
        latest_pay,
        ["유임승차", "유임승차인원"],
    )

    paid_out_col = find_column(
        latest_pay,
        ["유임하차", "유임하차인원"],
    )

    free_in_col = find_column(
        latest_pay,
        ["무임승차", "무임승차인원"],
    )

    free_out_col = find_column(
        latest_pay,
        ["무임하차", "무임하차인원"],
    )

    number_cols = [
        paid_in_col,
        paid_out_col,
        free_in_col,
        free_out_col,
    ]

    for col in number_cols:
        latest_pay[col] = pd.to_numeric(
            latest_pay[col],
            errors="coerce",
        ).fillna(0)

    latest_pay["유임인원"] = (
        latest_pay[paid_in_col]
        + latest_pay[paid_out_col]
    )

    latest_pay["무임인원"] = (
        latest_pay[free_in_col]
        + latest_pay[free_out_col]
    )

    latest_pay["전체인원"] = (
        latest_pay["유임인원"]
        + latest_pay["무임인원"]
    )

    top_n = st.slider(
        "상위 몇 개 역을 볼까요?",
        min_value=5,
        max_value=30,
        value=10,
        step=1,
    )

    merge_transfer = st.checkbox(
        "환승역은 하나의 역으로 합쳐 보기",
        value=True,
    )

    if merge_transfer:

        ranking = (
            latest_pay
            .groupby("역명_정리", as_index=False)[
                ["유임인원", "무임인원", "전체인원"]
            ]
            .sum()
        )

        ranking["표시역명"] = ranking["역명_정리"]

    else:

        ranking = (
            latest_pay
            .groupby(
                ["호선_정리", "역명_정리"],
                as_index=False,
            )[
                ["유임인원", "무임인원", "전체인원"]
            ]
            .sum()
        )

        ranking["표시역명"] = (
            ranking["역명_정리"]
            + " · "
            + ranking["호선_정리"]
        )

    ranking = ranking[
        ranking["전체인원"] > 0
    ].copy()

    ranking["무임 비율"] = (
        ranking["무임인원"]
        / ranking["전체인원"]
        * 100
    )

    ranking = (
        ranking
        .sort_values(
            "무임 비율",
            ascending=False,
        )
        .head(top_n)
        .sort_values(
            "무임 비율",
            ascending=True,
        )
    )

    year = int(latest_pay_month // 100)
    month = int(latest_pay_month % 100)

    st.caption(
        f"기준: {year}년 {month}월 · "
        "무임 승차와 무임 하차 인원을 전체 승하차 인원과 비교했습니다."
    )

    fig1 = px.bar(
        ranking,
        x="무임 비율",
        y="표시역명",
        orientation="h",
        text="무임 비율",
        labels={
            "무임 비율": "무임 비율(%)",
            "표시역명": "역",
        },
    )

    fig1.update_traces(
        texttemplate="%{text:.1f}%",
        textposition="outside",
    )

    fig1.update_layout(
        yaxis_title="",
        xaxis_title="무임 비율(%)",
        height=max(450, top_n * 35),
    )

    st.plotly_chart(
        fig1,
        use_container_width=True,
    )


# =========================================================
# TAB 2. 시간대별 승하차
# =========================================================
with tab2:

    st.subheader("⏰ 시간대별 승하차 1위 역")

    latest_time_month = time["사용월_정리"].max()

    latest_time = time[
        time["사용월_정리"] == latest_time_month
    ].copy()

    # 서울 지하철 데이터는 보통
    # 04시-05시부터 다음 날 03시-04시까지 제공됩니다.
    selected_hour = st.slider(
        "시간대를 선택하세요",
        min_value=4,
        max_value=27,
        value=8,
        step=1,
    )

    start_hour = selected_hour % 24
    end_hour = (selected_hour + 1) % 24

    time_label = (
        f"{start_hour:02d}시-{end_hour:02d}시"
    )

    st.write(
        f"선택한 시간대: **{time_label}**"
    )


    def find_time_column(df, start_hour, end_hour, kind):

        possible_patterns = [
            f"{start_hour:02d}시-{end_hour:02d}시 {kind}인원",
            f"{start_hour:02d}시-{end_hour:02d}시 {kind}",
            f"{start_hour:02d}시~{end_hour:02d}시 {kind}인원",
            f"{start_hour:02d}시~{end_hour:02d}시 {kind}",
        ]

        for col in df.columns:

            clean_col = str(col).replace(" ", "")

            for pattern in possible_patterns:

                if clean_col == pattern.replace(" ", ""):
                    return col

        return None


    board_col = find_time_column(
        latest_time,
        start_hour,
        end_hour,
        "승차",
    )

    exit_col = find_time_column(
        latest_time,
        start_hour,
        end_hour,
        "하차",
    )

    if board_col is None or exit_col is None:

        st.warning(
            f"{time_label} 시간대의 승하차 열을 "
            "데이터에서 찾지 못했습니다."
        )

    else:

        latest_time[board_col] = pd.to_numeric(
            latest_time[board_col],
            errors="coerce",
        ).fillna(0)

        latest_time[exit_col] = pd.to_numeric(
            latest_time[exit_col],
            errors="coerce",
        ).fillna(0)

        # 같은 역이 여러 호선에 있으면 합산
        hourly = (
            latest_time
            .groupby(
                "역명_정리",
                as_index=False,
            )[
                [board_col, exit_col]
            ]
            .sum()
        )

        top_board = hourly.loc[
            hourly[board_col].idxmax()
        ]

        top_exit = hourly.loc[
            hourly[exit_col].idxmax()
        ]

        col1, col2 = st.columns(2)

        with col1:

            st.metric(
                "🚇 승차 1위",
                top_board["역명_정리"],
                f"{int(top_board[board_col]):,}명",
            )

        with col2:

            st.metric(
                "🏁 하차 1위",
                top_exit["역명_정리"],
                f"{int(top_exit[exit_col]):,}명",
            )

        top_board_df = (
            hourly
            .nlargest(10, board_col)
            [["역명_정리", board_col]]
            .rename(
                columns={
                    board_col: "인원",
                }
            )
        )

        top_board_df["구분"] = "승차"

        top_exit_df = (
            hourly
            .nlargest(10, exit_col)
            [["역명_정리", exit_col]]
            .rename(
                columns={
                    exit_col: "인원",
                }
            )
        )

        top_exit_df["구분"] = "하차"

        chart_data = pd.concat(
            [
                top_board_df,
                top_exit_df,
            ],
            ignore_index=True,
        )

        fig2 = px.bar(
            chart_data,
            x="인원",
            y="역명_정리",
            color="구분",
            facet_col="구분",
            orientation="h",
            labels={
                "인원": "승하차 인원",
                "역명_정리": "역",
            },
        )

        fig2.update_yaxes(
            categoryorder="total ascending"
        )

        fig2.update_layout(
            height=550,
        )

        st.plotly_chart(
            fig2,
            use_container_width=True,
        )

        year = int(latest_time_month // 100)
        month = int(latest_time_month % 100)

        st.caption(
            f"기준: {year}년 {month}월"
        )


# =========================================================
# TAB 3. 월별 유동 인구
# =========================================================
with tab3:

    st.subheader("📈 역별 월별 유동 인구 변화")

    # 유무임 데이터를 이용해 전체 승하차 인원을 계산
    paid_in_col_all = find_column(
        pay,
        ["유임승차", "유임승차인원"],
    )

    paid_out_col_all = find_column(
        pay,
        ["유임하차", "유임하차인원"],
    )

    free_in_col_all = find_column(
        pay,
        ["무임승차", "무임승차인원"],
    )

    free_out_col_all = find_column(
        pay,
        ["무임하차", "무임하차인원"],
    )

    for col in [
        paid_in_col_all,
        paid_out_col_all,
        free_in_col_all,
        free_out_col_all,
    ]:

        pay[col] = pd.to_numeric(
            pay[col],
            errors="coerce",
        ).fillna(0)

    pay["유동인구"] = (
        pay[paid_in_col_all]
        + pay[paid_out_col_all]
        + pay[free_in_col_all]
        + pay[free_out_col_all]
    )

    station_list = sorted(
        pay["역명_정리"]
        .dropna()
        .unique()
    )

    selected_station = st.selectbox(
        "역을 선택하세요",
        station_list,
    )

    station_monthly = (
        pay[
            pay["역명_정리"]
            == selected_station
        ]
        .groupby(
            "사용월_정리",
            as_index=False,
        )["유동인구"]
        .sum()
        .sort_values("사용월_정리")
    )

    station_monthly["연월"] = (
        station_monthly["사용월_정리"]
        .astype("Int64")
        .astype(str)
        .str[:4]
        + "-"
        + station_monthly["사용월_정리"]
        .astype("Int64")
        .astype(str)
        .str[4:6]
    )

    fig3 = px.line(
        station_monthly,
        x="연월",
        y="유동인구",
        markers=True,
        labels={
            "연월": "월",
            "유동인구": "승하차 인원",
        },
        title=f"{selected_station}역 월별 유동 인구",
    )

    fig3.update_layout(
        xaxis_tickangle=-45,
        hovermode="x unified",
        height=550,
    )

    st.plotly_chart(
        fig3,
        use_container_width=True,
    )

    if not station_monthly.empty:

        latest_row = station_monthly.iloc[-1]

        st.metric(
            "가장 최근 월 유동 인구",
            f"{int(latest_row['유동인구']):,}명",
        )


# ---------------------------------------------------------
# 하단 안내
# ---------------------------------------------------------
st.divider()

st.caption(
    "※ 유동 인구는 유임·무임 승차와 하차 인원을 모두 합한 값으로 계산했습니다."
)
