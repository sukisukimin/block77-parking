import streamlit as st
import pandas as pd
import re
import altair as alt
from datetime import datetime

# 1. 앱 기본 설정
st.set_page_config(page_title="BLOCK77 주차관리", layout="wide")
st.title("BLOCK77 주차관리")

# 2. 탭 글씨 디자인 및 사이드바 숨김
st.markdown("""
<style>
    button[data-baseweb="tab"] p {
        font-weight: bold !important;
        font-size: 16px !important;
    }
    [data-testid="collapsedControl"] {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

# 3. ⭐️ 데이터 로딩 (구글 시트 엑셀을 통째로 가져와서 2개의 시트로 자동 분류합니다)
@st.cache_data(ttl=60)
def load_all_data(url):
    match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
    if match:
        sheet_id = match.group(1)
        # 엑셀 파일 형식으로 전체 시트를 한 번에 다운로드
        xlsx_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
        try:
            dict_df = pd.read_excel(xlsx_url, sheet_name=None, engine='openpyxl')
            sheet_names = list(dict_df.keys())
            
            df_main = dict_df[sheet_names[0]] # 무조건 첫 번째 시트 (입출차내역)
            df_pur = None
            
            # 탭 이름에 '구매내역'이 포함된 시트를 찾아 자동 연결!
            for name in sheet_names:
                if '구매내역' in name:
                    df_pur = dict_df[name]
                    break
                
            return df_main, df_pur
        except Exception as e:
            return None, None
    return None, None

sheet_url = "https://docs.google.com/spreadsheets/d/1khi9F-BUQOv2HYgJWIaWLIHhwV15MyHhxSrw_6JtK4E/edit?gid=0#gid=0"

df = None
df_pur = None
try:
    df, df_pur = load_all_data(sheet_url)
except Exception as e:
    st.error(f"데이터 로딩 오류: {e}")

if df is not None and not df.empty:
    df.columns = df.columns.str.strip()
    df = df.dropna(subset=['입차일시'], how='all')
    
    if '메모' not in df.columns: df['메모'] = ""
    else: df['메모'] = df['메모'].fillna("")
    
    for col in ['주차요금', '현금수입', '카드수입']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(r'[^\d\-.]', '', regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    for col in ['입차일시', '출차일시', '정산일시']:
        if col in df.columns: df[col] = pd.to_datetime(df[col], errors='coerce')
        
    if '입차일시' in df.columns:
        temp_date = df['입차일시'].fillna(df.get('출차일시')).fillna(df.get('정산일시'))
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

    year_list = sorted(df['정산년도'].dropna().unique().tolist(), reverse=True) if '정산년도' in df.columns else []
    
    if year_list:
        valid_df = df[df['요금종별'].astype(str).str.contains('웹할인|완전무료', na=False)] if '요금종별' in df.columns else df
        if valid_df.empty:
            valid_df = df
        recent_year = sorted(valid_df['정산년도'].dropna().unique().tolist(), reverse=True)[0]
        recent_month_val = valid_df[valid_df['정산년도'] == recent_year]['순수월'].dropna().max()
        recent_month = f"{int(recent_month_val)}월" if pd.notna(recent_month_val) else "1월"
    else:
        recent_year = str(datetime.now().year)
        recent_month = f"{datetime.now().month}월"
        
    month_list = [f"{i}월" for i in range(1, 13)]
    month_list_with_all = ["전체"] + month_list

    def get_index(lst, val):
        return lst.index(val) if val in lst else 0

    idx_year = get_index(year_list, f"{recent_year}년") if year_list else 0
    idx_month = get_index(month_list, recent_month)
    idx_month_all = get_index(month_list_with_all, recent_month)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["정산", "웹할인", "무료주차", "통 계", "차량조회"])
    
    # ------------------------------------
    # [탭 1] 정산
    # ------------------------------------
    with tab1:
        col_title, col_empty, col_f1 = st.columns([6.5, 2, 1.5])
        with col_title:
            st.subheader("정산 요약")
        with col_f1:
            opts1 = [f"{y}년" for y in year_list]
            s_year_label = st.selectbox("연도 선택", opts1, index=idx_year, key="s_year", label_visibility="collapsed") if opts1 else None

        if s_year_label:
            req_cols = ['주차요금', '웹할인', '무료주차', '카드']
            if all(c in df.columns for c in req_cols) and not df.empty:
                agg_funcs = {col: 'sum' for col in req_cols}
                agg_funcs['차량번호'] = 'count'
                
                s_year_val = s_year_label.replace("년", "")
                filtered_df = df[df['정산년도'] == s_year_val]
                
                if not filtered_df.empty:
                    monthly_summary = filtered_df.groupby('정산월').agg(agg_funcs).reset_index()
                    monthly_summary.rename(columns={'정산월': '기간', '차량번호': '주차대수'}, inplace=True)
                else:
                    monthly_summary = pd.DataFrame(columns=['기간', '주차대수'] + req_cols)
                
                if not monthly_summary.empty:
                    display_cols = ['기간', '주차대수', '주차요금', '웹할인', '무료주차', '카드']
                    final_table = monthly_summary[display_cols].sort_values(by='기간', ascending=False)
                    
                    def highlight_total(s):
                        return ['background-color: #fff3cd; color: #856404; font-weight: bold;' if col == '주차요금' else '' for col in s.index]
                    
                    st.dataframe(
                        final_table.style.apply(highlight_total, axis=1).format({
                            '주차대수': '{:,.0f}대', '주차요금': '{:,.0f}원', '웹할인': '{:,.0f}원', 
                            '무료주차': '{:,.0f}원', '카드': '{:,.0f}원'
                        }),
                        hide_index=True, use_container_width=True
                    )
                else:
                    st.info("해당 연도의 정산 데이터가 없습니다.")

    # ------------------------------------
    # [탭 2] 웹할인 (🚨 결제후잔여량으로 수정 완료)
    # ------------------------------------
    with tab2:
        col_title2, col_empty2, col_f3, col_f4 = st.columns([5, 2, 1.5, 1.5])
        with col_title2:
            st.subheader("웹할인 현황")
        with col_f3:
            opts_y = [f"{y}년" for y in year_list]
            w_year_label = st.selectbox("연도 선택", opts_y, index=idx_year, key="w_year", label_visibility="collapsed") if opts_y else None
        with col_f4:
            w_month = st.selectbox("월별 선택", month_list, index=idx_month, key="w_month", label_visibility="collapsed")

        if w_year_label and w_month:
            w_year = w_year_label.replace("년", "")
            w_month_num = w_month.replace("월", "").zfill(2)
            target_month = f"{w_year}-{w_month_num}"
            
            w_filtered_df = df[df['정산월'] == target_month]
            
            sub_tab1, sub_tab2 = st.tabs(["사용내역", "구매내역"])
            
            # [사용내역 탭]
            with sub_tab1:
                if '요금종별' in df.columns:
                    web_cars = w_filtered_df[(w_filtered_df['요금종별'].astype(str).str.contains('웹할인')) & (~w_filtered_df['요금종별'].astype(str).str.contains('완전무료'))]
                    total_web = web_cars['웹할인'].sum()
                    st.markdown(f"<div style='font-size: 16px; font-weight: normal; color: #1E90FF; margin-bottom: 10px;'>선택기간 사용내역 총액: {total_web:,.0f}원 (총 {len(web_cars)}건)</div>", unsafe_allow_html=True)
                    
                    cols_w = ['차량번호', '입차일시', '출차일시', '주차요금', '웹할인', '요금종별', '메모']
                    cols_w = [c for c in cols_w if c in df.columns]
                    st.dataframe(web_cars[cols_w].sort_values('입차일시', ascending=False).style.format({'주차요금': '{:,.0f}원', '웹할인': '{:,.0f}원'}), hide_index=True, use_container_width=True)

            # [구매내역 탭]
            with sub_tab2:
                if df_pur is not None and not df_pur.empty:
                    try:
                        df_pur.columns = df_pur.columns.str.strip()
                        
                        # 금액 관련 텍스트 정리 (콤마 등 제거)
                        for col in ['결제금액', '결제후잔여량']:
                            if col in df_pur.columns:
                                df_pur[col] = df_pur[col].astype(str).str.replace(r'[^\d\-.]', '', regex=True)
                                df_pur[col] = pd.to_numeric(df_pur[col], errors='coerce').fillna(0)
                        
                        if '결제일자' in df_pur.columns:
                            df_pur['결제일자'] = pd.to_datetime(df_pur['결제일자'], errors='coerce')
                            # 날짜가 없는 빈칸 무시
                            df_pur = df_pur.dropna(subset=['결제일자']) 
                            
                            # 우측 상단 드롭박스에서 선택한 연/월과 일치하는 데이터만 가져오기
                            df_pur_filtered = df_pur[df_pur['결제일자'].dt.strftime('%Y-%m') == target_month]
                            
                            if not df_pur_filtered.empty and '이름' in df_pur_filtered.columns:
                                # 1) 업체(이름)별로 '해당 월 결제금액' 모두 합산
                                sum_pur = df_pur_filtered.groupby('이름')['결제금액'].sum().reset_index()
                                
                                # 2) 업체(이름)별로 '해당 월 가장 최신 결제일자' 기준의 결제후잔여량 가져오기
                                last_bal_df = df_pur_filtered.sort_values('결제일자').groupby('이름')['결제후잔여량'].last().reset_index()
                                
                                # 병합하여 하나의 표로 만들기
                                final_pur_table = pd.merge(sum_pur, last_bal_df, on='이름', how='left')
                                final_pur_table = final_pur_table[final_pur_table['결제금액'] > 0]
                                final_pur_table.rename(columns={'이름': '업체명', '결제금액': f'{w_month} 총 결제금액', '결제후잔여량': '결제후 잔여량'}, inplace=True)
                                
                                total_pay = final_pur_table[f'{w_month} 총 결제금액'].sum()
                                st.markdown(f"<div style='font-size: 16px; font-weight: normal; color: #2E8B57; margin-bottom: 10px;'>선택기간 구매 결제 총액: {total_pay:,.0f}원</div>", unsafe_allow_html=True)
                                
                                st.dataframe(
                                    final_pur_table.sort_values(by=f'{w_month} 총 결제금액', ascending=False).style.format({
                                        f'{w_month} 총 결제금액': '{:,.0f}원', 
                                        '결제후 잔여량': '{:,.0f}'
                                    }), 
                                    hide_index=True, use_container_width=True
                                )
                            else:
                                st.info(f"{w_year}년 {w_month}의 구매내역 데이터가 없습니다.")
                        else:
                            st.error("구매내역 시트에 '결제일자' 열이 없습니다. 구글시트 항목명을 확인해주세요.")
                    except Exception as e:
                        st.error(f"구매내역 데이터 처리 중 오류 발생: {e}")
                else:
                    st.info("구글 시트의 '웹할인 구매내역' 시트가 비어있거나 제목이 다릅니다.")

    # ------------------------------------
    # [탭 3] 무료주차 (🚨 오타 수정 완료: idx_y -> idx_year)
    # ------------------------------------
    with tab3:
        col_title3, col_empty3, col_f5, col_f6 = st.columns([5, 2, 1.5, 1.5])
        with col_title3:
            st.subheader("무료주차 및 강제출차 현황")
        with col_f5:
            f_year_label = st.selectbox("연도 선택", opts_y, index=idx_year, key="f_year", label_visibility="collapsed") if opts_y else None
        with col_f6:
            f_month = st.selectbox("월별 선택", month_list, index=idx_month, key="f_month", label_visibility="collapsed")

        if f_year_label and f_month:
            f_year = f_year_label.replace("년", "")
            f_filtered_df = df[df['정산년도'] == f_year]
            f_filtered_df = f_filtered_df[f_filtered_df['순수월'] == f_month.replace("월", "").zfill(2)]
            
            sub_tab3, sub_tab4 = st.tabs(["무료주차", "강제출차"])
            
            with sub_tab3:
                if '요금종별' in df.columns:
                    free_cars = f_filtered_df[f_filtered_df['요금종별'].astype(str).str.contains('완전무료', na=False)]
                    total_free = free_cars['무료주차'].sum()
                    st.markdown(f"<div style='font-size: 16px; font-weight: normal; color: #FF4500; margin-bottom: 10px;'>선택기간 무료주차 총액: {total_free:,.0f}원 (총 {len(free_cars)}건)</div>", unsafe_allow_html=True)
                    
                    cols_f = ['차량번호', '입차일시', '출차일시', '주차요금', '무료주차', '요금종별', '메모']
                    cols_f = [c for c in cols_f if c in df.columns]
                    st.dataframe(free_cars[cols_f].sort_values('입차일시', ascending=False).style.format({'주차요금': '{:,.0f}원', '무료주차': '{:,.0f}원'}), hide_index=True, use_container_width=True)

            with sub_tab4:
                mask = f_filtered_df.astype(str).apply(lambda x: x.str.contains('강제출차', na=False)).any(axis=1)
                forced_exit = f_filtered_df[mask]
                st.markdown(f"<div style='font-size: 16px; font-weight: normal; margin-bottom: 10px;'>선택기간 강제출차 총 {len(forced_exit)}건의 기록이 있습니다.</div>", unsafe_allow_html=True)
                if not forced_exit.empty:
                    cols3 = ['차량번호', '입차일시', '출차일시', '주차요금', '요금종별', '메모']
                    cols3 = [c for c in cols3 if c in df.columns]
                    st.dataframe(forced_exit[cols3].sort_values('입차일시', ascending=False).style.format({'주차요금': '{:,.0f}원'}), hide_index=True, use_container_width=True)

    # ------------------------------------
    # [탭 4] 통 계 (🚨 오타 수정 완료: idx_y -> idx_year)
    # ------------------------------------
    with tab4:
        col_t_title, col_t_empty, col_t_f1 = st.columns([6.5, 2, 1.5])
        with col_t_title:
            st.subheader("📊 월별 주차대수")
        with col_t_f1:
            stat_m_year_label = st.selectbox("연도 선택", opts_y, index=idx_year, key="stat_m_year", label_visibility="collapsed") if opts_y else None
            
        if stat_m_year_label and not df.empty and '정산년도' in df.columns:
            try:
                stat_m_year = stat_m_year_label.replace("년", "")
                m_filtered_df = df[df['정산년도'] == stat_m_year]
                
                monthly_trend = m_filtered_df.groupby('정산월').size().reset_index(name='차량수')
                
                if not monthly_trend.empty:
                    monthly_trend = monthly_trend.sort_values(by='정산월')
                    monthly_trend['주차대수'] = monthly_trend['차량수'].astype(str) + "대"
                    
                    base_m = alt.Chart(monthly_trend).encode(
                        x=alt.X('정산월', sort=None, axis=alt.Axis(labelAngle=0, title=None)),
                        tooltip=alt.value(None)
                    )
                    line_m = base_m.mark_line(color='#ff7f0e', strokeWidth=3, point=True).encode(y=alt.Y('차량수', title='월별 차량대수 (대)'))
                    text_m = base_m.mark_text(align='center', baseline='bottom', dy=-15, fontSize=12, fontWeight='bold', color='#333').encode(y='차량수', text='주차대수')
                    
                    st.altair_chart((line_m + text_m).properties(height=300), use_container_width=True)
                else:
                    st.info(f"{stat_m_year_label}의 데이터가 없습니다.")
            except:
                st.info("그래프를 그릴 수 없습니다.")
                
        st.divider()

        col_title4, col_empty4, col_f7, col_f8 = st.columns([5, 2, 1.5, 1.5])
        with col_title4:
            st.subheader("📈 시간대별 주차대수")
        with col_f7:
            t4_y_label = st.selectbox("연도 선택", opts_y, index=idx_year, key="t4_y", label_visibility="collapsed") if opts_y else None
        with col_f8:
            t4_m = st.selectbox("월별 선택", month_list_with_all, index=idx_month_all, key="t4_m", label_visibility="collapsed")

        if t4_y_label and t4_m:
            t4_y = t4_y_label.replace("년", "")
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
                    cols = ['차량번호', '입차일시', '출차일시', '주차요금', '요금종별', '메모']
                    cols = [c for c in cols if c in result.columns]
                    st.dataframe(result[cols].sort_values('입차일시', ascending=False), hide_index=True, use_container_width=True)
            else:
                st.warning("검색된 차량이 없습니다.")
else:
    st.info("구글 시트 데이터를 불러올 수 없습니다.")
