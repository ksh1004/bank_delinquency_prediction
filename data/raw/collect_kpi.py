# -*- coding: utf-8 -*-
"""
fine.fss.or.kr에서 국내은행 핵심경영지표(분기별) 자동 수집
수집 항목: BIS비율, 고정이하여신비율(NPL), ROA, NIM
기간: 2011Q4 ~ 2025Q4
"""
import requests, json, time, sys
import pandas as pd
from bs4 import BeautifulSoup
from pathlib import Path

# 출력 인코딩 설정
sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://fine.fss.or.kr/fine/fncco/coreMngmt/fisisBank.do?menuNo=900048',
    'X-Requested-With': 'XMLHttpRequest',
}
BASE_URL = 'https://fisis.fss.or.kr/fss/wa/'

def call_fisis(session, endpoint, params):
    """FISIS API 호출 (괄호로 감싼 JSON 응답 처리)"""
    r = session.post(BASE_URL + endpoint, data=params, headers=HEADERS, timeout=15)
    text = r.content.decode('utf-8').strip()
    if not text:
        raise ValueError(f"빈 응답 (status={r.status_code})")
    # 응답 형식: (...); 또는 (...)
    if text.startswith('('):
        end = text.rfind(')')   # 마지막 ')' 위치
        text = text[1:end]      # '(' 다음부터 마지막 ')' 앞까지
    return json.loads(text)

# 0. 세션 시작 — 메인 페이지 방문으로 쿠키 확보
SESSION = requests.Session()
print("세션 초기화 중...")
SESSION.get('https://fine.fss.or.kr/fine/fncco/coreMngmt/fisisBank.do?menuNo=900048',
            headers={'User-Agent': HEADERS['User-Agent']}, timeout=15)

# 1. 날짜 목록 조회
print("날짜 목록 조회 중...")
info = call_fisis(SESSION, 'fsv051_getReportInfo.do', {'rc': 'SDCA001'})
date_list = info['dateValue']
print(f"수집 가능 분기: {len(date_list)}개 ({date_list[0]} ~ {date_list[-1]})")

# 2. 각 분기별 데이터 수집
rows = []
for i, yyyymm in enumerate(date_list):
    try:
        data = call_fisis(SESSION, 'fsv050_getReportData.do', {'rc': 'SDCA001', 'my': yyyymm})
        soup = BeautifulSoup(data['DATA'], 'html.parser')

        for tr in soup.find_all('tr'):
            tds = tr.find_all('td')
            bank_name = tds[0].get_text(strip=True) if tds else ''
            if bank_name in ['국내은행', '국내은행 합계', '합계']:
                vals = [td.get_text(strip=True) for td in tds]
                year, month = int(yyyymm[:4]), int(yyyymm[4:])
                q = (month - 1) // 3 + 1
                rows.append({
                    'quarter' : f'{year}Q{q}',
                    'BIS비율' : vals[5] if len(vals) > 5 else None,
                    'NPL비율' : vals[6] if len(vals) > 6 else None,
                    'ROA'     : vals[7] if len(vals) > 7 else None,
                    'NIM'     : vals[8] if len(vals) > 8 else None,
                })
                break

        print(f"  [{i+1:2d}/{len(date_list)}] {yyyymm} 완료")
        time.sleep(0.3)

    except Exception as e:
        print(f"  [{i+1:2d}/{len(date_list)}] {yyyymm} 오류: {e}")

# 3. 저장
df = pd.DataFrame(rows)
for col in ['BIS비율', 'NPL비율', 'ROA', 'NIM']:
    df[col] = pd.to_numeric(df[col].replace('', None), errors='coerce')

save_path = Path(__file__).parent / 'bank_kpi.csv'
df.to_csv(save_path, index=False, encoding='utf-8-sig')
print(f"\n저장 완료: {len(df)}행 → {save_path}")
print(df.tail(5).to_string())
