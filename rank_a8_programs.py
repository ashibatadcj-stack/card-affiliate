"""A8 推奨プログラム135件を、サイトコンセプト適合度＋収益性で優先度順にランク付け"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent
INPUT = BASE / 'a8_recommended_programs.json'
OUTPUT_MD = BASE / 'a8_priority_list.md'


# プログラム名のキーワードによる強い適合判定
NAME_TIER_S = [
    r'クレジットカード', r'クレカ', r'カード比較', r'カードランキング',
    r'楽天カード', r'三井住友', r'JCB', r'アメリカン.エキスプレス', r'AMEX',
    r'セゾン', r'イオンカード', r'ライフカード', r'リクルートカード',
    r'au.{0,3}PAY.{0,3}カード', r'PayPayカード', r'dカード', r'TS3', r'ANA.{0,3}カード',
    r'ビュー.{0,3}カード', r'プラチナカード', r'ゴールドカード',
]
NAME_TIER_A = [
    r'カードローン', r'キャッシング', r'プロミス', r'アコム', r'アイフル',
    r'モビット', r'レイク', r'消費者金融', r'即日融資', r'借入',
    r'ファクタリング', r'資金調達', r'売掛',
    r'法人.{0,3}カード', r'ビジネス.{0,3}カード', r'ETC', r'高速', r'ガソリン',
    r'個人事業', r'フリーランス',
]
NAME_TIER_B = [
    r'銀行', r'証券', r'NISA', r'iDeCo', r'投資信託', r'FX',
    r'ポイ活', r'ポイントサイト', r'お小遣い',
    r'プリペイド', r'デビットカード', r'電子マネー', r'スマホ決済',
    r'仮想通貨', r'ビットコイン', r'暗号資産',
]
# サイトコンセプト外（主要キーワード）
NAME_TIER_OUT = [
    r'保険', r'生命保険', r'医療保険', r'ペット保険', r'がん保険',
    r'WiFi', r'モバイル.{0,3}通信', r'eSIM', r'格安SIM',
    r'占い', r'恋愛', r'マッチング',
    r'転職', r'就職', r'求人',
    r'ダイエット', r'美容', r'脱毛', r'エステ',
    r'引越', r'不動産', r'住宅', r'マンション',
    r'モニター', r'アンケート',
]


def name_tier(name: str) -> str:
    n = name or ''
    for pat in NAME_TIER_OUT:
        if re.search(pat, n):
            return 'OUT'
    for pat in NAME_TIER_S:
        if re.search(pat, n, re.IGNORECASE):
            return 'S'
    for pat in NAME_TIER_A:
        if re.search(pat, n, re.IGNORECASE):
            return 'A'
    for pat in NAME_TIER_B:
        if re.search(pat, n, re.IGNORECASE):
            return 'B'
    return 'C'


def parse_reward(reward: str) -> int:
    """成果報酬文字列から金額(円)を推定。'1400円' → 1400, '5%' → 報酬率を簡易換算"""
    if not reward:
        return 0
    # "1,400円" や "1400円"
    m = re.search(r'([\d,]+)\s*円', reward)
    if m:
        return int(m.group(1).replace(',', ''))
    # "1.5%"
    m = re.search(r'([\d.]+)\s*%', reward)
    if m:
        # 平均購入額 5000円 と仮定して還元金額を概算
        return int(float(m.group(1)) * 50)
    return 0


def parse_epc(epc: str) -> float:
    if not epc:
        return 0.0
    m = re.search(r'([\d.]+)', epc)
    return float(m.group(1)) if m else 0.0


def main():
    data = json.loads(INPUT.read_text(encoding='utf-8'))
    candidates = data['new_candidates']

    # 各プログラムにスコア計算
    for p in candidates:
        pgName = p.get('pgName', '')
        company = p.get('company', '')
        category = p.get('category', '')

        # 名前ベースのティア判定（最も重要）
        tier = name_tier(pgName + ' ' + company)
        p['tier'] = tier

        # 基本スコア（ティア重み）
        tier_score = {'S': 1000, 'A': 500, 'B': 200, 'C': 50, 'OUT': 0}[tier]

        # 成果報酬（最大500ptまで）
        reward_yen = parse_reward(p.get('reward', ''))
        reward_score = min(500, reward_yen // 10)

        # EPC（最大100pt）
        epc = parse_epc(p.get('epc', ''))
        epc_score = min(100, int(epc * 10))

        p['score'] = tier_score + reward_score + epc_score
        p['reward_yen_est'] = reward_yen
        p['epc_value'] = epc

    # OUT を除外、スコア降順
    ranked = [p for p in candidates if p['tier'] != 'OUT']
    ranked.sort(key=lambda p: -p['score'])

    excluded = [p for p in candidates if p['tier'] == 'OUT']

    # Markdown 整形
    md = ["# 🎯 A8 推奨プログラム 優先度順リスト\n"]
    md.append(f"取得: {data['fetched_at']}  /  対象: 135件 → 優先度ランク済 {len(ranked)} 件（{len(excluded)} 件はサイト無関係で除外）\n")
    md.append("\n## 凡例\n")
    md.append("- **🏆 Sランク**: クレジットカード本体（最重要・サイト主軸）")
    md.append("- **🥇 Aランク**: カードローン・ファクタリング・法人カード等（高単価・関連性◎）")
    md.append("- **🥈 Bランク**: 銀行/証券・ポイ活・決済（クレカと連携可能）")
    md.append("- **🥉 Cランク**: その他（参考）")

    for tier_label, tier_emoji in [("S", "🏆 Sランク - クレジットカード本体"),
                                     ("A", "🥇 Aランク - カードローン/ファクタリング/法人系"),
                                     ("B", "🥈 Bランク - 銀行/証券/ポイ活/決済"),
                                     ("C", "🥉 Cランク - その他")]:
        items = [p for p in ranked if p['tier'] == tier_label]
        if not items:
            continue
        md.append(f"\n## {tier_emoji}（{len(items)}件）\n")
        md.append("| # | 広告主 | プログラム名 | 成果報酬 | EPC | 確定率 | カテゴリ | ID |")
        md.append("|---|---|---|---|---|---|---|---|")
        for i, p in enumerate(items, 1):
            md.append(f"| {i} | {p.get('company','')[:25]} | {p.get('pgName','')[:55]} | {p.get('reward','')[:30]} | {p.get('epc','')} | {p.get('decideRate','')} | {p.get('category','')[:15]} | `{p['id']}` |")

    if excluded:
        md.append(f"\n## 🚫 除外（{len(excluded)}件・サイト無関係）\n")
        md.append("<details><summary>クリックで展開</summary>\n")
        md.append("\n| 広告主 | プログラム名 | カテゴリ | ID |")
        md.append("|---|---|---|---|")
        for p in excluded:
            md.append(f"| {p.get('company','')[:25]} | {p.get('pgName','')[:55]} | {p.get('category','')[:15]} | `{p['id']}` |")
        md.append("\n</details>\n")

    OUTPUT_MD.write_text('\n'.join(md), encoding='utf-8')

    # コンソールサマリー
    print(f"=== 優先度ランク結果 ===")
    for tier in 'SABC':
        n = sum(1 for p in ranked if p['tier'] == tier)
        print(f"  {tier}ランク: {n}件")
    print(f"  除外（OUT）: {len(excluded)}件")
    print(f"\nMarkdown 出力: {OUTPUT_MD}")


if __name__ == '__main__':
    main()
