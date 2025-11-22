import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
import numpy as np
from folium.plugins import BeautifyIcon
import seaborn as sns
import matplotlib.pyplot as plt
import os
import io # '구글 지도' 링크 임시 수정용

# ---------- 한글 폰트 설정 및 Matplotlib 스타일 ----------
# Matplotlib 폰트 설정 (Streamlit 환경에 따라 'Malgun Gothic'이 없을 수 있으나, 
# 사용자 로컬 환경에서는 보통 동작함. 없으면 기본 폰트로 대체됨)
plt.rcParams['font.family'] = 'Malgun Gothic'   # Windows 폰트
plt.rcParams['axes.unicode_minus'] = False # 마이너스 폰트 깨짐 방지
sns.set(font='Malgun Gothic', rc={'axes.unicode_minus':False})

st.set_page_config(layout="wide")
st.title("🏨 호텔 선택을 위한 대시보드")
st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">
""", unsafe_allow_html=True)

# API 키 설정 (보안상 환경변수 또는 Streamlit Secrets 사용을 권장하지만, 예시로 하드코딩)
# 실제 사용 시에는 이 부분을 반드시 보호하세요.
# 예: api_key = st.secrets["data_api"]["key"]
api_key = "f0e46463ccf90abd0defd9c79c8568e922e07a835961b1676cdb2065ecc23494"
# 참고: 이 API 키는 공공 데이터 포털의 '국문 관광정보 서비스(TourAPI 3.0)'의 테스트 키로 보이며, 
# '영문 관광정보 서비스' API에서 사용 가능 여부는 확인이 필요합니다.

# 슬라이더: 관광지 검색 반경
radius_m = st.slider("관광지 반경 (m)", 500, 2000, 1000, step=100)

# ------------------ 타입 정의 ------------------
# contenttypeid에 따른 색상, 이름, 아이콘 정의
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

# ------------------ 호텔 데이터 캐싱 및 로드 ------------------
@st.cache_data(ttl=3600)
def get_hotels(api_key, area_code):
    """지정된 지역의 숙박 정보를 API에서 가져옵니다."""
    url = "http://apis.data.go.kr/B551011/EngService2/searchStay2"
    params = {"ServiceKey": api_key, "numOfRows": 50, "pageNo": 1,
              "MobileOS": "ETC", "MobileApp": "hotel_analysis",
              "arrange": "A", "_type": "json", "areaCode": area_code}
    
    try:
        res = requests.get(url, params=params)
        res.raise_for_status() # HTTP 오류가 있으면 예외 발생
        data = res.json()
        items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
        
        # item이 딕셔너리 하나일 경우 리스트로 변환
        if isinstance(items, dict):
            items = [items]

        df = pd.DataFrame(items)
        if df.empty:
            st.error(f"{selected_region} 지역의 호텔 데이터를 불러오지 못했습니다.")
            return pd.DataFrame()
            
        df = df.rename(columns={"title": "name", "mapy": "lat", "mapx": "lng"})
        df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
        df = df.dropna(subset=["lat","lng"])
        
        # 임의의 데이터 추가 (가격, 평점, 주변 관광지 수)
        n = len(df)
        df["price"] = np.random.randint(150000, 300000, size=n)
        df["rating"] = np.random.uniform(3.0, 5.0, size=n).round(1)
        df["tourist_count"] = np.random.randint(5, 20, size=n)
        return df

    except requests.exceptions.RequestException as e:
        st.error(f"API 요청 중 오류 발생: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"데이터 처리 중 오류 발생: {e}")
        return pd.DataFrame()

# 데이터 로드
hotels_df = get_hotels(api_key, area_code)

if hotels_df.empty:
    st.stop() # 데이터 없으면 실행 중지

selected_hotel = st.selectbox("호텔 선택", hotels_df["name"])
hotel_info = hotels_df[hotels_df["name"]==selected_hotel].iloc[0]

# ------------------ 주변 관광지 데이터 캐싱 및 로드 ------------------
@st.cache_data(ttl=3600)
def get_tourist_list(api_key, lat, lng, radius_m):
    """특정 좌표와 반경 내의 관광지 정보를 API에서 가져옵니다."""
    url = "http://apis.data.go.kr/B551011/EngService2/locationBasedList2"
    params = {"ServiceKey": api_key, "numOfRows": 200, "pageNo":1,
              "MobileOS":"ETC","MobileApp":"hotel_analysis",
              "mapX":lng,"mapY":lat,"radius":radius_m,"arrange":"A","_type":"json"}
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        data = res.json()
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        
        if isinstance(items, dict):
            items = [items]
            
        results = []
        for t in items:
            # 숙박지(80)는 제외하고, 지도 데이터가 있는 항목만 처리
            content_type = int(t.get("contenttypeid", 0))
            if content_type == 80:
                continue
            
            try:
                results.append({
                    "name": t.get("title",""),
                    "lat": float(t.get("mapy",0)),
                    "lng": float(t.get("mapx",0)),
                    "type": content_type,
                })
            except ValueError:
                # lat, lng 변환 오류 무시
                continue
                
        return results
    except:
        return []

tourist_list = get_tourist_list(api_key, hotel_info["lat"], hotel_info["lng"], radius_m)
tourist_df = pd.DataFrame(tourist_list)
if not tourist_df.empty:
    tourist_df["type_name"] = tourist_df["type"].map(TYPE_NAMES).fillna("기타")
    tourist_df["color"] = tourist_df["type"].map(TYPE_COLORS).fillna("#000000") # 매핑되지 않은 타입은 검정
else:
    tourist_df = pd.DataFrame(columns=["name", "lat", "lng", "type", "type_name", "color"])

# ------------------ 페이지 선택 ------------------
page = st.radio(
    "페이지 선택",
    ["호텔 정보", "관광지 보기", "호텔 비교 분석"],
    horizontal=True
)
st.markdown("---") # 페이지 구분선

# ------------------ 호텔 이미지 로드 함수 ------------------
@st.cache_data(ttl=3600)
def get_hotel_images(api_key, content_id):
    """호텔의 상세 이미지를 API에서 가져옵니다."""
    if not content_id:
        return []
        
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
        res.raise_for_status()
        data = res.json()
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        
        if isinstance(items, dict):
            items = [items]
            
        # 원본 이미지 URL만 추출
        return [i.get("originimgurl") for i in items if i.get("originimgurl")]
    except:
        return []

# ------------------ 페이지별 처리 ------------------
if page == "호텔 정보":
    ## 🏨 호텔 정보 페이지
    
    st.subheader(f"🏨 {selected_region} 선택 호텔 정보")
    
    # 기본 정보 카드
    col_info, col_counts = st.columns([2, 1])

    with col_info:
        st.markdown(f"""
        <div style="
            padding: 15px; 
            border: 1px solid #d3d3d3; 
            border-radius: 5px; 
            margin-bottom: 20px;">
        **호텔명:** {hotel_info['name']}  
        **가격:** {hotel_info['price']:,}원  
        **평점:** ⭐ **{hotel_info['rating']}** **주변 관광지 수:** **{hotel_info['tourist_count']}**
        </div>
        """, unsafe_allow_html=True)
        
    # 관광지 타입별 수
    with col_counts:
        st.markdown("#### 주변 관광지 타입별 개수")
        if not tourist_df.empty:
            type_counts = tourist_df.groupby("type_name").size().reset_index(name="개수")
            type_counts = type_counts.rename(columns={"type_name":"관광지 타입"})
            st.dataframe(type_counts, use_container_width=True, hide_index=True)
        else:
            st.info("주변 관광지 데이터가 없습니다.")

    st.markdown("---")
    
    # 호텔 이미지
    st.markdown("### 📷 호텔 이미지")
    images = get_hotel_images(api_key, hotel_info.get("contentid", ""))
    if images:
        st.image(images, width=300)
    else:
        st.info("호텔 이미지를 불러올 수 없습니다.")
        
    st.markdown("---")
        
    # 주변 관광지 Top5
    st.markdown("### 주변 관광지 Top 5 (거리순)")
    if not tourist_df.empty:
        # 호텔과 관광지 간의 유클리드 거리 계산 (대략적인 거리)
        tourist_df_filtered = tourist_df[tourist_df["type"] != 80].copy() # 숙박지(80) 제외
        tourist_df_filtered["dist"] = np.sqrt(
            (tourist_df_filtered["lat"] - hotel_info["lat"])**2 +
            (tourist_df_filtered["lng"] - hotel_info["lng"])**2
        )
        top5 = tourist_df_filtered.sort_values("dist").head(5)
        for i, row in top5.iterrows():
            st.write(f"**{i+1}. {row['name']}** ({row['type_name']})")
    else:
        st.info("주변 관광지 데이터가 없습니다.")
    
    st.markdown("---")
    
    # 예약 링크
    booking_url = f"https://www.booking.com/searchresults.ko.html?ss={hotel_info['name'].replace(' ','+')}"
    st.markdown(f"""
