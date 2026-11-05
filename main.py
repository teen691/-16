# main.py — 급식 규칙 찾기: 같은 날 함께 나온 메뉴 쌍을 센다
"""송탄고 급식 데이터로 두 메뉴 사이의 연관규칙을 탐색합니다."""

from collections import Counter
from itertools import combinations
import re

import pandas as pd
import plotly.express as px
import streamlit as st


DATA_URL = "https://raw.githubusercontent.com/it-teacher-go/data-share-/main/songtan_meals_184.csv"

st.set_page_config(page_title="급식 규칙 찾기", page_icon="🍱", layout="wide")
st.title("🍱 급식 규칙 찾기")
st.caption("송탄고 중식 · 하루 식단을 장바구니 1건으로 계산합니다.")


def clean_menu(value):
    """메뉴명에 붙은 괄호 정보(중첩 괄호 포함)를 제거합니다."""
    value = str(value)
    previous = None
    while previous != value:
        previous = value
        value = re.sub(r"\([^()]*\)|\[[^\[\]]*\]|（[^（）]*）", "", value)
    return re.sub(r"\s+", " ", value).strip()


@st.cache_data(ttl=3600)
def load_data():
    df = pd.read_csv(DATA_URL, encoding="utf-8-sig", dtype=str)
    required = {"날짜", "식사", "메뉴"}
    if not required.issubset(df.columns):
        raise ValueError(f"CSV에 필요한 열이 없습니다: {', '.join(sorted(required - set(df.columns)))}")

    baskets = []
    for raw in df["메뉴"].fillna(""):
        # 같은 날 동일 메뉴가 여러 번 기록되어도 한 번만 셉니다.
        items = {clean_menu(item) for item in raw.split("|")}
        items.discard("")
        baskets.append(items)
    return baskets


@st.cache_data(ttl=3600)
def build_rules(baskets_as_tuples):
    baskets = [set(items) for items in baskets_as_tuples]
    days = len(baskets)
    menu_counts = Counter(item for basket in baskets for item in basket)
    pair_counts = Counter(
        pair for basket in baskets for pair in combinations(sorted(basket), 2)
    )

    records = []
    for (a, b), together in pair_counts.items():
        for antecedent, consequent in ((a, b), (b, a)):
            support = together / days
            confidence = together / menu_counts[antecedent]
            lift = confidence / (menu_counts[consequent] / days)
            records.append({
                "조건": antecedent,
                "결과": consequent,
                "동시": together,
                "지지도": support,
                "신뢰도": confidence,
                "향상도": lift,
            })

    columns = ["조건", "결과", "동시", "지지도", "신뢰도", "향상도"]
    return pd.DataFrame(records, columns=columns), menu_counts, pair_counts


try:
    baskets = load_data()
    if not baskets:
        st.warning("CSV에서 급식 데이터를 찾지 못했습니다.")
        st.stop()
except Exception as exc:
    st.error(f"급식 데이터를 불러오지 못했습니다: {exc}")
    st.stop()

rules, menu_counts, pair_counts = build_rules(tuple(tuple(sorted(b)) for b in baskets))

col1, col2, col3 = st.columns(3)
col1.metric("급식 일수", f"{len(baskets):,}일")
col2.metric("메뉴 종류 수", f"{len(menu_counts):,}종")
col3.metric("함께 나온 메뉴 쌍", f"{len(pair_counts):,}쌍")

st.caption("메뉴 쌍은 순서를 구분하지 않은 개수이며, 아래 규칙 표에는 조건과 결과를 바꾼 두 방향이 모두 포함됩니다.")

filter_col, sort_col = st.columns([2, 1])
with filter_col:
    menus = sorted(menu_counts)
    selected = st.selectbox("규칙 좁혀 보기: 메뉴 선택", ["전체 메뉴"] + menus)
with sort_col:
    sort_name = st.selectbox("정렬 기준", ["향상도 순", "신뢰도 순", "동시 순"])

