CARDS = [
    {
        "id": "rakuten",
        "name": "楽天カード",
        "affiliate_url": "https://example.com/rakuten",  # TODO: A8またはafbの楽天カード提携URLに変更
        "annual_fee": "永年無料",
        "points": "楽天ポイント 1%〜3%",
        "features": ["年会費無料", "楽天市場で還元率アップ", "審査が通りやすい"],
        "target": ["初めてクレジットカードを作る人", "楽天をよく使う人", "年会費を払いたくない人"],
        "income_required": "安定収入があれば可",
        "difficulty": "初級",
    },
    {
        "id": "epos",
        "name": "エポスカード",
        "affiliate_url": "https://px.a8.net/svt/ejp?a8mat=4B3IIG+1BMP6A+38L8+BX3J5",  # A8 エポスカード
        "annual_fee": "永年無料",
        "points": "エポスポイント 0.5%",
        "features": ["年会費無料", "マルイで優待", "海外旅行保険付き（無料）"],
        "target": ["マルイをよく使う人", "海外旅行が多い人", "審査に不安がある人"],
        "income_required": "パート・アルバイトでも可",
        "difficulty": "初級",
    },
    {
        "id": "amazon",
        "name": "Amazon Mastercard",
        "affiliate_url": "https://example.com/amazon",  # TODO: Amazon Mastercardの提携URLに変更
        "annual_fee": "永年無料",
        "points": "Amazonポイント 1.5%〜2%",
        "features": ["Amazon利用者向け高還元", "年会費無料", "Primeと相性抜群"],
        "target": ["Amazonをよく使う人", "ネット通販が多い人"],
        "income_required": "安定収入があれば可",
        "difficulty": "easy",
    },
    {
        "id": "sbi_platinum",
        "name": "三井住友カード プラチナプリファード",
        "affiliate_url": "https://example.com/sbi_platinum",  # TODO: 三井住友カード提携URLに変更
        "annual_fee": "33,000円（税込）",
        "points": "Vポイント 最大5%",
        "features": ["高還元率", "SBI証券との連携", "コンシェルジュサービス"],
        "target": ["年収500万円以上", "投資をしている人", "高ステータスを求める人"],
        "income_required": "年収500万円以上推奨",
        "difficulty": "上級",
    },
]

BUSINESS_CARDS = [
    {
        "id": "hojin_etc",
        "name": "新会社でも作れる法人ETCカード",
        "issuer": "高速情報協同組合",
        "affiliate_url": "https://px.a8.net/svt/ejp?a8mat=4B3IIF+D8W8C2+1WW0+NTJWY",
        "annual_fee": "出資金のみ（年会費なし）",
        "discount": "高速料金30〜50%割引",
        "features": [
            "新会社・設立直後でも発行可能",
            "高速道路料金が30〜50%割引",
            "法人・個人事業主どちらも申込可",
            "審査なしで発行しやすい",
            "複数枚発行対応",
        ],
        "target": ["法人", "個人事業主", "新会社・設立直後", "高速道路をよく使う事業者"],
        "apply_condition": "法人または個人事業主であること",
        "reward": "新規成約5,000円",
    },
]

QUIZ_QUESTIONS = [
    {
        "id": "usage",
        "text": "クレジットカードを主にどこで使いますか？",
        "options": [
            {"value": "amazon", "label": "Amazon・ネット通販"},
            {"value": "rakuten", "label": "楽天市場"},
            {"value": "travel", "label": "旅行・海外"},
            {"value": "general", "label": "特にこだわりなし"},
        ],
    },
    {
        "id": "fee",
        "text": "年会費についてどのようにお考えですか？",
        "options": [
            {"value": "free", "label": "絶対に無料がいい"},
            {"value": "ok_paid", "label": "特典次第で有料でも可"},
        ],
    },
    {
        "id": "income",
        "text": "現在の収入状況は？",
        "options": [
            {"value": "part", "label": "パート・アルバイト"},
            {"value": "full", "label": "正社員・公務員"},
            {"value": "high", "label": "年収500万円以上"},
        ],
    },
]
