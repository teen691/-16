# main.py — 급식 규칙 찾기: 같은 날 함께 나온 메뉴 쌍을 센다
import re
from collections import Counter
from itertools import combinations

import pandas as pd
import plotly.express as px
import streamlit as st

URL = "https://raw.githubusercontent.com/it-teacher-go/data-share-/main/songtan_meals_184.csv"

st.title("🍚 급식 규칙 찾기")


@st.cache_data(ttl=3600)
def load_baskets(url):
    table = pd.read_csv(url, encoding="utf-8")
    baskets = []
    for line in table["메뉴"]:
        names = set()
        for dish in str(line).split("|"):
            name = re.sub(r"\([^)]*\)", "", dish).strip()   # 괄호와 그 안의 내용은 제외한다
            if name:
                names.add(name)
        if names:
            baskets.append(sorted(names))
    return baskets


baskets = load_baskets(URL)
n = len(baskets)
single = Counter(item for basket in baskets for item in basket)           # 메뉴가 나온 날 수
pair = Counter(c for basket in baskets for c in combinations(basket, 2))  # 두 메뉴가 함께 나온 날 수

rows = []
for (a, b), together in pair.items():
    for x, y in [(a, b), (b, a)]:              # 한 쌍에서 두 방향의 규칙이 나온다
        rows.append({"조건": x, "결과": y, "동시": together,
                     "지지도": round(together / n, 3),
                     "신뢰도": round(together / single[x], 3),
                     "향상도": round((together / single[x]) / (single[y] / n), 2)})
규칙 = pd.DataFrame(rows, columns=["조건", "결과", "동시", "지지도", "신뢰도", "향상도"])

st.caption(f"급식 {n}일 · 메뉴 {len(single)}종 · 함께 나온 적이 있는 메뉴 쌍 {len(pair):,}개 · "
           f"규칙 {len(규칙):,}개")

기준 = st.radio("정렬", ["향상도 순", "신뢰도 순", "동시 순"], horizontal=True)
메뉴 = st.selectbox("메뉴로 좁혀 보기", ["(전체)"] + sorted(single))
보기 = 규칙 if 메뉴 == "(전체)" else 규칙[(규칙["조건"] == 메뉴) | (규칙["결과"] == 메뉴)]
보기 = 보기.sort_values({"향상도 순": "향상도", "신뢰도 순": "신뢰도", "동시 순": "동시"}[기준],
                    ascending=False, ignore_index=True)
st.dataframe(보기, width="stretch", hide_index=True)

top = 보기.sort_values("향상도", ascending=False).head(10).copy()
top["규칙"] = top["조건"] + " → " + top["결과"]
fig = px.bar(top, x="향상도", y="규칙", orientation="h", text="향상도")
fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=420)
st.plotly_chart(fig, width="stretch")