<div style="
    padding: 15px; 
    border: 2px solid #0071c2; 
    background-color: #e6f7ff; 
    border-radius: 10px; 
    text-align: center;
    font-size: 18px;
    font-weight: bold;">
    <a href="{booking_url}" target="_blank" style="text-decoration:none; color: #0071c2;">
        <i class="fa fa-external-link" style="margin-right: 10px;"></i>
        '{hotel_info['name']}' 예약하러 가기
    </a>
</div>
""", unsafe_allow_html=True)

elif page == "관광지 보기":
    ## 📍 관광지 보기 페이지 (Folium 지도)
    
    st.subheader(f"📍 {selected_region} 호텔 주변 관광지 보기")
    
    # --------- 관광지 선택 ---------
    st.markdown("### 관광지 선택")
    
    selected_spot = None
    if not tourist_df.empty:
        category_list = ["선택 안 함"] + tourist_df["type_name"].unique().tolist()
        selected_category = st.selectbox("관광지 분류 선택", category_list)
        
        if selected_category != "선택 안 함":
            filtered = tourist_df[tourist_df["type_name"] == selected_category]
            spot_list = ["선택 안 함"] + filtered["name"].tolist()
            selected_name = st.selectbox(f"'{selected_category}' 내 관광지 선택", spot_list)
            if selected_name != "선택 안 함":
                selected_spot = filtered[filtered["name"] == selected_name].iloc[0]
    else:
        st.info("주변 관광지 데이터가 없어 지도를 표시할 수 없습니다.")
        st.stop()


    # --------- 지도 + 범례 컬럼 배치 ---------
    col1, col2 = st.columns([3, 1])  # 지도 넓게, 범례 좁게

    with col1:
        # 지도 생성
        map_center_lat = selected_spot["lat"] if selected_spot is not None else hotel_info["lat"]
        map_center_lng = selected_spot["lng"] if selected_spot is not None else hotel_info["lng"]
        map_zoom = 17 if selected_spot is not None else 15
        
        m = folium.Map(location=[map_center_lat, map_center_lng], zoom_start=map_zoom)

        # 호텔 마커 (빨간색)
        folium.Marker(
            location=[hotel_info['lat'], hotel_info['lng']],
            popup=f"**호텔:** {hotel_info['name']}",
            icon=folium.Icon(color='red', icon='hotel', prefix='fa')
        ).add_to(m)

        # 관광지 마커
        for _, row in tourist_df.iterrows():
            highlight = selected_spot is not None and row["name"] == selected_spot["name"]
            icon_name = TYPE_ICONS.get(row["type"], "info-sign")
            
            # 선택된 관광지는 별 모양 노란색 테두리로 강조
            if highlight:
                icon = BeautifyIcon(
                    icon="star", icon_shape="marker",
                    border_color="yellow", text_color="black", background_color="yellow",
                    prefix="fa", icon_size=[30,30]
                )
            else:
                # 일반 관광지는 원 모양
                icon = BeautifyIcon(
                    icon=icon_name, icon_shape="circle",
                    border_color=row["color"], text_color="white", background_color=row["color"],
                    prefix="fa", icon_size=[20,20]
                )
            folium.Marker(
                location=[row["lat"], row["lng"]],
                popup=f"**{row['name']}** ({row['type_name']})",
                icon=icon
            ).add_to(m)

        # 지도 출력
        st_folium(m, width=700, height=550)

    with col2:
        # --------- 범례 ---------
        legend_html = """
        <div style="
            background-color: white;
            border:2px solid #d3d3d3;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 3px 3px 6px rgba(0,0,0,0.3);
            font-size: 16px;
        ">
        <b>[관광지 범례]</b><br>
        <hr style="margin-top: 5px; margin-bottom: 5px;">
        """
    
        # 관광지 타입별 아이콘 + 색상
        for t_type, name in TYPE_NAMES.items():
            if t_type == 80: continue # 다른 숙박지는 범례에서 제외
            color = TYPE_COLORS.get(t_type, "#000000")
            icon = TYPE_ICONS.get(t_type, "info-sign")
            legend_html += f'<i class="fa fa-{icon}" style="color:{color}; margin-right:5px; width: 20px;"></i> {name} <br>'
    
        # 선택 관광지 / 호텔
        legend_html += '<hr style="margin-top: 5px; margin-bottom: 5px;">'
        legend_html += '<i class="fa fa-star" style="color:yellow; margin-right:5px; width: 20px;"></i> 선택 관광지<br>'
        legend_html += '<i class="fa fa-hotel" style="color:red; margin-right:5px; width: 20px;"></i> 호텔<br>'
    
        legend_html += "</div>"
    
        st.markdown(legend_html, unsafe_allow_html=True)

    st.markdown("---")

    # ---------------- 관광지 목록 ----------------
    st.markdown("### 주변 관광지 목록")
    if not tourist_df.empty:
        # 그룹별로 목록을 정리
        df_list = []
        for t_type_name, group in tourist_df.groupby("type_name"):
            temp = group[["name","lat","lng"]].copy()
            temp["관광지 타입"] = t_type_name
            # 구글 지도 링크 생성
            temp["구글 지도"] = temp.apply(
                lambda x: f'<a href="https://www.google.com/maps/search/?api=1&query={x["lat"]},{x["lng"]}" target="_blank">지도 보기</a>', axis=1
            )
            df_list.append(temp[["관광지 타입","name","구글 지도"]])
            
        final_df = pd.concat(df_list, ignore_index=True)
        final_df = final_df.rename(columns={"name":"관광지명"})
        
        # HTML 테이블로 출력 (Streamlit의 기본 st.dataframe보다 커스터마이징이 용이)
        st.write(
            final_df.to_html(
                index=False, 
                escape=False,
                justify="center"
            ).replace("<th>", "<th style='text-align:center'>"),
            unsafe_allow_html=True
        )
    else:
        st.info("주변 관광지 데이터가 없습니다.")

elif page == "호텔 비교 분석":
    ## 📊 호텔 비교 분석 페이지
    
    st.subheader(f"📊 {selected_region} 선택 호텔 비교")
    
    selected_hotel_row = hotels_df[hotels_df["name"] == selected_hotel].iloc[0]
    
    st.markdown(f"""
    <div style="
        padding: 15px; 
        border: 1px solid #d3d3d3; 
        border-radius: 5px; 
        margin-bottom: 20px;">
    **선택 호텔 ({selected_hotel_row['name']}):** 가격: **{selected_hotel_row['price']:,}원** | 평점: **{selected_hotel_row['rating']}** | 주변 관광지 수: **{selected_hotel_row['tourist_count']}**
    </div>
    """, unsafe_allow_html=True)
    
    # 지역별 평균 계산
    avg_rating = hotels_df["rating"].mean()
    avg_price = hotels_df["price"].mean()
    avg_tourist = hotels_df["tourist_count"].mean()
    
    st.markdown(f"**{selected_region} 지역 호텔 평균** 평점: **{avg_rating:.2f}** | 주변 관광지 수: **{avg_tourist:.1f}** | 가격: **{avg_price:,.0f}원**")

    st.markdown("---")
    
    st.markdown("### 지역 내 분포 비교")
    st.markdown("각 그래프의 **빨간색 점선**은 **선택한 호텔의 값**을 나타냅니다.")

    # 시각화 (평점, 관광지 수, 가격 분포)
    fig, axes = plt.subplots(1,3, figsize=(18,5))
    
    # 1. 평점 분포
    sns.histplot(hotels_df["rating"], bins=10, kde=True, ax=axes[0], color='skyblue')
    axes[0].axvline(selected_hotel_row["rating"], color='red', linestyle='--', label=f"선택 호텔: {selected_hotel_row['rating']}")
    axes[0].set_title("평점 분포 (Rating Distribution)", fontsize=15)
    axes[0].set_xlabel("평점")
    axes[0].legend()
    
    # 2. 주변 관광지 수 분포
    sns.histplot(hotels_df["tourist_count"], bins=10, kde=True, ax=axes[1], color='lightgreen')
    axes[1].axvline(selected_hotel_row["tourist_count"], color='red', linestyle='--', label=f"선택 호텔: {selected_hotel_row['tourist_count']}")
    axes[1].set_title("주변 관광지 수 분포 (Nearby Attractions Distribution)", fontsize=15)
    axes[1].set_xlabel("주변 관광지 수")
    axes[1].legend()

    # 3. 가격 분포
    sns.histplot(hotels_df["price"], bins=10, kde=True, ax=axes[2], color='lightcoral')
    axes[2].axvline(selected_hotel_row["price"], color='red', linestyle='--', label=f"선택 호텔: {selected_hotel_row['price']:,}원")
    axes[2].set_title("가격 분포 (Price Distribution)", fontsize=15)
    axes[2].set_xlabel("가격 (원)")
    axes[2].ticklabel_format(style='plain', axis='x') # 과학적 표기법 방지
    axes[2].legend()
    
    plt.tight_layout()
    st.pyplot(fig)

```
