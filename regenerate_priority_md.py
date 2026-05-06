"""
a8_recommended_programs.json から、申請ステータス付きの優先度Markdown を再生成
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent
INPUT = BASE / 'a8_recommended_programs.json'
OUTPUT_MD = BASE / 'a8_priority_list.md'


NAME_TIER_S = [
    r'クレジットカード', r'クレカ', r'カード比較', r'カードランキング',
    r'楽天カード', r'三井住友', r'JCB', r'アメリカン.エキスプレス', r'AMEX',
    r'セゾン', r'イオンカード', r'ライフカード', r'リクルートカード',
    r'au.{0,3}PAY.{0,3}カード', r'PayPayカード', r'dカード', r'TS3', r'ANA.{0,3}カード',
    r'ビュー.{0,3}カード', r'プラチナカード', r'ゴールドカード', r'INVOY', r'請求書',
    r'JAカード', r'Nexus.Card', r'FASIO',
]
NAME_TIER_A = [
    r'カードローン', r'キャッシング', r'プロミス', r'アコム', r'アイフル',
    r'モビット', r'レイク', r'消費者金融', r'即日融資', r'借入',
    r'ファクタリング', r'資金調達', r'売掛',
    r'法人.{0,3}カード', r'ビジネス.{0,3}カード', r'ETC', r'高速', r'ガソリン',
    r'個人事業', r'フリーランス', r'マネーフォワード',
]
NAME_TIER_B = [
    r'銀行', r'証券', r'NISA', r'iDeCo', r'投資信託', r'FX', r'CFD',
    r'ポイ活', r'ポイントサイト', r'お小遣い', r'ハピタス', r'ちょびリッチ', r'ECナビ', r'モッピー', r'ワラウ', r'アメフリ',
    r'プリペイド', r'デビットカード', r'電子マネー',
    r'仮想通貨', r'ビットコイン', r'暗号資産', r'VC.{0,3}トレード',
]
NAME_OUT = [
    r'保険', r'生命保険', r'医療保険', r'ペット保険', r'がん保険',
    r'WiFi', r'Wi-Fi', r'wi-fi', r'モバイル.{0,3}通信', r'eSIM', r'格安SIM',
    r'占い', r'恋愛', r'マッチング',
    r'転職', r'就職', r'求人', r'在宅ワーク',
    r'ダイエット', r'美容', r'脱毛', r'エステ',
    r'引越', r'不動産', r'住宅', r'マンション', r'バーチャルオフィス', r'コワーキング',
    r'モニター', r'アンケート', r'ゲーム', r'スロット', r'パチンコ',
    r'英会話', r'ヨガ', r'宅食', r'レンタル携帯', r'ネットショップ検定',
    r'ファッション', r'コーディネート', r'ナビタイム', r'レンタカー', r'整備', r'車検',
    r'POS', r'クラウドファンディング', r'資料請求', r'アート', r'ポスター',
]


def name_tier(text: str) -> str:
    for pat in NAME_OUT:
        if re.search(pat, text):
            return 'OUT'
    for pat in NAME_TIER_S:
        if re.search(pat, text, re.IGNORECASE):
            return 'S'
    for pat in NAME_TIER_A:
        if re.search(pat, text, re.IGNORECASE):
            return 'A'
    for pat in NAME_TIER_B:
        if re.search(pat, text, re.IGNORECASE):
            return 'B'
    return 'C'


def status_emoji(p):
    app = p.get('application_status', '')
    apv = p.get('approval_status', '')
    if app == '申請済み' and '許可' in apv and '未' not in apv:
        return '🟢 提携中'
    if app == '申請済み' and '審査' in apv:
        return '🟡 審査中'
    if '否認' in apv:
        return '🔴 否認'
    if 'キャンセル' in apv:
        return '⚫ キャンセル'
    if app == '未申請':
        return '⚪ 未申請'
    return '?'


def main():
    data = json.loads(INPUT.read_text(encoding='utf-8'))
    candidates = data['new_candidates']

    for p in candidates:
        text = p.get('pgName', '') + ' ' + p.get('company', '')
        p['_tier'] = name_tier(text)

    # 統計
    from collections import Counter
    tier_count = Counter(p['_tier'] for p in candidates)
    app_count = Counter(p.get('application_status', '不明') for p in candidates)
    apv_count = Counter(p.get('approval_status', '-') for p in candidates)

    md = ["# 🎯 A8 推奨プログラム 優先度・申請ステータス一覧\n"]
    md.append(f"取得: {data.get('fetched_at','-')}  /  対象: {len(candidates)} 件\n")
    md.append("\n## 📊 全体ステータス\n")
    md.append("### ティア別件数")
    for t in 'SABCO':
        if t == 'O':
            md.append(f"- 🚫 OUT（サイト無関係）: {tier_count.get('OUT',0)}件")
        else:
            tname = {'S': '🏆 Sランク（クレカ本体）',
                     'A': '🥇 Aランク（カードローン/ファクタリング/法人）',
                     'B': '🥈 Bランク（銀行/証券/ポイ活/決済）',
                     'C': '🥉 Cランク（その他）'}[t]
            md.append(f"- {tname}: {tier_count.get(t,0)}件")
    md.append("\n### 申請ステータス")
    md.append(f"- 🟢 提携中（広告リンク発行可）: **{apv_count.get('許可（広告リンク発行）',0)}件**")
    md.append(f"- 🟡 審査中: {apv_count.get('未許可（審査中）',0)}件")
    md.append(f"- 🔴 否認: {apv_count.get('否認',0)}件")
    md.append(f"- ⚪ 未申請: {app_count.get('未申請',0)}件")

    # ソート: ステータス（提携中優先）→ ティア → company
    def status_order(p):
        apv = p.get('approval_status', '')
        if '許可' in apv and '未' not in apv: return 0
        if '審査' in apv: return 1
        if '未申請' == p.get('application_status', ''): return 2
        if '否認' in apv: return 3
        return 4
    tier_order = {'S':0, 'A':1, 'B':2, 'C':3, 'OUT':9}

    for tier, tier_label in [('S', '🏆 Sランク'),
                                ('A', '🥇 Aランク'),
                                ('B', '🥈 Bランク'),
                                ('C', '🥉 Cランク')]:
        items = [p for p in candidates if p['_tier'] == tier]
        if not items:
            continue
        items.sort(key=lambda p: (status_order(p), p.get('company','')))
        md.append(f"\n## {tier_label}（{len(items)}件）\n")
        md.append("| # | ステータス | 広告主 | プログラム名 | 成果報酬 | EPC | ID |")
        md.append("|---|---|---|---|---|---|---|")
        for i, p in enumerate(items, 1):
            stat = status_emoji(p)
            md.append(f"| {i} | {stat} | {p.get('company','')[:25]} | {p.get('pgName','')[:55]} | {p.get('reward','')[:25]} | {p.get('epc','')} | `{p['id']}` |")

    # OUT セクションは折り畳み
    out_items = [p for p in candidates if p['_tier'] == 'OUT']
    if out_items:
        md.append(f"\n## 🚫 サイト無関係（{len(out_items)}件）\n")
        md.append("<details><summary>クリックで展開</summary>\n")
        md.append("\n| ステータス | 広告主 | プログラム名 | ID |")
        md.append("|---|---|---|---|")
        for p in out_items:
            md.append(f"| {status_emoji(p)} | {p.get('company','')[:25]} | {p.get('pgName','')[:55]} | `{p['id']}` |")
        md.append("\n</details>")

    OUTPUT_MD.write_text('\n'.join(md), encoding='utf-8')
    print(f"出力: {OUTPUT_MD}")
    print(f"\n=== ステータス内訳 ===")
    print(f"  🟢 提携中: {apv_count.get('許可（広告リンク発行）', 0)}件")
    print(f"  🟡 審査中: {apv_count.get('未許可（審査中）', 0)}件")
    print(f"  🔴 否認: {apv_count.get('否認', 0)}件")
    print(f"  ⚪ 未申請: {app_count.get('未申請', 0)}件")


if __name__ == '__main__':
    main()
