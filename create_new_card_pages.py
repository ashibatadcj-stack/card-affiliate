"""新規カードページ（HTMLファイル）を一括作成"""
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
CARDS_DIR = BASE_DIR / 'docs' / 'cards'

# 新規作成が必要なプログラム情報
NEW_PAGES = [
    {
        "id": "s00000015923002",
        "title": "ETC協同組合 法人ETCカード（ポイント版）",
        "h1": "新会社でも作れる・ポイントも貯まる！法人ETCカード【ETC協同組合】",
        "description": "新会社でも発行可能・ポイントも貯まるETC協同組合の法人ETCカード。高速道路料金を大幅削減できる法人向けサービスを解説。",
        "body": """
<h2>ETC協同組合の法人ETCカードとは</h2>
<p>ETC協同組合が提供する法人ETCカードは、新会社や設立直後の法人でも発行しやすいETCカードです。このバージョンではポイントも貯まるお得な特典が付いています。</p>
<p>通常の法人クレジットカードでは審査が厳しく、設立直後の会社が高速道路をよく使う場合でも、ETCカードを入手するのが困難なことがあります。ETC協同組合のカードはこの問題を解決します。</p>

<h2>主な特徴・メリット</h2>
<ul>
    <li><strong>新会社・設立直後でも発行可能</strong> - 銀行系カードでは通りにくい新設法人でも申し込み可能</li>
    <li><strong>ポイントが貯まる</strong> - 高速道路利用でポイントを獲得できる特典付き</li>
    <li><strong>高速道路料金の割引</strong> - まとめて請求で管理が楽になり、割引も適用</li>
    <li><strong>複数枚発行対応</strong> - 車両ごとに複数枚のカードを発行できる</li>
    <li><strong>法人・個人事業主どちらも可</strong> - 法人だけでなく個人事業主でも申し込める</li>
</ul>

<h2>申し込み条件</h2>
<p>法人または個人事業主であることが条件です。新会社でも申し込めるため、設立直後から高速道路を使う事業者に最適です。出資金のみで年会費がかかりません。</p>
"""
    },
    {
        "id": "s00000015923005",
        "title": "ETC協同組合 法人ETCカード（マンガ版）",
        "h1": "マンガでわかる！新会社向け法人ETCカード【ETC協同組合】",
        "description": "マンガ形式でわかりやすく解説！ETC協同組合の法人ETCカード。新会社・設立直後でも発行率No.1のスピード発行サービスを紹介。",
        "body": """
<h2>マンガ版 法人ETCカードとは</h2>
<p>ETC協同組合が提供するマンガ版法人ETCカードは、わかりやすいマンガ形式の説明ページで、サービス内容をより直感的に理解できるように工夫されています。内容は通常版と同じく、新会社でも発行しやすい法人ETCカードです。</p>

<h2>主な特徴・メリット</h2>
<ul>
    <li><strong>新会社への発行率No.1</strong> - 他社では審査が通りにくい設立直後の法人でも発行実績多数</li>
    <li><strong>スピード発行</strong> - 申し込みから最短で手元に届くスピード対応</li>
    <li><strong>高速道路料金30〜50%割引</strong> - 事業での高速道路利用コストを大幅削減</li>
    <li><strong>複数枚発行対応</strong> - 車両台数に応じてカードを複数枚発行可能</li>
    <li><strong>年会費不要</strong> - 出資金のみで年会費がかからない</li>
</ul>

<h2>こんな事業者に向いています</h2>
<p>設立直後で銀行系のETCカードが作れない、車両を複数台保有していてカードを複数枚必要としている、高速道路の使用頻度が高く経費削減したい、という事業者に特におすすめです。</p>
"""
    },
    {
        "id": "s00000015923006",
        "title": "ETC協同組合 法人ガソリンカード（マンガ版）",
        "h1": "全国対応！法人専用ガソリンカード【ETC協同組合 マンガ版】",
        "description": "マンガ形式で解説。ETC協同組合の法人専用ガソリンカード。全国のガソリンスタンドで使えて新会社でも作れる法人向けサービス。",
        "body": """
<h2>法人専用ガソリンカードとは</h2>
<p>ETC協同組合が提供する法人専用ガソリンカードは、全国のガソリンスタンドで利用できる法人向けカードです。このマンガ版では、わかりやすいマンガ形式でサービス内容を解説しています。</p>

<h2>主な特徴・メリット</h2>
<ul>
    <li><strong>全国のガソリンスタンドで使える</strong> - 幅広いネットワークで利便性が高い</li>
    <li><strong>新会社でも作れる</strong> - 法人向けカードながら設立直後でも申し込み可能</li>
    <li><strong>ガソリン代の管理が楽になる</strong> - 経費精算が一元化され経理業務を効率化</li>
    <li><strong>法人・個人事業主対応</strong> - どちらの事業形態でも利用できる</li>
    <li><strong>成約で5000円の報酬</strong> - 新規成約で高額報酬が得られる</li>
</ul>

<h2>申し込み方法</h2>
<p>Web申し込みから始まり、必要書類を提出後、審査を経て発行されます。法人の業種や規模を問わず申し込めますが、法人または個人事業主であることが条件です。</p>
"""
    },
    {
        "id": "s00000018733005",
        "title": "ラボル ファクタリング10秒カンタン無料診断",
        "h1": "法人経営者必見！ファクタリング10秒無料診断【ラボル】",
        "description": "資金調達プロのラボルが提供するファクタリング10秒カンタン無料診断。法人経営者向けの即日資金調達サービスを詳しく解説。",
        "body": """
<h2>ラボル ファクタリング診断とは</h2>
<p>ラボルが提供するファクタリング診断サービスは、法人経営者が10秒で自社のファクタリング可能額を無料で確認できるサービスです。売掛債権を現金化する「ファクタリング」という資金調達手段を、簡単に試せるように設計されています。</p>
<p>ファクタリングとは、会社が保有する売掛金（まだ受け取っていない代金）を専門会社に買い取ってもらうことで、即座に現金を手にする資金調達方法です。銀行融資と異なり、審査が速く、担保が不要な点が特徴です。</p>

<h2>主な特徴・メリット</h2>
<ul>
    <li><strong>10秒で簡単診断</strong> - Webフォームに入力するだけで即座に見積もりが表示される</li>
    <li><strong>無料診断</strong> - 費用なしでファクタリング可能額を確認できる</li>
    <li><strong>即日資金調達も可能</strong> - 審査通過後、最短当日中に資金を受け取れる場合がある</li>
    <li><strong>担保・保証人不要</strong> - 売掛金を担保にするため、不動産担保や保証人が不要</li>
    <li><strong>赤字・債務超過でも利用可能</strong> - 銀行融資が難しい場合でも申し込める</li>
    <li><strong>無料診断申込で10000円の報酬</strong> - 新規無料診断申込で高額の成果報酬</li>
</ul>

<h2>こんな経営者におすすめ</h2>
<p>売掛金があるが入金まで時間がかかる、急な支払いで資金繰りが厳しい、銀行融資の審査に時間がかかって困っている、という法人経営者に特に有用なサービスです。</p>
"""
    },
    {
        "id": "s00000023727001",
        "title": "クレカリ賃貸 家賃クレジット決済サービス",
        "h1": "家賃をクレジットカードで支払う！全国対応【クレカリ賃貸】",
        "description": "クレカリ賃貸は全国の賃貸物件に対応した家賃クレジット決済サービス。ポイント還元を受けながら家賃を支払う方法を解説。",
        "body": """
<h2>クレカリ賃貸とは</h2>
<p>クレカリ賃貸は、通常は銀行振込や口座引き落としで支払う家賃を、クレジットカードで決済できるサービスです。全国の賃貸物件に対応しており、大家さんや管理会社がクレジット決済に対応していなくても、クレカリ賃貸を通じてカード決済が可能になります。</p>
<p>毎月の家賃は多くの家庭で大きな出費となっています。この家賃をクレジットカードで支払うことで、ポイントやマイルを効率的に貯めることができます。</p>

<h2>主な特徴・メリット</h2>
<ul>
    <li><strong>全国の賃貸物件に対応</strong> - 大家さんの対応不要、全国どこでも利用可能</li>
    <li><strong>クレジットカードのポイントが貯まる</strong> - 毎月の家賃でポイントやマイルを獲得</li>
    <li><strong>支払い履歴の一元管理</strong> - カード明細で家賃支払いを管理できる</li>
    <li><strong>引き落とし日の柔軟性</strong> - カードの締め日・支払い日に合わせた資金繰りが可能</li>
    <li><strong>新規利用で1000円の報酬</strong> - 初回利用で成果報酬が得られる</li>
</ul>

<h2>利用開始の流れ</h2>
<p>クレカリ賃貸への申し込みはWebから完結します。物件情報と利用するクレジットカードを登録し、審査を経て利用開始となります。賃貸借契約書などの書類が必要になる場合があります。</p>
"""
    },
    {
        "id": "s00000016537001",
        "title": "ファクタリング事業資金調達【トップ・マネジメント】",
        "h1": "7秒で無料見積！即日ファクタリング資金調達【トップ・マネジメント】",
        "description": "事業資金調達ならトップ・マネジメントのファクタリングサービス。7秒無料お見積り・即日対応で急な資金需要に対応する方法を解説。",
        "body": """
<h2>トップ・マネジメントのファクタリングとは</h2>
<p>株式会社トップ・マネジメントは、法人・個人事業主向けのファクタリングサービスを提供する専門会社です。Webフォームから7秒で無料見積もりを取得でき、急な資金需要にも即日対応します。</p>
<p>ファクタリングは売掛債権（将来受け取れる代金）を専門会社に買い取ってもらい、即座に現金化する資金調達方法です。銀行融資と比べて審査が早く、担保なしで利用できます。</p>

<h2>主な特徴・メリット</h2>
<ul>
    <li><strong>7秒無料お見積り</strong> - Webフォーム入力後すぐに見積額を確認できる</li>
    <li><strong>即日対応可能</strong> - 急な資金需要にも最短当日中に資金を提供</li>
    <li><strong>担保・保証人不要</strong> - 売掛金を活用するため担保不要</li>
    <li><strong>審査通過で24000円の高額報酬</strong> - 新規契約で大きな成果報酬</li>
    <li><strong>Web見積フォームで1000円の報酬</strong> - 見積申込だけでも成果報酬が発生</li>
    <li><strong>法人・個人事業主どちらも対応</strong> - 事業形態を問わず利用可能</li>
</ul>

<h2>こんな事業者に向いています</h2>
<p>請求書を発行しているが入金まで時間がかかる、急な支払いで資金が不足している、銀行融資の審査を待てない、という状況の経営者・事業主に最適なサービスです。</p>
"""
    },
    {
        "id": "s00000012115029",
        "title": "決済代行会社紹介サービス【EMEAO!】",
        "h1": "累計10万件突破！決済代行会社を無料で比較【EMEAO!】",
        "description": "EMEAO!は決済代行会社の紹介サービス。クレジットカード決済導入を検討する事業者向けに最適な決済代行会社を無料で比較紹介。",
        "body": """
<h2>EMEAO!（エミーオ）とは</h2>
<p>EMEAO!は、クレジットカード決済や各種決済代行サービスの導入を検討する事業者向けに、最適な決済代行会社を無料で紹介するマッチングサービスです。累計お問い合わせ数10万件を突破した実績のあるサービスです。</p>
<p>決済代行会社は数多く存在し、手数料率や対応決済方法、サポート体制などが各社で異なります。EMEAO!を利用することで、複数の会社を一度に比較でき、自社に最適なサービスを選べます。</p>

<h2>主な特徴・メリット</h2>
<ul>
    <li><strong>無料で利用できる</strong> - 紹介サービスの利用自体は費用なし</li>
    <li><strong>複数社を一括比較</strong> - 1回の入力で複数の決済代行会社から提案を受けられる</li>
    <li><strong>累計10万件以上の実績</strong> - 多くの事業者が利用している信頼性の高いサービス</li>
    <li><strong>対応業種が幅広い</strong> - 小売業、サービス業、ECサイトなど様々な業種に対応</li>
    <li><strong>新規申込で4000円の報酬</strong> - 新規申し込みで高額の成果報酬</li>
</ul>

<h2>こんな事業者に向いています</h2>
<p>クレジットカード決済を初めて導入したい、現在の決済代行会社の手数料が高い、複数の決済方法（QR決済・電子マネーなど）にまとめて対応したい、という事業者に特におすすめです。</p>
"""
    },
    {
        "id": "s00000012115008",
        "title": "BtoB決済代行比較サービス【一括.jp】",
        "h1": "利用料0円！クレジット・カード決済代行を一括比較【一括.jp】",
        "description": "一括.jpは日本最大級のBtoB見積比較サービス。決済代行会社を無料で一括比較、最適なカード決済導入を支援するサービスを解説。",
        "body": """
<h2>一括.jp（BtoB決済代行比較）とは</h2>
<p>一括.jpは、クレジットカード決済代行サービスをBtoB向けに一括比較できる日本最大級の見積比較サービスです。利用料0円で複数の決済代行会社から見積もりを取り、最適なサービスを選べます。</p>
<p>事業でクレジットカード決済を導入するにあたって、どの会社が自社に合っているか比較するのは手間がかかります。一括.jpなら一度の入力で複数社に見積もり依頼ができます。</p>

<h2>主な特徴・メリット</h2>
<ul>
    <li><strong>利用料0円</strong> - 比較・見積もりサービス自体は完全無料</li>
    <li><strong>日本最大級のBtoB比較サービス</strong> - 豊富な比較対象から最適な会社を選べる</li>
    <li><strong>クレジット・カード決済に特化</strong> - 決済代行に絞った専門的な比較が可能</li>
    <li><strong>一括で複数社に見積もり依頼</strong> - 1回の入力で複数の決済代行会社から提案</li>
    <li><strong>新規打ち合わせで2777円の報酬</strong> - 成約前の打ち合わせだけでも成果報酬が発生</li>
</ul>

<h2>申し込み・利用の流れ</h2>
<p>Webフォームから事業内容と必要な決済機能を入力して送信するだけで、複数の決済代行会社から提案・見積もりが届きます。その中から自社のニーズに合ったサービスを選択できます。</p>
"""
    },
    {
        "id": "s00000008928001",
        "title": "新会社でも作れる法人ETCカード【高速情報協同組合】",
        "h1": "新会社でも安心！法人ETCカード【高速情報協同組合】",
        "description": "高速情報協同組合の法人ETCカード。新会社・設立直後でも発行可能な法人向けETCカードの特徴と申し込み方法を解説。",
        "body": """
<h2>高速情報協同組合の法人ETCカードとは</h2>
<p>高速情報協同組合が提供する法人ETCカードは、新会社や設立直後の法人でも作りやすいETCカードです。銀行系のクレジットカードでは審査が通りにくい設立直後の法人でも、高速道路をよく使う場合に活用できます。</p>

<h2>主な特徴・メリット</h2>
<ul>
    <li><strong>新会社・設立直後でも申し込み可能</strong> - 審査ハードルが比較的低い</li>
    <li><strong>高速道路料金の割引</strong> - 事業での高速道路利用コストを削減</li>
    <li><strong>複数枚発行対応</strong> - 複数車両での使用も対応</li>
    <li><strong>法人・個人事業主どちらも可</strong> - 事業形態を問わず申し込める</li>
    <li><strong>新規成約で5000円の報酬</strong> - 高額の成果報酬</li>
</ul>

<h2>申し込み条件と流れ</h2>
<p>法人または個人事業主であることが申し込み条件です。出資金のみで年会費は不要です。Webから申し込みができ、書類提出後に審査・発行という流れになります。</p>
"""
    },
]

