import streamlit as st
import pandas as pd

# 페이지 설정
st.set_page_config(page_title="포케팜 매출 계산기", page_icon="💰", layout="wide")

# 제목 변경 적용
st.title("💰 포케팜 매출 신고 계산기")
st.caption("made by 윤")

uploaded_file = st.file_uploader("구글 플레이 CSV 파일을 선택하세요", type=['csv'])

if uploaded_file is not None:
    try:
        # 인코딩 처리
        try:
            df = pd.read_csv(uploaded_file, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(uploaded_file, encoding='cp949')

        # 컬럼명 설정
        col_date = 'Transaction Date'                 # 날짜 컬럼
        col_net_amt = 'Amount (Merchant Currency)'   # 순매출 기준
        col_buyer_amt = 'Amount (Buyer Currency)'     # 현지 결제액
        col_buyer_cur = 'Buyer Currency'              # 통화 코드
        col_product_title = 'Product Title'           # 상품명

        # 1. 날짜 및 월 추출 (신규 기능)
        if col_date in df.columns:
            # 날짜 형식으로 변환 (에러는 무시)
            df[col_date] = pd.to_datetime(df[col_date], errors='coerce')
            # 'O월' 형식으로 고유값 추출
            months = df[col_date].dt.strftime('%m월').dropna().unique()
            months_str = ", ".join(sorted(months))
            st.success(f"📅 데이터 포함 기간: **{months_str}**")
        
        required_cols = [col_net_amt, col_buyer_amt, col_buyer_cur]
        if all(col in df.columns for col in required_cols):
            # 데이터 전처리
            for col in [col_net_amt, col_buyer_amt]:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            
            # 2. 상단 요약
            total_net_krw = df[col_net_amt].sum()
            total_gross_krw = total_net_krw * 1.4285
            
            st.divider()
            c1, c2 = st.columns(2)
            c1.metric(label="🛒 총 매출액 (Gross Sales)", value=f"{total_gross_krw:,.0f} 원")
            c2.metric(label="📈 순 매출액 (Net Sales)", value=f"{total_net_krw:,.0f} 원")

            # 3. 통화별 상세 분석 표
            st.subheader("🌐 통화별 매출 상세")

            stats = df.groupby(col_buyer_cur).agg({
                col_net_amt: 'sum',
                col_buyer_amt: 'sum',
                col_buyer_cur: 'count'
            }).rename(columns={col_buyer_cur: '거래 건수'})

            stats['총 매출 (Gross 원화)'] = stats[col_net_amt] * 1.4285
            
            def get_currency_symbol(currency_code):
                symbols = {
                    'USD': '$', 'KRW': '₩', 'JPY': '￥', 'EUR': '€', 
                    'GBP': '£', 'CNY': '¥', 'TWD': 'NT$', 'HKD': 'HK$'
                }
                return symbols.get(currency_code, currency_code + " ")

            final_df = stats.reset_index()
            final_df['현지통화결제 합계'] = final_df.apply(
                lambda x: f"{get_currency_symbol(x[col_buyer_cur])} {x[col_buyer_amt]:,.0f}", axis=1
            )
            
            # 컬럼 순서 재배치
            final_df = final_df[['총 매출 (Gross 원화)', col_net_amt, '현지통화결제 합계', '거래 건수', col_buyer_cur]]
            final_df.columns = ['총 매출 (Gross)', '순 매출 (Net)', '현지통화결제 합계', '거래 건수', '통화 단위']

            # 현지 결제액 기준 내림차순 정렬
            final_df = final_df.iloc[stats[col_buyer_amt].argsort()[::-1].values]

            # 표 출력 (우측 정렬)
            st.dataframe(
                final_df.style.format({
                    '총 매출 (Gross)': "{:,.0f} 원",
                    '순 매출 (Net)': "{:,.0f} 원",
                    '거래 건수': "{:,} 건"
                }).set_properties(**{'text-align': 'right'}),
                use_container_width=True,
                hide_index=True
            )

            # 4. 상품별 판매 현황
            st.write("---")
            with st.expander("📦 상품별 판매 상세 현황 확인"):
                if col_product_title in df.columns:
                    item_stats = df.groupby(col_product_title).agg({
                        col_net_amt: 'sum',
                        col_product_title: 'count'
                    }).rename(columns={col_net_amt: '순 매출 합계(원)', col_product_title: '판매 건수'})
                    
                    item_stats['총 매출 합계(원)'] = item_stats['순 매출 합계(원)'] * 1.4285
                    item_stats = item_stats[['총 매출 합계(원)', '순 매출 합계(원)', '판매 건수']]
                    item_stats = item_stats.sort_values(by='총 매출 합계(원)', ascending=False).reset_index()
                    
                    st.dataframe(
                        item_stats.style.format({
                            '총 매출 합계(원)': "{:,.0f} 원",
                            '순 매출 합계(원)': "{:,.0f} 원",
                            '판매 건수': "{:,} 건"
                        }).set_properties(**{'text-align': 'right'}),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.warning(f"CSV에 '{col_product_title}' 컬럼이 없습니다.")

            with st.expander("📄 데이터 원본 확인"):
                st.write(df)
        else:
            st.error("필수 컬럼이 부족합니다.")
    except Exception as e:
        st.error(f"오류 발생: {e}")