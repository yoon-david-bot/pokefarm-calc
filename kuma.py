import streamlit as st
import pandas as pd
import io

# 1. 페이지 설정
st.set_page_config(page_title="포케팜 매출 계산기", page_icon="💰", layout="wide")

# 제목 및 캡션
st.title("💰 포케팜 매출 신고 계산기")
st.caption("made by 윤형식 🐻")

# 2. 사이드바 - 플랫폼 바로 선택 (라디오 버튼)
st.sidebar.header("플랫폼 선택")
platform = st.sidebar.radio(
    "계산할 플랫폼을 클릭하세요", 
    ["Google Play", "Apple (App Store)"],
    index=0
)

# 공통 숫자 정제 함수
def to_numeric_clean(series):
    return pd.to_numeric(series.astype(str).str.replace(',', ''), errors='coerce').fillna(0)

if platform == "Google Play":
    # --- [구글 플레이 섹션: 기존 로직 100% 유지] ---
    uploaded_file = st.file_uploader("구글 플레이 CSV 파일을 선택하세요", type=['csv'])

    if uploaded_file is not None:
        try:
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(uploaded_file, encoding='cp949')

            col_date = 'Transaction Date'
            col_net_amt = 'Amount (Merchant Currency)'
            col_buyer_amt = 'Amount (Buyer Currency)'
            col_buyer_cur = 'Buyer Currency'
            col_product_title = 'Product Title'

            if col_date in df.columns:
                df[col_date] = pd.to_datetime(df[col_date], errors='coerce')
                months = df[col_date].dt.strftime('%m월').dropna().unique()
                months_str = ", ".join(sorted(months))
                st.success(f"📅 데이터 포함 기간: **{months_str}**")

            required_cols = [col_net_amt, col_buyer_amt, col_buyer_cur]
            if all(col in df.columns for col in required_cols):
                df[col_net_amt] = to_numeric_clean(df[col_net_amt])
                df[col_buyer_amt] = to_numeric_clean(df[col_buyer_amt])

                total_net_krw = df[col_net_amt].sum()
                total_gross_krw = total_net_krw * 1.4285

                st.divider()
                c1, c2 = st.columns(2)
                c1.metric(label="🛒 총 매출액 (Gross Sales)", value=f"{total_gross_krw:,.0f} 원")
                c2.metric(label="📈 순 매출액 (Net Sales)", value=f"{total_net_krw:,.0f} 원")

                st.subheader("🌐 통화별 매출 상세")
                stats = df.groupby(col_buyer_cur).agg({
                    col_net_amt: 'sum',
                    col_buyer_amt: 'sum',
                    col_buyer_cur: 'count'
                }).rename(columns={col_buyer_cur: '거래 건수'})

                stats['총 매출 (Gross 원화)'] = stats[col_net_amt] * 1.4285

                def get_currency_symbol(currency_code):
                    symbols = {'USD': '$', 'KRW': '₩', 'JPY': '￥', 'EUR': '€', 'GBP': '£', 'CNY': '¥', 'TWD': 'NT$', 'HKD': 'HK$'}
                    return symbols.get(currency_code, currency_code + " ")

                final_df = stats.reset_index()
                final_df['현지통화결제 합계'] = final_df.apply(
                    lambda x: f"{get_currency_symbol(x[col_buyer_cur])} {x[col_buyer_amt]:,.0f}", axis=1
                )
                final_df = final_df[['총 매출 (Gross 원화)', col_net_amt, '현지통화결제 합계', '거래 건수', col_buyer_cur]]
                final_df.columns = ['총 매출 (Gross)', '순 매출 (Net)', '현지통화결제 합계', '거래 건수', '통화 단위']
                final_df = final_df.iloc[stats[col_buyer_amt].argsort()[::-1].values]

                st.dataframe(
                    final_df.style.format({'총 매출 (Gross)': "{:,.0f} 원", '순 매출 (Net)': "{:,.0f} 원", '거래 건수': "{:,} 건"}).set_properties(**{'text-align': 'right'}),
                    use_container_width=True, hide_index=True
                )

                with st.expander("📦 상품별 판매 상세 현황 확인"):
                    if col_product_title in df.columns:
                        item_stats = df.groupby(col_product_title).agg({col_net_amt: 'sum', col_product_title: 'count'}).rename(columns={col_net_amt: '순 매출 합계(원)', col_product_title: '판매 건수'})
                        item_stats['총 매출 합계(원)'] = item_stats['순 매출 합계(원)'] * 1.4285
                        item_stats = item_stats[['총 매출 합계(원)', '순 매출 합계(원)', '판매 건수']].sort_values(by='총 매출 합계(원)', ascending=False).reset_index()
                        st.dataframe(item_stats.style.format({'총 매출 합계(원)': "{:,.0f} 원", '순 매출 합계(원)': "{:,.0f} 원", '판매 건수': "{:,} 건"}).set_properties(**{'text-align': 'right'}), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"구글 데이터 오류: {e}")