min_together = st.slider("최소 동시 등장 일수", min_value=1, max_value=10, value=1, step=1)

filtered = rules[rules["동시"] >= min_together].copy()
if selected != "전체 메뉴":
    filtered = filtered[
        (filtered["조건"] == selected) | (filtered["결과"] == selected)
    ]

sort_key = {"향상도 순": "향상도", "신뢰도 순": "신뢰도", "동시 순": "동시"}[sort_name]
sort_columns = [sort_key] + [x for x in ("향상도", "신뢰도", "동시") if x != sort_key]
filtered = filtered.sort_values(
    sort_columns + ["조건", "결과"],
    ascending=[False, False, False, True, True],
).reset_index(drop=True)

st.subheader("연관규칙 표")
st.write(f"최소 {min_together}일 이상 함께 등장한 규칙은 **{len(filtered):,}개**입니다. (양방향 규칙 포함)")
st.dataframe(
    filtered,
    use_container_width=True,
    hide_index=True,
    column_config={
        "지지도": st.column_config.NumberColumn("지지도", format="%.3f"),
        "신뢰도": st.column_config.NumberColumn("신뢰도", format="%.3f"),
        "향상도": st.column_config.NumberColumn("향상도", format="%.2f"),
    },
)

st.subheader("향상도 상위 10개 규칙")
top10 = filtered.sort_values(
    ["향상도", "동시", "조건", "결과"], ascending=[False, False, True, True]
).head(10).copy()

if top10.empty:
    st.info("표시할 규칙이 없습니다.")
else:
    top10["규칙"] = top10["조건"] + " → " + top10["결과"]
    # plotly는 카테고리 축을 아래에서 위로 표시하므로 역순으로 정렬합니다.
    top10 = top10.iloc[::-1]
    fig = px.bar(
        top10,
        x="향상도",
        y="규칙",
        orientation="h",
        text="향상도",
        hover_data={"동시": True, "지지도": ":.3f", "신뢰도": ":.3f", "향상도": ":.2f"},
        labels={"규칙": "", "향상도": "향상도 (Lift)"},
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig.update_layout(height=max(340, 55 * len(top10)), margin=dict(l=10, r=60, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

st.caption("지지도 = 동시 등장 일수 ÷ 전체 급식 일수 · 신뢰도 = 동시 등장 일수 ÷ 조건 메뉴 등장 일수 · 향상도 = 신뢰도 ÷ 결과 메뉴 등장 비율")
st.info("향상도가 1보다 크면 우연히 기대되는 수준보다 함께 등장하는 경향이 강합니다. 다만 드문 메뉴 쌍의 향상도도 클 수 있으므로 동시 등장 일수를 함께 확인하세요. 연관규칙은 인과관계를 뜻하지 않습니다.")

st.divider()
st.subheader("함께 나온 적 없는 짝")
st.caption("선택한 메뉴와 같은 날 한 번도 등장하지 않았지만, 전체 기간에 10일 이상 등장한 다른 메뉴를 찾습니다.")
never_selected = st.selectbox("함께 나온 적 없는 짝 찾기: 기준 메뉴", menus, key="never_together_menu")
st.write(f"**{never_selected}** 등장 일수: **{menu_counts[never_selected]:,}일**")

never_together = [
    {"메뉴": other, "등장 일수": count}
    for other, count in menu_counts.items()
    if other != never_selected
    and count >= 10
    and pair_counts.get(tuple(sorted((never_selected, other))), 0) == 0
]
never_df = pd.DataFrame(never_together, columns=["메뉴", "등장 일수"])
never_df = never_df.sort_values(
    ["등장 일수", "메뉴"], ascending=[False, True]
).reset_index(drop=True)
st.write(f"조건에 맞는 메뉴: **{len(never_df):,}종**")
if never_df.empty:
    st.info("조건에 맞는 메뉴가 없습니다.")
else:
    st.dataframe(never_df, hide_index=True, use_container_width=True)
