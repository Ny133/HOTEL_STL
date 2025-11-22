import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
import numpy as np
from folium.plugins import BeautifyIcon
import seaborn as sns
import matplotlib.pyplot as plt

# ---------- 한글 폰트 설정 ----------
plt.rcParams['font.family'] = 'Malgun Gothic'   # Windows
plt.rcParams['axes.unicode_minus'] = False
sns.set(font='Malgun Gothic', rc={'axes.unicode_minus':False})

st.set_page_config(layout="wide")
st.title("🏨 호텔 선택을 위한 대시보드")
st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">
""", unsafe_allow_html=True)

api_key = "f0e46463ccf90abd0defd9c79c8568e922e07a835961b1676cdb2065ecc23494"
radius_m = st.slider("관광지 반경 (m)", 500, 2000, 1000, step=100)

# ------------------ 타입 정의 ------------------
TYPE_COLORS = {
    75: "#32CD32", 76: "#1E90FF", 77: "#00CED1", 78: "#9370DB",
    79: "#FFB347", 80: "#A9A9A9", 82: "#FF69B4", 85: "#4682B4"
}

TYPE_NAMES = {75: "레포츠", 76: "관광지", 77: "교통", 78: "문화시설",
              79: "쇼핑", 80: "다른 숙박지", 82: "음식점", 85: "축제/공연/행사"}

TYPE_ICONS = {75: "fire", 76: "flag", 77: "plane", 78: "camera",
              79: "shopping-cart", 80: "home", 82: "cutlery", 85: "music"}

# ------------------ 지역 선택 ------------------
region_map = {
    "서울": 1,
    "부산": 6,
    "제주": 39
}

selected_region = st.sidebar.selectbox("지역 선택", list(region_map.keys()))
area_code = region_map[selected_region]

# ------------------ 호텔 데이터 ------------------
@st.cache_data(ttl=3600)
def get_hotels(api_key, area_code):
    url = "http://apis.data.go.kr/B551011/EngService2/searchStay2"
    params = {"ServiceKey": api_key, "numOfRows": 50, "pageNo": 1,
              "MobileOS": "ETC", "MobileApp": "hotel_analysis",
              "arrange": "A", "_type": "json", "areaCode": area_code}
    res = requests.get(url, params=params)
    data = res.json()
    items = data['response']['body']['items']['item']
    df = pd.DataFrame(items)
    df = df.rename(columns={"title": "name", "mapy": "lat", "mapx": "lng"})
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
    df = df.dropna(subset=["lat","lng"])
    df["price"] = np.random.randint(150000, 300000, size=len(df))
    df["rating"] = np.random.uniform(3.0,5.0, size=len(df)).round(1)
    return df

hotels_df = get_hotels(api_key, area_code)
selected_hotel = st.selectbox("호텔 선택", hotels_df["name"])
hotel_info = hotels_df[hotels_df["name"]==selected_hotel].iloc[0]

# ------------------ 관광지 데이터 ------------------
@st.cache_data(ttl=3600)
def get_tourist_list(api_key, lat, lng, radius_m):
    url = "http://apis.data.go.kr/B551011/EngService2/locationBasedList2"
    params = {"ServiceKey": api_key, "numOfRows": 200, "pageNo":1,
              "MobileOS":"ETC","MobileApp":"hotel_analysis",
              "mapX":lng,"mapY":lat,"radius":radius_m,"arrange":"A","_type":"json"}
    try:
        res = requests.get(url, params=params)
        data = res.json()
        items = data["response"]["body"]["items"]["item"]
        results = []
        for t in items if isinstance(items, list) else [items]:
            results.append({
                "name": t.get("title",""),
                "lat": float(t.get("mapy",0)),
                "lng": float(t.get("mapx",0)),
                "type": int(t.get("contenttypeid",0)),
            })
        return results
    except:
        return []

# ------------------ 호텔별 관광지 수 계산 (캐시 적용) ------------------
@st.cache_data(ttl=3600)
def get_tourist_count(lat, lng, radius_m):
    tourist_list = get_tourist_list(api_key, lat, lng, radius_m)
    return len(tourist_list)

# 호텔별 관광지 수 계산
hotels_df["tourist_count"] = hotels_df.apply(lambda x: get_tourist_count(x["lat"], x["lng"], radius_m), axis=1)
hotel_info = hotels_df[hotels_df["name"]==selected_hotel].iloc[0]

# ------------------ 페이지 선택 ------------------
page = st.radio(
    "페이지 선택",
    ["호텔 정보", "관광지 보기", "호텔 비교 분석"],
    horizontal=True
)

# ------------------ 호텔 이미지 ------------------
def get_hotel_images(api_key, content_id):
    url = "http://apis.data.go.kr/B551011/EngService2/detailImage2"
    params = {
        "ServiceKey": api_key,
        "MobileOS": "ETC",
        "MobileApp": "hotel_app",
        "contentId": content_id,
        "imageYN": "Y",
        "_type": "json"
    }
    try:
        res = requests.get(url, params=params)
        data = res.json()
        items = data["response"]["body"]["items"]["item"]
        if isinstance(items, dict):
            return [items.get("originimgurl")]
        return [i.get("originimgurl") for i in items if i.get("originimgurl")]
    except:
        return []

# ------------------ 페이지별 처리 ------------------
if page == "호텔 정보":
    st.subheader(f"🏨 {selected_region} 선택 호텔 정보")
    st.markdown(f"""
**호텔명:** {hotel_info['name']}  
**가격:** {hotel_info['price']:,}원  
**평점:** ⭐ {hotel_info['rating']}  
**주변 관광지 수:** {hotel_info['tourist_count']}
""")

elif page == "관광지 보기":
    st.subheader(f"📍 {selected_region} 호텔 주변 관광지 보기")
    tourist_list = get_tourist_list(api_key, hotel_info["lat"], hotel_info["lng"], radius_m)
    tourist_df = pd.DataFrame(tourist_list)
    if not tourist_df.empty:
        tourist_df["type_name"] = tourist_df["type"].map(TYPE_NAMES)
        tourist_df["color"] = tourist_df["type"].map(TYPE_COLORS)
        st.write(tourist_df[["name","type_name"]])
    else:
        st.write("주변 관광지 데이터가 없습니다.")

elif page == "호텔 비교 분석":
    st.subheader(f"📊 {selected_region} 선택 호텔 비교")
    st.table(hotels_df[["name","price","rating","tourist_count"]])
