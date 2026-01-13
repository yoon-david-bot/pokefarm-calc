import streamlit as st
import pandas as pd
import io

# 1. 페이지 설정
st.set_page_config(page_title="포케팜 매출 계산기", page_icon="💰", layout="wide")

st.title("💰 포케팜 매출 신고 계산기")
st.caption("made by 윤 & 쿠마아이콘 🐻")

# 2. 사이드바 - 플랫폼 바로 선택 (라디오 버튼)
st.sidebar.header("플랫폼 선택")
# 드롭다운 대신 라디오 버튼을 사용하여 바로 선택 가능하게 변경
platform = st.sidebar.radio(
    "계산할 플랫폼을 클릭하세요", 
    ["Google Play", "Apple (App Store)"],
    index=0  # 기본값 Google Play
)

if platform == "Google Play":
    # --- [구글 플레이: 원래 로직 100% 유지] ---
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
                for col in [col_net_amt, col_buyer_amt]:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

                total_net_krw = df[col_net_amt].sum()
                total_gross_krw = total_net_krw * 1.4285

                st.divider()
                c1, c2 = st.columns(2)
                c1.metric(label="🛒 총 매출액 (Gross Sales)", value=f"{total_gross_krw:,.0f} 원")
                c2.metric(label="📈 순 매출액 (Net Sales)", value=f"{total_net_krw:,.0f} 원")

                st.subheader("🌐 통화별 매출 상세")
                stats = df.groupby(col_buyer_cur).agg({col_net_amt: 'sum', col_buyer_amt: 'sum', col_buyer_cur: 'count'}).rename(columns={col_buyer_cur: '거래 건수'})
                stats['총 매출 (Gross 원화)'] = stats[col_net_amt] * 1.4285

                final_df = stats.reset_index()
                final_df.columns = ['통화 단위', '순 매출 (Net)', '현지통화결제 합계', '거래 건수', '총 매출 (Gross)']
                st.dataframe(final_df.style.format({'총 매출 (Gross)': "{:,.0f} 원", '순 매출 (Net)': "{:,.0f} 원"}), use_container_width=True, hide_index=True)

                with st.expander("📦 상품별 판매 상세 현황 확인"):
                    item_stats = df.groupby(col_product_title).agg({col_net_amt: 'sum', col_product_title: 'count'}).rename(columns={col_net_amt: '순 매출 합계(원)', col_product_title: '판매 건수'})
                    item_stats['총 매출 합계(원)'] = item_stats['순 매출 합계(원)'] * 1.4285
                    st.dataframe(item_stats.style.format({'총 매출 합계(원)': "{:,.0f} 원", '순 매출 합계(원)': "{:,.0f} 원"}), use_container_width=True)
        except Exception as e:
            st.error(f"구글 데이터 오류: {e}")

else:
    # --- [애플 앱스토어: 정산일 기준 & 요약 섹션 제거 버전] ---
    uploaded_file = st.file_uploader("애플 리포트(CSV 형식)를 선택하세요", type=['csv'])

    if uploaded_file is not None:
        try:
            raw_bytes = uploaded_file.read()
            raw_text = raw_bytes.decode('utf-8')
            lines = raw_text.splitlines()

            filtered_lines = []
            header_found = False
            header_row_index = 0

            for i, line in enumerate(lines):
                if 'SKU' in line and ('Transaction Date' in line or 'Settlement Date' in line):
                    header_found = True
                    header_row_index = i
                if 'Country Of Sale' in line and 'Partner Share Currency' in line:
                    break
                filtered_lines.append(line)

            final_csv_text = "\n".join(filtered_lines)
            df = pd.read_csv(io.StringIO(final_csv_text), skiprows=header_row_index)

            # 정산일 기준 날짜 표시
            col_date_apple = 'Settlement Date' 
            if col_date_apple in df.columns:
                df[col_date_apple] = pd.to_datetime(df[col_date_apple], errors='coerce')
                apple_months = df[col_date_apple].dt.strftime('%m월').dropna().unique()
                apple_months_str = ", ".join(sorted(apple_months))
                st.success(f"📅 데이터 포함 기간 (정산일 기준): **{apple_months_str}**")

            # 수치 데이터 전처리
            num_cols = ['Customer Price', 'Extended Partner Share', 'Quantity', 'Partner Share']
            for col in num_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

            cur_map = {'JP': 'JPY', 'KR': 'KRW', 'CA': 'CAD', 'US': 'USD'}
            if 'Country of Sale' in df.columns:
                df['통화'] = df['Country of Sale'].map(cur_map).fillna(df.get('Customer Currency', 'Unknown'))

            st.subheader("🚩 국가별 매출 상세 (Apple)")
            if 'Country of Sale' in df.columns:
                country_summary = df.groupby(['Country of Sale', '통화']).agg({
                    'Customer Price': 'sum',
                    'Extended Partner Share': 'sum',
                    'Quantity': 'sum'
                }).reset_index()
                country_summary.columns = ['국가', '통화', '총매출 (Gross)', '순매출 (Net)', '판매 수량']
                country_summary['판매 수량'] = country_summary['판매 수량'].astype(int)
                st.dataframe(country_summary.style.format({'총매출 (Gross)': "{:,.2f}", '순매출 (Net)': "{:,.2f}", '판매 수량': "{:,}"}), use_container_width=True, hide_index=True)

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
                st.dataframe(sku_stats.sort_values(by='판매 수량', ascending=False).style.format({'총매출 합계(Gross)': "{:,.2f}", '순매출 합계(Net)': "{:,.2f}", '판매 수량': "{:,}"}), use_container_width=True, hide_index=True)

            with st.expander("📄 데이터 원본 확인"):
                st.write(df)
        except Exception as e:
            st.error(f"애플 리포트 처리 중 오류: {e}")
