import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import os
import datetime

# --- 設定エリア ---
TARGET_RANKING_URL = "https://ranking.rakuten.co.jp/daily/"
GET_LIMIT = 5
SAVE_DIR = "lp_stock"
PAGE_PASSWORD = "1234" # ★ここで好きなパスワードを設定できます！
# ------------------

SNS_KEYWORDS = ["インスタ", "Instagram", "instagram", "SNS", "インフルエンサー", "見て購入", "紹介"]

async def run():
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    data_list = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 390, 'height': 844},
            device_scale_factor=2,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
        )
        page = await context.new_page()
        
        print(f"ランキングページにアクセス中: {TARGET_RANKING_URL}")
        await page.goto(TARGET_RANKING_URL, timeout=60000)
        await page.wait_for_timeout(3000)

        # リンク取得
        all_links = await page.locator("a").all()
        target_urls = []
        for link in all_links:
            if len(target_urls) >= GET_LIMIT: break
            try:
                url = await link.get_attribute("href")
                if url and "item.rakuten.co.jp" in url and url not in target_urls:
                    target_urls.append(url)
            except:
                continue

        print(f"【成功】{len(target_urls)}個の商品リンクを確保しました！撮影を開始します...")

        for i, url in enumerate(target_urls):
            try:
                print(f"[{i+1}/{GET_LIMIT}] 撮影中: {url[:30]}...")
                await page.goto(url, timeout=90000, wait_until="domcontentloaded")
                
                await page.evaluate("window.scrollTo(0, 0)")
                prev_height = -1
                scroll_count = 0
                while scroll_count < 40:
                    await page.evaluate("window.scrollBy(0, 1000)")
                    await page.wait_for_timeout(500)
                    curr_height = await page.evaluate("document.body.scrollHeight")
                    if curr_height == prev_height:
                        break
                    prev_height = curr_height
                    scroll_count += 1
                
                title = await page.title()
                content_text = await page.content()
                page_height = await page.evaluate("document.body.scrollHeight")

                sns_score = 0
                found_keywords = []
                for kw in SNS_KEYWORDS:
                    if kw in content_text:
                        sns_score += 1
                        found_keywords.append(kw)
                
                prediction = "不明"
                reason = ""
                tag_color = "gray"

                if sns_score >= 1:
                    prediction = "SNS/指名買い型"
                    reason = f"キーワード検出: {','.join(found_keywords)}"
                    tag_color = "#e1306c"
                elif page_height > 25000:
                    prediction = "従来型LP(説得型)"
                    reason = f"ページが長い({page_height}px)"
                    tag_color = "#bf0000"
                else:
                    prediction = "シンプル/SNS型"
                    reason = f"ページが短い({page_height}px)"
                    tag_color = "#555"

                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-'))[:20]
                img_filename = f"rank{i+1}_{safe_title}.png"
                img_path = os.path.join(SAVE_DIR, img_filename)
                
                await page.screenshot(path=img_path, full_page=True)
                
                data_list.append({
                    "rank": i+1,
                    "title": title,
                    "type": prediction,
                    "reason": reason,
                    "url": url,
                    "img": img_filename,
                    "color": tag_color
                })

            except Exception as e:
                print(f"スキップ: {e}")
                continue

        await browser.close()

    if len(data_list) > 0:
        df = pd.DataFrame(data_list)
        csv_filename = f"rakuten_lp_list_{datetime.date.today()}.csv"
        df.to_csv(os.path.join(SAVE_DIR, csv_filename), index=False, encoding="utf-8-sig")

        # ★ここから：パスワード付きHTML生成
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>楽天LP分析ギャラリー</title>
            <style>
                body {{ font-family: sans-serif; background: #f4f4f4; padding: 20px; display: none; }} /* 最初は非表示 */
                h1 {{ text-align: center; color: #333; }}
                .gallery {{ display: flex; flex-wrap: wrap; gap: 20px; justify-content: center; }}
                .card {{ background: white; width: 300px; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                .tag {{ display: inline-block; padding: 5px 10px; border-radius: 20px; color: white; font-size: 12px; font-weight: bold; margin-bottom: 10px; }}
                .thumb {{ width: 100%; height: 400px; object-fit: cover; object-position: top; border: 1px solid #ddd; border-radius: 5px; cursor: pointer; }}
                .title {{ font-size: 14px; margin: 10px 0; height: 40px; overflow: hidden; }}
                .reason {{ font-size: 11px; color: #666; background: #eee; padding: 5px; border-radius: 4px; }}
                a.link {{ display: block; margin-top: 10px; text-align: center; color: #bf0000; text-decoration: none; font-size: 12px; }}
            </style>
            <script>
                window.onload = function() {{
                    var pass = prompt("閲覧パスワードを入力してください:");
                    if (pass === "{PAGE_PASSWORD}") {{
                        document.body.style.display = "block";
                    }} else {{
                        alert("パスワードが違います。閲覧できません。");
                        document.body.innerHTML = "<h1>⛔ Access Denied</h1>";
                        document.body.style.display = "block";
                    }}
                }};
            </script>
        </head>
        <body>
            <h1>🏆 楽天LP分析ギャラリー ({datetime.date.today()})</h1>
            <div class="gallery">
        """

        for item in data_list:
            html_content += f"""
                <div class="card">
                    <span class="tag" style="background: {item['color']}">{item['type']}</span>
                    <a href="{item['img']}" target="_blank">
                        <img src="{item['img']}" class="thumb" title="クリックで全体を見る">
                    </a>
                    <div class="title"><b>{item['rank']}位:</b> {item['title'][:40]}...</div>
                    <div class="reason">💡 {item['reason']}</div>
                    <a href="{item['url']}" target="_blank" class="link">楽天ページを開く &rarr;</a>
                </div>
            """

        html_content += """
            </div>
        </body>
        </html>
        """

        with open(os.path.join(SAVE_DIR, "index.html"), "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"\n✨ 完成！パスワード付きです。")
        print(f"設定パスワード: {PAGE_PASSWORD}")
    else:
        print("\nデータなし")

asyncio.run(run())