TEMPLATE = '''<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | クレジットカード比較ナビ</title>
  <meta name="description" content="{description}">
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-HWEHFB30XE"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-HWEHFB30XE');</script>
  <meta name="google-site-verification" content="1c5AWMG1j97j_m-wV1lNjDUbZ1Y85Wv992jqB-QElYI" />
  <style>
    body {{ font-family: 'Hiragino Sans', sans-serif; max-width: 860px; margin: 0 auto; padding: 20px 16px; color: #333; line-height: 1.9; }}
    header {{ background: #1a56db; color: white; padding: 16px 20px; border-radius: 8px; margin-bottom: 28px; }}
    header a {{ color: #aac4ff; text-decoration: none; font-size: 0.9rem; }}
    .article-content h1 {{ font-size: 1.7rem; margin-bottom: 20px; line-height: 1.4; }}
    .article-content h2 {{ font-size: 1.25rem; margin: 32px 0 12px; border-left: 4px solid #1a56db; padding-left: 12px; color: #1a56db; }}
    .article-content table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
    .article-content th {{ background: #1a56db; color: white; padding: 10px; text-align: left; }}
    .article-content td {{ padding: 10px; border: 1px solid #ddd; }}
    .article-content tr:nth-child(even) td {{ background: #f5f7fa; }}
    .apply-btn {{ display: block; width: 100%; padding: 16px; background: #e53e3e; color: white; text-align: center; border-radius: 8px; font-size: 1.05rem; font-weight: bold; text-decoration: none; margin: 16px 0; }}
    .banner-wrap {{ text-align: center; margin: 24px 0 8px; }}
    footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; font-size: 0.8rem; color: #888; }}
  </style>
</head>
<body>
  <header><a href="../../index.html">← クレジットカード比較ナビに戻る</a></header>
  <article class="article-content">

<h1>{h1}</h1>

{body}

<a href="AFFILIATE_LINK" class="apply-btn" rel="nofollow noopener" target="_blank">▶ 今すぐ無料で申し込む</a>

  </article>
  <footer><p><a href="../../index.html">トップページ</a> | <a href="../../privacy.html">プライバシーポリシー</a></p><p>※本サイトはアフィリエイト広告を含みます。</p></footer>
</body>
</html>'''


def main():
    created = 0
    skipped = 0
    for p in NEW_PAGES:
        out_path = CARDS_DIR / f'a8_{p["id"]}.html'
        if out_path.exists():
            print(f'スキップ（既存）: {out_path.name}')
            skipped += 1
            continue
        html = TEMPLATE.format(
            title=p['title'],
            description=p['description'],
            h1=p['h1'],
            body=p['body'].strip(),
        )
        out_path.write_text(html, encoding='utf-8')
        print(f'作成: {out_path.name}')
        created += 1
    print(f'\n=== 完了: {created}件作成 / {skipped}件スキップ ===')


if __name__ == '__main__':
    main()
