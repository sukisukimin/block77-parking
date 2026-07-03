import streamlit as st
import pandas as pd
import re
import altair as alt
from datetime import datetime

# 1. 앱 기본 설정
st.set_page_config(page_title="BLOCK77 주차관리", layout="wide")
st.title("BLOCK77 주차관리")

# 2. 탭 글씨 디자인 (크기 및 굵게)
st.markdown("""
<style>
    button[data-baseweb="tab"] p {
        font-weight: bold !important;
        font-size: 16px !important;
    }
    /* 스트림릿 기본 사이드바 화살표 버튼을 완전히 숨겨버리는 CSS 코드 */
    [data-testid="collapsedControl"] {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

# 3. ⭐️ 사이드바 완전 삭제 및 구글 시트 주소 코드 내장(하드코딩)
sheet_url = "https://docs.google.com/spreadsheets/d/1khi9F-BUQOv2HYgJWIaWLIHhwV15MyHhxSrw_6JtK4E/edit?gid=0#gid=0"

df = None
try:
    match = re.search(r'/d/([a-zA-Z0-9-_]+)', sheet_url)
    if match:
        sheet_id = match.group(1)
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        df = pd.read_csv(csv_url)
except Exception as e:
    st.error(f"데이터 로딩 오류: {e}")

if df is not None and not df.empty:
    df.columns = df.columns.str.strip()
    df = df.dropna(subset=['입차일시'], how='all')
    
    for col in ['주차요금', '현금수입', '카드수입']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(r'[^\d\-.]', '', regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    for col in ['입차일시', '출차일시', '정산일시']:
        if col in df.columns: df[col] = pd.to_datetime(df[col], errors='coerce')
        
    if '정산일시' in df.columns:
        temp_date = df['정산일시'].fillna(df.get('출차일시')).fillna(df.get('입차일시'))
        df['정산월'] = temp_date.dt.strftime('%Y-%m')
        df['정산년도'] = temp_date.dt.strftime('%Y')
        df['순수월'] = temp_date.dt.strftime('%m') 
        df = df.dropna(subset=['정산월']) 
        
    if '출차일시' in df.columns and '입차일시' in df.columns:
        df['주차시간(분)'] = (df['출차일시'] - df['입차일시']).dt.total_seconds() / 60 
        df['주차시간(분)'] = df['주차시간(분)'].fillna(0)
    
    def extract_discounts(row):
        val = str(row.get('요금종별', ''))
        web_discount = 0.0
        free_parking = 0.0
        if '웹할인' in val:
            if '완전무료' in val:
                free_parking = float(row.get('주차요금', 0))
            else:
                match = re.search(r"웹할인\s*\(\s*([\d,]+)", val)
                if match:
                    web_discount = float(match.group(1).replace(',', ''))
        return pd.Series([web_discount, free_parking])

    if '요금종별' in df.columns:
        df[['웹할인', '무료주차']] = df.apply(extract_discounts, axis=1)
    else:
        df['웹할인'] = 0.0; df['무료주차'] = 0.0

    if '현금수입' in df.columns: df.rename(columns={'현금수입': '현금'}, inplace=True)
    if '카드수입' in df.columns: df.rename(columns={'카드수입': '카드'}, inplace=True)

    now = datetime.now()
    current_year = str(now.year)
    current_month = f"{now.month}월"

    year_list = sorted(df['정산년도'].dropna().unique().tolist(), reverse=True) if '정산년도' in df.columns else []
    if current_year not in year_list:
        year_list = [current_year] + year_list
        year_list.sort(reverse=True)
        
    month_list = [f"{i}월" for i in range(1, 13)]

    def get_index(lst, val):
        return lst.index(val) if val in lst else 0

    idx_year = get_index(year_list, current_year)
    idx_month = get_index(month_list, current_month)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["정산", "웹할인", "무료주차", "통 계", "차량조회"])
    
    # ------------------------------------
    # [탭 1] 정산
    # ------------------------------------
    with tab1:
        col_title, col_empty, col_f1, col_f2 = st.columns([5, 2, 1.5, 1.5])
        with col_title:
            st.subheader("정산 요약")
        with col_f1:
            opts1 = ["전체"] + [f"{y}년" for y in year_list]
            idx1 = get_index(opts1, f"{current_year}년")
            s_year_label = st.selectbox("연도 선택", opts1, index=idx1, key="s_year", label_visibility="collapsed")
        with col_f2:
            opts2 = ["전체"] + month_list
            idx2 = get_index(opts2, current_month)
            if s_year_label == "전체":
                st.selectbox("월별 선택", ["비활성"], disabled=True, key="s_month_dis", label_visibility="collapsed")
                s_month_label = "전체"
            else:
                s_month_label = st.selectbox("월별 선택", opts2, index=idx2, key="s_month", label_visibility="collapsed")

        req_cols = ['주차요금', '웹할인', '무료주차', '카드', '현금']
        if all(c in df.columns for c in req_cols) and not df.empty:
            
            # 🚨 인터넷 서버(스트림릿 클라우드) 최신 버전에 맞춘 에러 방지용 안전한 집계 로직
            agg_funcs = {col: 'sum' for col in req_cols}
            agg_funcs['차량번호'] = 'count'
            
            if s_year_label == "전체":
                monthly_summary = df.groupby('정산년도').agg(agg_funcs).reset_index()
                monthly_summary.rename(columns={'정산년도': '기간', '차량번호': '주차대수'}, inplace=True)
                monthly_summary['기간'] = monthly_summary['기간'] + "년"
            else:
                s_year_val = s_year_label.replace("년", "")
                filtered_df = df[df['정산년도'] == s_year_val]
                if s_month_label == "전체":
                    if not filtered_df.empty:
                        monthly_summary = filtered_df.groupby('정산월').agg(agg_funcs).reset_index()
                        monthly_summary.rename(columns={'정산월': '기간', '차량번호': '주차대수'}, inplace=True)
                    else:
                        monthly_summary = pd.DataFrame(columns=['기간', '주차대수'] + req_cols)
                else:
                    m_val = s_month_label.replace("월", "").zfill(2)
                    filtered_df = filtered_df[filtered_df['순수월'] == m_val]
                    if not filtered_df.empty:
                        monthly_summary = filtered_df.groupby('정산월').agg(agg_funcs).reset_index()
                        monthly_summary.rename(columns={'정산월': '기간', '차량번호': '주차대수'}, inplace=True)
                    else:
                        monthly_summary = pd.DataFrame(columns=['기간', '주차대수'] + req_cols)
            
            if not monthly_summary.empty:
                display_cols = ['기간', '주차대수', '주차요금', '웹할인', '무료주차', '카드', '현금']
                final_table = monthly_summary[display_cols].sort_values(by='기간', ascending=False)
                
                def highlight_total(s):
                    return ['background-color: #fff3cd; color: #856404; font-weight: bold;' if col == '주차요금' else '' for col in s.index]
                
                st.dataframe(
                    final_table.style.apply(highlight_total, axis=1).format({
                        '주차대수': '{:,.0f}대', '주차요금': '{:,.0f}원', '웹할인': '{:,.0f}원', 
                        '무료주차': '{:,.0f}원', '카드': '{:,.0f}원', '현금': '{:,.0f}원'
                    }),
                    hide_index=True, use_container_width=True
                )
            else:
                st.info("해당 기간의 정산 데이터가 없습니다.")

    # ------------------------------------
    # [탭 2] 웹할인 
    # ------------------------------------
    with tab2:
        col_title2, col_empty2, col_f3, col_f4 = st.columns([5, 2, 1.5, 1.5])
        with col_title2:
            st.subheader("웹할인 현황")
        with col_f3:
            w_year = st.selectbox("연도 선택", year_list, index=idx_year, key="w_year", label_visibility="collapsed")
        with col_f4:
            opts2_w = ["전체"] + month_list
            idx2_w = get_index(opts2_w, current_month)
            w_month = st.selectbox("월별 선택", opts2_w, index=idx2_w, key="w_month", label_visibility="collapsed")

        if w_year:
            w_filtered_df = df[df['정산년도'] == w_year]
            if w_month != "전체":
                w_filtered_df = w_filtered_df[w_filtered_df['순수월'] == w_month.replace("월", "").zfill(2)]
            
            sub_tab1, sub_tab2 = st.tabs(["사용내역", "구매내역"])
            with sub_tab1:
                if '요금종별' in df.columns:
                    web_cars = w_filtered_df[(w_filtered_df['요금종별'].astype(str).str.contains('웹할인')) & (~w_filtered_df['요금종별'].astype(str).str.contains('완전무료'))]
                    total_web = web_cars['웹할인'].sum()
                    st.markdown(f"<div style='font-size: 16px; font-weight: normal; color: #1E90FF; margin-bottom: 10px;'>선택기간 사용내역 총액: {total_web:,.0f}원 (총 {len(web_cars)}건)</div>", unsafe_allow_html=True)
                    cols_w = ['차량번호', '입차일시', '출차일시', '주차요금', '웹할인', '요금종별']
                    cols_w = [c for c in cols_w if c in web_cars.columns]
                    st.dataframe(web_cars[cols_w].sort_values('입차일시', ascending=False).style.format({'주차요금': '{:,.0f}원', '웹할인': '{:,.0f}원'}), hide_index=True, use_container_width=True)

            with sub_tab2:
                st.info("현재 구매내역 데이터가 비어 있습니다.")

    # ------------------------------------
    # [탭 3] 무료주차 
    # ------------------------------------
    with tab3:
        col_title3, col_empty3, col_f5, col_f6 = st.columns([5, 2, 1.5, 1.5])
        with col_title3:
            st.subheader("무료주차 및 강제출차 현황")
        with col_f5:
            f_year = st.selectbox("연도 선택", year_list, index=idx_year, key="f_year", label_visibility="collapsed")
        with col_f6:
            opts2_f = ["전체"] + month_list
            idx2_f = get_index(opts2_f, current_month)
            f_month = st.selectbox("월별 선택", opts2_f, index=idx2_f, key="f_month", label_visibility="collapsed")

        if f_year:
            f_filtered_df = df[df['정산년도'] == f_year]
            if f_month != "전체":
                f_filtered_df = f_filtered_df[f_filtered_df['순수월'] == f_month.replace("월", "").zfill(2)]
            
            sub_tab3, sub_tab4 = st.tabs(["무료주차", "강제출차"])
            with sub_tab3:
                if '요금종별' in df.columns:
                    free_cars = f_filtered_df[f_filtered_df['요금종별'].astype(str).str.contains('완전무료', na=False)]
                    total_free = free_cars['무료주차'].sum()
                    st.markdown(f"<div style='font-size: 16px; font-weight: normal; color: #FF4500; margin-bottom: 10px;'>선택기간 무료주차 총액: {total_free:,.0f}원 (총 {len(free_cars)}건)</div>", unsafe_allow_html=True)
                    cols_f = ['차량번호', '입차일시', '출차일시', '주차요금', '무료주차', '요금종별']
                    cols_f = [c for c in cols_f if c in free_cars.columns]
                    st.dataframe(free_cars[cols_f].sort_values('입차일시', ascending=False).style.format({'주차요금': '{:,.0f}원', '무료주차': '{:,.0f}원'}), hide_index=True, use_container_width=True)

            with sub_tab4:
                mask = f_filtered_df.astype(str).apply(lambda x: x.str.contains('강제출차', na=False)).any(axis=1)
                forced_exit = f_filtered_df[mask]
                st.markdown(f"<div style='font-size: 16px; font-weight: normal; margin-bottom: 10px;'>선택기간 강제출차 총 {len(forced_exit)}건의 기록이 있습니다.</div>", unsafe_allow_html=True)
                if not forced_exit.empty:
                    cols3 = ['차량번호', '입차일시', '출차일시', '주차요금', '요금종별', '메모']
                    cols3 = [c for c in cols3 if c in df.columns]
                    st.dataframe(forced_exit[cols3].sort_values('입차일시', ascending=False), hide_index=True, use_container_width=True)

    # ------------------------------------
    # [탭 4] 통 계
    # ------------------------------------
    with tab4:
        st.subheader("📊 월별 주차대수 (최근 1년)")
        if not df.empty and '정산월' in df.columns:
            try:
                valid_months = []
                now_date = datetime.now()
                for i in range(12):
                    valid_months.append((now_date - pd.DateOffset(months=i)).strftime('%Y-%m'))
                
                monthly_trend = df[df['정산월'].isin(valid_months)].groupby('정산월').size().reset_index(name='차량수')
                
                if not monthly_trend.empty:
                    monthly_trend['주차대수'] = monthly_trend['차량수'].astype(str) + "대"
                    
                    base_m = alt.Chart(monthly_trend).encode(
                        x=alt.X('정산월', sort=None, axis=alt.Axis(labelAngle=0, title=None)),
                        tooltip=alt.value(None)
                    )
                    line_m = base_m.mark_line(color='#ff7f0e', strokeWidth=3, point=True).encode(y=alt.Y('차량수', title='월별 차량대수 (대)'))
                    text_m = base_m.mark_text(align='center', baseline='bottom', dy=-15, fontSize=12, fontWeight='bold', color='#333').encode(y='차량수', text='주차대수')
                    
                    st.altair_chart((line_m + text_m).properties(height=300), use_container_width=True)
                else:
                    st.info("최근 1년간의 데이터가 없습니다.")
            except:
                st.info("그래프를 그릴 수 없습니다.")
                
        st.divider()

        col_title4, col_empty4, col_f7, col_f8 = st.columns([5, 2, 1.5, 1.5])
        with col_title4:
            st.subheader("📈 시간대별 주차대수")
        with col_f7:
            t4_y = st.selectbox("연도 선택", year_list, index=idx_year, key="t4_y", label_visibility="collapsed")
        with col_f8:
            opts_t2 = ["전체"] + month_list
            idx_t2 = get_index(opts_t2, current_month)
            t4_m = st.selectbox("월별 선택", opts_t2, index=idx_t2, key="t4_m", label_visibility="collapsed")

        if t4_y:
            filtered_stat_df = df[df['정산년도'] == t4_y]
            if t4_m == "전체":
                period_str = f"{t4_y}년 전체"
            else:
                filtered_stat_df = filtered_stat_df[filtered_stat_df['순수월'] == t4_m.replace("월", "").zfill(2)]
                period_str = f"{t4_y}년 {t4_m}"
                    
            if '입차일시' in filtered_stat_df.columns and '출차일시' in filtered_stat_df.columns and not filtered_stat_df.empty:
                hour_counts = {h: 0 for h in range(24)}
                for _, row in filtered_stat_df.iterrows():
                    if pd.notna(row['입차일시']) and pd.notna(row['출차일시']):
                        try:
                            in_h = row['입차일시'].hour
                            out_h = row['출차일시'].hour
                            if row['입차일시'].date() == row['출차일시'].date():
                                if in_h <= out_h:
                                    for h in range(in_h, out_h + 1): hour_counts[h] += 1
                            else:
                                for h in range(in_h, 24): hour_counts[h] += 1
                                for h in range(0, out_h + 1): hour_counts[h] += 1
                        except: pass
                
                days_count = filtered_stat_df['입차일시'].dt.date.nunique()
                if days_count == 0: days_count = 1
                
                chart_data = pd.DataFrame({
                    "시간대": [f"{h:02d}시" for h in range(24)],
                    "차량수": [int(round(hour_counts[h] / days_count, 0)) for h in range(24)]
                })
                chart_data['주차대수'] = chart_data['차량수'].astype(str) + "대"
                
                base = alt.Chart(chart_data).encode(
                    x=alt.X('시간대', sort=None, axis=alt.Axis(labelAngle=0, title=None)),
                    tooltip=alt.value(None)
                )
                line = base.mark_line(color='#1f77b4', strokeWidth=3, point=True).encode(y=alt.Y('차량수', title='하루 평균 차량대수 (대)'))
                text = base.mark_text(align='center', baseline='bottom', dy=-15, fontSize=12, fontWeight='bold', color='#333333').encode(y='차량수', text='주차대수')
                
                st.altair_chart((line + text).properties(height=350), use_container_width=True)
                st.caption(f"선택한 기간({period_str}) 동안 각 시간대(0시~23시)에 주차장에 머문 하루 평균 차량 대수입니다. (총 {days_count}일 기준)")
            else:
                st.info("데이터가 부족하여 그래프를 그릴 수 없습니다.")

    # ------------------------------------
    # [탭 5] 차량조회
    # ------------------------------------
    with tab5:
        st.subheader("차량 번호 검색")
        search_car = st.text_input("차량번호 4자리를 입력하세요")
        if search_car and '차량번호' in df.columns:
            result = df[df['차량번호'].astype(str).str.contains(search_car, na=False)]
            if not result.empty:
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.write("월별 누적 주차시간")
                    monthly_time = result.groupby('정산월')['주차시간(분)'].sum().reset_index()
                    monthly_time['총 주차시간'] = monthly_time['주차시간(분)'].apply(lambda x: f"{int(x//60)}시간 {int(x%60)}분")
                    st.dataframe(monthly_time[['정산월', '총 주차시간']], hide_index=True, use_container_width=True)
                with col2:
                    st.write("상세 입출차 내역")
                    cols = ['차량번호', '입차일시', '출차일시', '주차요금', '요금종별']
                    cols = [c for c in cols if c in result.columns]
                    st.dataframe(result[cols].sort_values('입차일시', ascending=False), hide_index=True, use_container_width=True)
            else:
                st.warning("검색된 차량이 없습니다.")
else:
    st.info("구글 시트에서 데이터를 불러올 수 없습니다.")
