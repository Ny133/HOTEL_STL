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

# ------------------ 관광지 리스트 API ------------------
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

# ------------------ 관광지 수 계산 (API 기반) ------------------
@st.cache_data(ttl=3600)
def get_tourist_count(lat, lng, radius_m):
    tourist_list = get_tourist_list(api_key, lat, lng, radius_m)
    return len(tourist_list)

# ------------------ 호텔 데이터 가져오기 + 관광지 수 계산 ------------------
hotels_df = get_hotels(api_key, area_code)
hotels_df["tourist_count"] = hotels_df.apply(
    lambda x: get_tourist_count(x["lat"], x["lng"], radius_m), axis=1
)

selected_hotel = st.selectbox("호텔 선택", hotels_df["name"])
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

# ------------------ 관광지 데이터 ------------------
tourist_list = get_tourist_list(api_key, hotel_info["lat"], hotel_info["lng"], radius_m)
tourist_df = pd.DataFrame(tourist_list)
tourist_df["type_name"] = tourist_df["type"].map(TYPE_NAMES)
tourist_df["color"] = tourist_df["type"].map(TYPE_COLORS)

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
    
    # --------- 관광지 선택 ---------
    st.markdown("### 관광지 선택")
    category_list = ["선택 안 함"] + tourist_df["type_name"].unique().tolist()
    selected_category = st.selectbox("관광지 분류 선택", category_list)
    selected_spot = None
    if selected_category != "선택 안 함":
        filtered = tourist_df[tourist_df["type_name"] == selected_category]
        spot_list = ["선택 안 함"] + filtered["name"].tolist()
        selected_name = st.selectbox(f"{selected_category} 내 관광지 선택", spot_list)
        if selected_name != "선택 안 함":
            selected_spot = filtered[filtered["name"] == selected_name].iloc[0]

    # --------- 지도 + 범례 컬럼 배치 ---------
    col1, col2 = st.columns([3, 1])  # 지도 넓게, 범례 좁게

    with col1:
        # 지도 생성
        m = folium.Map(location=[hotel_info["lat"], hotel_info["lng"]], zoom_start=15)

        # 호텔 마커
        folium.Marker(
            location=[hotel_info['lat'], hotel_info['lng']],
            popup=f"{hotel_info['name']}",
            icon=folium.Icon(color='red', icon='hotel', prefix='fa')
        ).add_to(m)

        # 관광지 마커
        for _, row in tourist_df.iterrows():
            highlight = selected_spot is not None and row["name"] == selected_spot["name"]
            icon_name = TYPE_ICONS.get(row["type"], "info-sign")
            if highlight:
                icon = BeautifyIcon(
                    icon="star", icon_shape="marker",
                    border_color="yellow", text_color="white", background_color="yellow",
                    prefix="fa", icon_size=[30,30]
                )
            else:
                icon = BeautifyIcon(
                    icon=icon_name, icon_shape="circle",
                    border_color=row["color"], text_color="white", background_color=row["color"],
                    prefix="fa", icon_size=[20,20]
                )
            folium.Marker(
                location=[row["lat"], row["lng"]],
                popup=f"{row['name']} ({row['type_name']})",
                icon=icon
            ).add_to(m)

        # 선택한 관광지 강조
        if selected_spot is not None:
            m.location = [selected_spot["lat"], selected_spot["lng"]]
            m.zoom_start = 17

        # 지도 출력
        st_folium(m, width=700, height=550)

    with col2:
        # --------- 범례 ---------
        legend_html = """
        <div style="
            background-color: white;
            border:2px solid grey;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 3px 3px 6px rgba(0,0,0,0.3);
            font-size: 16px;
        ">
        <b>[관광지 범례]</b><br>
        """
    
        # 관광지 타입별 아이콘 + 색상
        for t_type, color in TYPE_COLORS.items():
            icon = TYPE_ICONS.get(t_type, "info-sign")
            name = TYPE_NAMES.get(t_type, "")
            legend_html += f'<i class="fa fa-{icon}" style="color:{color}; margin-right:5px;"></i> {name} <br>'
    
        # 선택 관광지 / 호텔
        legend_html += '<i class="fa fa-star" style="color:yellow; margin-right:5px;"></i> 선택 관광지<br>'
        legend_html += '<i class="fa fa-hotel" style="color:red; margin-right:5px;"></i> 호텔<br>'
    
        legend_html += "</div>"
    
        st.markdown(legend_html, unsafe_allow_html=True)

    # ---------------- 관광지 목록 ----------------
    st.markdown("### 관광지 목록")
    if not tourist_df.empty:
        df_list = []
        for t_type, group in tourist_df.groupby("type_name"):
            temp = group[["name","lat","lng"]].copy()
            temp["관광지 타입"] = t_type
            temp["구글 지도"] = temp.apply(
                lambda x: f'<a href="https://www.google.com/maps/search/{x["name"].replace(" ","+")}" target="_blank">지도 보기</a>', axis=1
            )
            df_list.append(temp[["관광지 타입","name","구글 지도"]])
        final_df = pd.concat(df_list, ignore_index=True)
        final_df = final_df.rename(columns={"name":"관광지명"})
        st.write(
            final_df.to_html(
                index=False, 
                escape=False,
                justify="center"
            ).replace("<th>", "<th style='text-align:center'>"),
            unsafe_allow_html=True
        )
    else:
        st.write("주변 관광지 데이터가 없습니다.")

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
