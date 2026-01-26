import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import os
import datetime

# --- 設定エリア ---
TARGET_CATEGORIES = {
    "🏆 総合": "https://ranking.rakuten.co.jp/daily/",
    "👗 レディースファッション": "https://ranking.rakuten.co.jp/daily/100371/",
    "🍜 食品": "https://ranking.rakuten.co.jp/daily/100227/",
    "💄 美容・コスメ": "https://ranking.rakuten.co.jp/daily/100939/"
}

GET_LIMIT = 3   # 各カテゴリーごとに何位まで取るか
SAVE_DIR = "lp_stock"
PAGE_PASSWORD = "1234" 
# ------------------

SNS_KEYWORDS = ["インスタ", "Instagram", "instagram", "SNS", "インフルエンサー", "見て購入", "紹介"]

async def run():
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    all_data_list = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 390, 'height': 844},
            device_scale_factor=2,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
        )
        page = await context.new_page()

        # ▼▼▼ カテゴリーごとにループ開始 ▼▼▼
        for cat_name, cat_url in TARGET_CATEGORIES.items():
            print(f"\n🔍 【{cat_name}】 のランキングを取得中...")
            
            try:
                await page.goto(cat_url, timeout=60000)
                await page.wait_for_timeout(2000)

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
                
                print(f"   -> {len(target_urls)}個の商品を発見。撮影します。")

                for i, url in enumerate(target_urls):
                    try:
                        print(f"   [{i+1}/{GET_LIMIT}] 撮影中...")
                        await page.goto(url, timeout=90000, wait_until="domcontentloaded")
                        
                        await page.evaluate("window.scrollTo(0, 0)")
                        prev_height = -1
                        scroll_count = 0
                        while scroll_count < 30:
                            await page.evaluate("window.scrollBy(0, 1500)")
                            await page.wait_for_timeout(300)
                            curr_height = await page.evaluate("document.body.scrollHeight")
                            if curr_height == prev_height: break
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
                            reason = f"キーワード: {','.join(found_keywords)}"
                            tag_color = "#e1306c"
                        elif page_height > 25000:
                            prediction = "従来型LP(説得型)"
                            reason = f"長尺({page_height}px)"
                            tag_color = "#bf0000"
                        else:
                            prediction = "シンプル/SNS型"
                            reason = f"短尺({page_height}px)"
                            tag_color = "#555"

                        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-'))[:15]
                        safe_cat_name = "".join(c for c in cat_name if c.isalnum())
                        img_filename = f"{safe_cat_name}_{i+1}_{safe_title}.jpg"
                        img_path = os.path.join(SAVE_DIR, img_filename)
                        
                        await page.screenshot(path=img_path, full_page=True, type="jpeg", quality=70)
                        
                        all_data_list.append({
                            "category": cat_name,
                            "rank": i+1,
                            "title": title,
                            "type": prediction,
                            "reason": reason,
                            "url": url,
                            "img": img_filename,
                            "color": tag_color
                        })

                    except Exception as e:
                        print(f"   スキップ: {e}")
                        continue
            except Exception as e:
                print(f"   カテゴリー取得エラー: {e}")
                continue
        
        await browser.close()

    # --- HTML生成エリア（ビューアー機能を追加！） ---
    if len(all_data_list) > 0:
        df = pd.DataFrame(all_data_list)
        csv_filename = f"rakuten_lp_list_{datetime.date.today()}.csv"
        df.to_csv(os.path.join(SAVE_DIR, csv_filename), index=False, encoding="utf-8-sig")

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>楽天LP分析ギャラリー</title>
            <style>
                body {{ font-family: "Helvetica Neue", Arial, sans-serif; background: #f0f2f5; padding: 20px; display: none; color: #333; }}
                h1 {{ text-align: center; margin-bottom: 30px; }}
                h2.cat-title {{ 
                    margin-top: 50px; margin-bottom: 20px; padding-left: 15px; 
                    border-left: 5px solid #bf0000; font-size: 24px; background: #fff;
                    padding: 10px 15px; border-radius: 0 5px 5px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                }}
                .gallery {{ display: flex; flex-wrap: wrap; gap: 20px; justify-content: flex-start; }}
                
                /* カードのデザイン */
                .card {{ background: white; width: 300px; padding: 15px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); transition: transform 0.2s; position: relative; }}
                .card:hover {{ transform: translateY(-5px); box-shadow: 0 8px 15px rgba(0,0,0,0.15); }}
                
                .tag {{ display: inline-block; padding: 4px 12px; border-radius: 20px; color: white; font-size: 11px; font-weight: bold; margin-bottom: 10px; }}
                
                /* サムネイルクリック時のカーソルを変更 */
                .thumb-wrapper {{ cursor: zoom-in; overflow: hidden; border-radius: 6px; border: 1px solid #eee; height: 350px; }}
                .thumb {{ width: 100%; height: 100%; object-fit: cover; object-position: top; transition: opacity 0.3s; }}
                .thumb:hover {{ opacity: 0.8; }}

                .title {{ font-size: 13px; margin: 10px 0; height: 38px; overflow: hidden; line-height: 1.4; }}
                .reason {{ font-size: 11px; color: #666; background: #f8f8f8; padding: 6px; border-radius: 4px; margin-bottom: 10px; }}
                a.link {{ display: block; text-align: center; background: #bf0000; color: white; text-decoration: none; font-size: 12px; padding: 8px; border-radius: 6px; font-weight: bold; }}
                
                /* --- 拡大ビューアー（モーダル）のスタイル --- */
                .modal {{
                    display: none; position: fixed; z-index: 999; left: 0; top: 0;
                    width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.85);
                    backdrop-filter: blur(5px);
                }}
                .modal-content-wrapper {{
                    position: relative; margin: 20px auto; width: 95%; max-width: 600px;
                    background: white; border-radius: 8px; overflow: hidden;
                    box-shadow: 0 0 20px rgba(0,0,0,0.5);
                }}
                .modal-header {{
                    background: #fff; padding: 15px; border-bottom: 1px solid #eee;
                    display: flex; justify-content: space-between; align-items: center;
                    position: sticky; top: 0; z-index: 100;
                }}
                .close-btn {{
                    color: #333; font-size: 28px; font-weight: bold; cursor: pointer; line-height: 1;
                    background: #f0f0f0; width: 40px; height: 40px; border-radius: 50%;
                    text-align: center; display: flex; align-items: center; justify-content: center;
                }}
                .modal-img {{ width: 100%; display: block; }}
            </style>
            
            <script>
                // パスワード認証
                window.onload = function() {{
                    var pass = prompt("閲覧パスワードを入力してください:");
                    if (pass === "{PAGE_PASSWORD}") {{
                        document.body.style.display = "block";
                    }} else {{
                        alert("パスワードが違います。");
                        document.body.innerHTML = "<h1>⛔ Access Denied</h1>";
                        document.body.style.display = "block";
                    }}
                }};

                // ビューアーを開く関数
                function openModal(imgSrc, title) {{
                    var modal = document.getElementById("imageModal");
                    var modalImg = document.getElementById("modalImg");
                    var modalTitle = document.getElementById("modalTitle");
                    
                    modal.style.display = "block";
                    modalImg.src = imgSrc;
                    modalTitle.innerText = title;
                    document.body.style.overflow = "hidden"; // 背景スクロール固定
                }}

                // ビューアーを閉じる関数
                function closeModal() {{
                    var modal = document.getElementById("imageModal");
                    modal.style.display = "none";
                    document.body.style.overflow = "auto"; // スクロール解除
                }}

                // 背景クリックでも閉じる
                window.onclick = function(event) {{
                    var modal = document.getElementById("imageModal");
                    if (event.target == modal) {{
                        closeModal();
                    }}
                }}
            </script>
        </head>
        <body>
            <h1>🏆 楽天LP分析ギャラリー ({datetime.date.today()})</h1>

            <div id="imageModal" class="modal">
                <div class="modal-content-wrapper">
                    <div class="modal-header">
                        <div id="modalTitle" style="font-size:14px; font-weight:bold; overflow:hidden; white-space:nowrap; text-overflow:ellipsis; width:85%;">タイトル</div>
                        <span class="close-btn" onclick="closeModal()">&times;</span>
                    </div>
                    <img class="modal-img" id="modalImg">
                </div>
            </div>
        """

        unique_categories = list(TARGET_CATEGORIES.keys())
        for cat in unique_categories:
            cat_items = [d for d in all_data_list if d['category'] == cat]
            if len(cat_items) > 0:
                html_content += f'<h2 class="cat-title">{cat}</h2>'
                html_content += '<div class="gallery">'
                for item in cat_items:
                    html_content += f"""
                        <div class="card">
                            <span class="tag" style="background: {item['color']}">{item['type']}</span>
                            <div class="thumb-wrapper" onclick="openModal('{item['img']}', '{item['title']}')">
                                <img src="{item['img']}" class="thumb" loading="lazy" title="クリックで拡大">
                            </div>
                            <div class="title"><b>{item['rank']}位:</b> {item['title'][:35]}...</div>
                            <div class="reason">💡 {item['reason']}</div>
                            <a href="{item['url']}" target="_blank" class="link">楽天ページを見る</a>
                        </div>
                    """
                html_content += '</div>'

        html_content += """
        </body>
        </html>
        """

        with open(os.path.join(SAVE_DIR, "index.html"), "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"\n✨ 全カテゴリー収集完了！ビューアー機能付きです。")
    else:
        print("\nデータが取れませんでした")

asyncio.run(run())