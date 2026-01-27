import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import os
import datetime
import re
from collections import Counter

# --- 🛠 設定エリア 🛠 ---
TARGET_CATEGORIES = {
    "👛 レディース財布": "https://ranking.rakuten.co.jp/weekly/502368/",
    "💼 メンズ財布": "https://ranking.rakuten.co.jp/weekly/552710/",
    "🛋 インテリア": "https://ranking.rakuten.co.jp/weekly/100804/",
    "🍳 キッチン用品": "https://ranking.rakuten.co.jp/weekly/558944/",
    "💄 美容・コスメ": "https://ranking.rakuten.co.jp/weekly/100939/",
}

GET_LIMIT = 3       # 各カテゴリー上位3商品（レビューを深く読むので少なめに）
REVIEW_PAGES = 3    # レビューを何ページ分読むか（1ページ約15~20件）
SAVE_DIR = "review_report"
PAGE_PASSWORD = "1234"
# -----------------------

# 分析したいキーワード辞書
KEYWORDS = {
    "👍 良い点": ["早い", "丁寧", "可愛い", "かわいい", "おしゃれ", "安い", "コスパ", "便利", "使いやすい", "リピ", "満足", "美味", "軽い", "柔らかい"],
    "👎 悪い点": ["遅い", "雑", "汚い", "安っぽい", "臭い", "壊れ", "不良", "残念", "重い", "硬い", "小さい", "大きい", "最悪", "微妙"]
}

