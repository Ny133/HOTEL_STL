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
st.title("🏨 호텔 + 주변 관광지 시각화")
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
    df["tourist_count"] = np.random.randint(5, 20, size=len(df))
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

tourist_list = get_tourist_list(api_key, hotel_info["lat"], hotel_info["lng"], radius_m)
tourist_df = pd.DataFrame(tourist_list)
tourist_df["type_name"] = tourist_df["type"].map(TYPE_NAMES)
tourist_df["color"] = tourist_df["type"].map(TYPE_COLORS)

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
    
    # 관광지 타입별 수
    type_counts = tourist_df.groupby("type_name").size().reset_index(name="개수")
    type_counts = type_counts.rename(columns={"type_name":"관광지 타입"})
    st.table(type_counts)
    
    # 호텔 이미지
    st.markdown("### 📷 호텔 이미지")
    images = get_hotel_images(api_key, hotel_info.get("contentid", ""))
    if images:
        st.image(images, width=300)
    else:
        st.write("이미지 없음")
        
    # 주변 관광지 Top5
    st.markdown("### 주변 관광지 Top 5")
    tourist_df_filtered = tourist_df[tourist_df["type"] != 80]
    tourist_df_filtered["dist"] = np.sqrt(
        (tourist_df_filtered["lat"] - hotel_info["lat"])**2 +
        (tourist_df_filtered["lng"] - hotel_info["lng"])**2
    )
    top5 = tourist_df_filtered.sort_values("dist").head(5)
    for _, row in top5.iterrows():
        st.write(f"- **{row['name']}** ({row['type_name']})")
    
    # 예약 링크
    booking_url = f"https://www.booking.com/searchresults.ko.html?ss={hotel_info['name'].replace(' ','+')}"
    st.markdown(f"""
<div style="
    padding: 15px; 
    border: 2px solid #d3d3d3; 
    background-color: #f0f0f0; 
    border-radius: 10px; 
    text-align: center;
    font-size: 18px;
    font-weight: bold;">
    <a href="{booking_url}" target="_blank">👉 '{hotel_info['name']}' 예약하러 가기</a>
</div>
""", unsafe_allow_html=True)

elif page == "관광지 보기":
    st.subheader(f"📍 {selected_region} 호텔 주변 관광지 보기")
    
    # 지도
    m = folium.Map(location=[hotel_info["lat"], hotel_info["lng"]], zoom_start=15)
    folium.Marker(
        location=[hotel_info['lat'], hotel_info['lng']],
        popup=f"{hotel_info['name']}",
        icon=folium.Icon(color='red', icon='hotel', prefix='fa')
    ).add_to(m)
    
    for _, row in tourist_df.iterrows():
        icon = BeautifyIcon(
            icon=TYPE_ICONS.get(row["type"], "info-sign"), icon_shape="circle",
            border_color=row["color"], text_color="white", background_color=row["color"],
            prefix="fa", icon_size=[20,20]
        )
        folium.Marker(
            location=[row["lat"], row["lng"]],
            popup=f"{row['name']} ({row['type_name']})",
            icon=icon
        ).add_to(m)
    
    st_folium(m, width=700, height=550)
    
elif page == "호텔 비교 분석":
    st.subheader(f"📊 {selected_region} 선택 호텔 비교")
    
    selected_hotel_row = hotels_df[hotels_df["name"] == selected_hotel].iloc[0]
    
    st.markdown(f"""
**호텔:** {selected_hotel_row['name']}  
**가격:** {selected_hotel_row['price']:,}원  
**평점:** ⭐ {selected_hotel_row['rating']}  
**주변 관광지 수:** {selected_hotel_row['tourist_count']}
""")
    
    # 지역별 평균 계산
    avg_rating = hotels_df["rating"].mean()
    avg_price = hotels_df["price"].mean()
    avg_tourist = hotels_df["tourist_count"].mean()
    
    st.markdown(f"**{selected_region} 호텔 평균**  평점: {avg_rating:.2f}  주변 관광지 수: {avg_tourist:.1f}  가격: {avg_price:,.0f}원")
    
    # 시각화 (영문/숫자만, 선택 호텔 빨간선)
    fig, axes = plt.subplots(1,3, figsize=(18,5))
    
    sns.histplot(hotels_df["rating"], bins=10, kde=True, ax=axes[0], color='skyblue')
    axes[0].axvline(selected_hotel_row["rating"], color='red', linestyle='--')
    axes[0].set_title("Rating Distribution")
    
    sns.histplot(hotels_df["tourist_count"], bins=10, kde=True, ax=axes[1], color='lightgreen')
    axes[1].axvline(selected_hotel_row["tourist_count"], color='red', linestyle='--')
    axes[1].set_title("Nearby Attractions Distribution")
    
    sns.histplot(hotels_df["price"], bins=10, kde=True, ax=axes[2], color='lightcoral')
    axes[2].axvline(selected_hotel_row["price"], color='red', linestyle='--')
    axes[2].set_title("Price Distribution")
    
    st.pyplot(fig)