else:
    # --- [애플 앱스토어 섹션: 정산일 기준 & 화폐별 요약] ---
    uploaded_file = st.file_uploader("애플 리포트(CSV 형식)를 선택하세요", type=['csv'])

    if uploaded_file is not None:
        try:
            raw_bytes = uploaded_file.read()
            raw_text = raw_bytes.decode('utf-8')
            lines = raw_text.splitlines()

            filtered_lines = []
            header_row_index = 0
            for i, line in enumerate(lines):
                if 'SKU' in line and ('Transaction Date' in line or 'Settlement Date' in line):
                    header_row_index = i
                if 'Country Of Sale' in line and 'Partner Share Currency' in line:
                    break
                filtered_lines.append(line)

            df = pd.read_csv(io.StringIO("\n".join(filtered_lines)), skiprows=header_row_index)

            # 1. 기간 표시 (정산일 기준)
            col_date_apple = 'Settlement Date' 
            if col_date_apple in df.columns:
                df[col_date_apple] = pd.to_datetime(df[col_date_apple], errors='coerce')
                apple_months = df[col_date_apple].dt.strftime('%m월').dropna().unique()
                st.success(f"📅 데이터 포함 기간 (정산일 기준): **{', '.join(sorted(apple_months))}**")

            # 수치 데이터 전처리
            num_cols = ['Customer Price', 'Extended Partner Share', 'Quantity', 'Partner Share']
            for col in num_cols:
                if col in df.columns:
                    df[col] = to_numeric_clean(df[col])

            # 통화 매핑 및 컬럼 추가
            cur_map = {'JP': 'JPY', 'KR': 'KRW', 'CA': 'CAD', 'US': 'USD'}
            if 'Country of Sale' in df.columns:
                df['통화'] = df['Country of Sale'].map(cur_map).fillna(df.get('Customer Currency', 'Unknown'))

            # 2. 상단 요약: 화폐별 매출 합계 나열
            st.divider()
            currency_totals = df.groupby('통화').agg({
                'Customer Price': 'sum',
                'Extended Partner Share': 'sum'
            }).reset_index()

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("### 🛒 총 매출액 (Gross)")
                for _, row in currency_totals.iterrows():
                    st.write(f"**{row['통화']}**: {row['Customer Price']:,.2f}")
            
            with c2:
                st.markdown("### 📈 순 매출액 (Net)")
                for _, row in currency_totals.iterrows():
                    st.write(f"**{row['통화']}**: {row['Extended Partner Share']:,.2f}")

            # 3. 국가별 상세 (수량 정수화)
            st.subheader("🚩 국가별 매출 상세 (Apple)")
            if 'Country of Sale' in df.columns:
                country_summary = df.groupby(['Country of Sale', '통화']).agg({
                    'Customer Price': 'sum', 
                    'Extended Partner Share': 'sum', 
                    'Quantity': 'sum'
                }).reset_index()
                country_summary.columns = ['국가', '통화', '총매출 (Gross)', '순매출 (Net)', '판매 수량']
                country_summary['판매 수량'] = country_summary['판매 수량'].astype(int)
                
                st.dataframe(
                    country_summary.style.format({'총매출 (Gross)': "{:,.2f}", '순매출 (Net)': "{:,.2f}", '판매 수량': "{:,}"}).set_properties(**{'text-align': 'right'}),
                    use_container_width=True, hide_index=True
                )

            # 4. SKU별 집계 (구글 스타일 상세 표)
            st.write("---")
            st.subheader("📦 상품별(SKU) 판매 현황")
            if 'SKU' in df.columns and 'Title' in df.columns:
                sku_stats = df.groupby(['SKU', 'Title', '통화']).agg({
                    'Quantity': 'sum', 
                    'Customer Price': 'sum', 
                    'Extended Partner Share': 'sum'
                }).reset_index()
                sku_stats.columns = ['SKU', '상품명', '통화', '판매 수량', '총매출 합계(Gross)', '순매출 합계(Net)']
                sku_stats['판매 수량'] = sku_stats['판매 수량'].astype(int)
                
                st.dataframe(
                    sku_stats.sort_values(by='판매 수량', ascending=False).style.format({'총매출 합계(Gross)': "{:,.2f}", '순매출 합계(Net)': "{:,.2f}", '판매 수량': "{:,}"}).set_properties(**{'text-align': 'right'}), 
                    use_container_width=True, hide_index=True
                )

            with st.expander("📄 데이터 원본 확인"):
                st.write(df)
        except Exception as e:
            st.error(f"애플 리포트 처리 중 오류가 발생했습니다: {e}")