async def run():
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    today_str = str(datetime.date.today())
    all_data = []

    async with async_playwright() as p:
        # ブラウザ起動（画像は読み込まない設定で高速化）
        browser = await p.chromium.launch(
            headless=False, 
            slow_mo=500,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        # 画像読み込みをブロックして高速化
        await context.route("**/*.{png,jpg,jpeg,gif,webp}", lambda route: route.abort())
        page = await context.new_page()

        for cat_name, cat_url in TARGET_CATEGORIES.items():
            print(f"\n🔍 【{cat_name}】 のランキングを取得中...")
            try:
                await page.goto(cat_url, timeout=60000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)

                # 商品リンク取得
                all_links = await page.locator("div.rnkRanking_after a[href*='item.rakuten.co.jp']").all()
                
                # サムネイル画像取得（ランキングページの画像を流用）
                thumb_imgs = await page.locator("div.rnkRanking_after img").all()
                
                target_items = []
                seen = set()
                
                for i, link in enumerate(all_links):
                    if len(target_items) >= GET_LIMIT: break
                    url = await link.get_attribute("href")
                    clean_url = url.split('?')[0]
                    
                    if clean_url not in seen:
                        seen.add(clean_url)
                        # サムネイルURLを取得
                        thumb_src = ""
                        try:
                            if i < len(thumb_imgs):
                                thumb_src = await thumb_imgs[i].get_attribute("src")
                        except: pass
                        
                        target_items.append({"url": clean_url, "rank": len(target_items)+1, "thumb": thumb_src})

                print(f"   -> {len(target_items)}商品を分析します")

                for item in target_items:
                    print(f"   [{item['rank']}位] レビュー深掘り中...")
                    
                    # 商品ページへ移動
                    await page.goto(item['url'], timeout=60000, wait_until="domcontentloaded")
                    title = await page.title()

                    # レビューURLを探す
                    review_url = ""
                    try:
                        link_loc = page.locator("a[href*='review.rakuten.co.jp']").first
                        if await link_loc.count() > 0:
                            review_url = await link_loc.get_attribute("href")
                    except: pass

                    full_review_text = ""
                    but_sentences = []

                    if review_url:
                        # レビューページへ（複数ページ巡回）
                        curr_rev_url = review_url
                        for p_idx in range(REVIEW_PAGES):
                            try:
                                await page.goto(curr_rev_url, timeout=30000, wait_until="domcontentloaded")
                                content = await page.content()
                                
                                # 本文テキストを全部取得（HTMLタグ除去）
                                text_only = await page.inner_text("body")
                                full_review_text += text_only + "\n"
                                
                                # 「〜ですが、」「〜けど、」などの逆接文を探す（本音チェッカー）
                                # 簡易的な正規表現で抽出
                                sentences = re.split(r'[。！\n]', text_only)
                                for s in sentences:
                                    if "けど" in s or "ですが" in s or "しかし" in s or "残念" in s:
                                        if len(s) < 60: # 長すぎる文は除外
                                            but_sentences.append(s.strip())

                                # 次のページへ
                                next_btn = page.locator("a.next, a:has-text('次の')").first
                                if await next_btn.count() > 0:
                                    curr_rev_url = await next_btn.get_attribute("href")
                                else:
                                    break # 次のページがなければ終了
                            except:
                                break

                    # キーワード集計
                    pos_counts = {}
                    neg_counts = {}
                    
                    for word in KEYWORDS["👍 良い点"]:
                        cnt = full_review_text.count(word)
                        if cnt > 0: pos_counts[word] = cnt
                    
                    for word in KEYWORDS["👎 悪い点"]:
                        cnt = full_review_text.count(word)
                        if cnt > 0: neg_counts[word] = cnt

                    # 逆接文（本音）をランダムに3つ抽出
                    top_buts = list(set(but_sentences))[:3]

                    all_data.append({
                        "category": cat_name,
                        "rank": item['rank'],
                        "title": title[:30] + "...",
                        "thumb": item['thumb'],
                        "url": item['url'],
                        "pos_counts": pos_counts,
                        "neg_counts": neg_counts,
                        "buts": top_buts
                    })

            except Exception as e:
                print(f"   エラースキップ: {e}")
                continue

        await browser.close()

    # --- レポート生成 (HTML) ---
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>レビュー深掘りレポート ({today_str})</title>
        <style>
            body {{ font-family: sans-serif; background: #f4f7f6; padding: 20px; color: #333; }}
            .container {{ max-width: 800px; margin: 0 auto; }}
            h1 {{ text-align: center; color: #003366; }}
            .cat-section {{ margin-top: 40px; border-top: 3px solid #003366; padding-top: 10px; }}
            .product-card {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); display: flex; gap: 15px; }}
            .p-thumb {{ width: 100px; height: 100px; object-fit: cover; border-radius: 4px; border:1px solid #ddd; }}
            .p-info {{ flex: 1; }}
            .p-title {{ font-weight: bold; font-size: 14px; margin-bottom: 10px; display: block; text-decoration: none; color: #333; }}
            .bar-chart {{ display: flex; align-items: center; margin-bottom: 4px; font-size: 11px; }}
            .bar-label {{ width: 60px; text-align: right; margin-right: 8px; }}
            .bar-bg {{ flex: 1; background: #eee; height: 8px; border-radius: 4px; overflow: hidden; max-width: 200px; }}
            .bar-fill {{ height: 100%; }}
            .cnt {{ font-size: 10px; margin-left: 5px; color: #666; }}
            .but-box {{ background: #fff0f0; padding: 10px; border-radius: 6px; font-size: 11px; margin-top: 10px; color: #c00; }}
            .col-2 {{ display: flex; gap: 20px; }}
            .col {{ flex: 1; }}
            h4 {{ margin: 0 0 10px 0; font-size: 12px; color: #666; border-bottom: 1px solid #eee; padding-bottom: 3px; }}
        </style>
        <script>
            window.onload = function() {{
                var pass = prompt("パスワード:");
                if (pass !== "{PAGE_PASSWORD}") {{ document.body.innerHTML = "Access Denied"; }}
            }};
        </script>
    </head>
    <body>
        <div class="container">
            <h1>🧐 レビュー深掘り分析 ({today_str})</h1>
            <p style="text-align:center">各カテゴリTOP3 / 直近約50件の口コミを解析</p>
    """

    categories = list(TARGET_CATEGORIES.keys())
    for cat in categories:
        items = [d for d in all_data if d['category'] == cat]
        if not items: continue
        
        html += f"<div class='cat-section'><h2>{cat}</h2>"
        for item in items:
            # グラフ生成用HTML
            def make_bars(counts, color):
                res = ""
                if not counts: return "<div style='font-size:10px; color:#ccc'>該当なし</div>"
                sorted_k = sorted(counts, key=counts.get, reverse=True)[:5]
                for k in sorted_k:
                    v = counts[k]
                    width = min(100, v * 5) # 1件につき5%幅
                    res += f"""
                    <div class="bar-chart">
                        <span class="bar-label">{k}</span>
                        <div class="bar-bg"><div class="bar-fill" style="width:{width}%; background:{color}"></div></div>
                        <span class="cnt">{v}</span>
                    </div>
                    """
                return res

            pos_html = make_bars(item['pos_counts'], "#4caf50")
            neg_html = make_bars(item['neg_counts'], "#f44336")
            
            but_html = ""
            if item['buts']:
                but_html = "<div class='but-box'><b>⚠️ 気になる本音:</b><ul>" + "".join([f"<li>{s}</li>" for s in item['buts']]) + "</ul></div>"

            html += f"""
            <div class="product-card">
                <img src="{item['thumb']}" class="p-thumb">
                <div class="p-info">
                    <a href="{item['url']}" target="_blank" class="p-title">👑 {item['rank']}位: {item['title']}</a>
                    <div class="col-2">
                        <div class="col">
                            <h4>👍 ポジティブ頻出</h4>
                            {pos_html}
                        </div>
                        <div class="col">
                            <h4>👎 ネガティブ頻出</h4>
                            {neg_html}
                        </div>
                    </div>
                    {but_html}
                </div>
            </div>
            """
        html += "</div>"

    html += "</div></body></html>"

    with open(os.path.join(SAVE_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())