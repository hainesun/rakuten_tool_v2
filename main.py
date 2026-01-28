import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import os
import datetime
import glob
import re
import random

# --- 🛠 設定エリア (デイリー版) 🛠 ---
TARGET_CATEGORIES = {
    "👛 レディース財布(デイリー)": "https://ranking.rakuten.co.jp/daily/502368/",
    "💼 メンズ財布(デイリー)": "https://ranking.rakuten.co.jp/daily/552710/",
    "🛋 インテリア(デイリー)": "https://ranking.rakuten.co.jp/daily/100804/",
    "🍳 キッチン用品(デイリー)": "https://ranking.rakuten.co.jp/daily/558944/",
    "💄 美容・コスメ(デイリー)": "https://ranking.rakuten.co.jp/daily/100939/",
}

GET_LIMIT = 10      # 10位まで取得
SAVE_DIR = "lp_stock"
REVIEW_DIR = "review_report"
PAGE_PASSWORD = "1234" 
KEEP_DAYS = 60

# キーワードリスト
REVIEW_KEYWORDS = [
    "早い", "遅い", "丁寧", "雑", 
    "可愛い", "かわいい", "おしゃれ", "シンプル", "高見え", "安っぽい",
    "使いやすい", "便利", "軽い", "重い", "小さい", "大きい",
    "リピ", "プレゼント", "満足", "残念", "おすすめ", "サイズ感", "ちょうどいい", "到着", "リピート",
    "美味", "不味", "香り", "肌触り", "柔らかい", "硬い", "コスパ", "お得", "セール", "割引", "値上げ", "値下げ"
]
SNS_KEYWORDS = ["インスタ", "Instagram", "instagram", "SNS", "インフルエンサー", "見て購入", "紹介"]

async def run_fixed():
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    all_data_list = []
    today = datetime.date.today()
    today_str = str(today)

    # お掃除
    limit_date = today - datetime.timedelta(days=KEEP_DAYS)
    files = glob.glob(os.path.join(SAVE_DIR, "*"))
    for f in files:
        filename = os.path.basename(f)
        match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
        if match:
            try:
                if datetime.datetime.strptime(match.group(1), "%Y-%m-%d").date() < limit_date:
                    os.remove(f)
            except: continue

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=500,    
            args=['--disable-blink-features=AutomationControlled'] 
        )
        
        context = await browser.new_context(
            viewport={'width': 390, 'height': 8000}, 
            device_scale_factor=2,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        )
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        for cat_name, cat_url in TARGET_CATEGORIES.items():
            print(f"\n🔍 【{cat_name}】 のランキングを取得中...")
            try:
                await page.goto(cat_url, timeout=90000, wait_until="domcontentloaded")
                
                # 画像を読み込ませるためのスクロール
                await page.evaluate("window.scrollBy(0, 1000)")
                await page.wait_for_timeout(1000)

                # リンク取得
                all_links = await page.locator("div.rnkRanking_image a[href*='item.rakuten.co.jp'], div.rnkRanking_after a[href*='item.rakuten.co.jp']").all()
                
                # ★修正ポイント: 上位(rnkRanking_image)と下位(rnkRanking_after)の両方の画像を取得
                thumb_imgs = await page.locator("div.rnkRanking_image img, div.rnkRanking_after img").all()

                target_items = []
                seen_items = set()
                
                for i, link in enumerate(all_links):
                    if len(target_items) >= GET_LIMIT: break
                    try:
                        url = await link.get_attribute("href")
                        if url and "item.rakuten.co.jp" in url:
                            clean_url = url.split('?')[0]
                            if clean_url not in seen_items:
                                seen_items.add(clean_url)
                                
                                # サムネイルURLを取得
                                thumb_src = ""
                                if i < len(thumb_imgs):
                                    thumb_src = await thumb_imgs[i].get_attribute("src")
                                    if not thumb_src:
                                        thumb_src = await thumb_imgs[i].get_attribute("data-src")
                                    
                                    if thumb_src and "?_ex=" in thumb_src:
                                         thumb_src = thumb_src.split("?_ex=")[0] + "?_ex=200x200"

                                target_items.append({"url": clean_url, "thumb": thumb_src})
                    except: continue
                
                print(f"   -> {len(target_items)}個の商品リンク・画像を確保")

                for i, item in enumerate(target_items):
                    url = item["url"]
                    thumb_url = item["thumb"]
                    
                    try:
                        print(f"   [{i+1}/{GET_LIMIT}] 分析中...")
                        
                        await page.goto(url, timeout=90000, wait_until="domcontentloaded")
                        
                        await page.evaluate("window.scrollTo(0, 0)")
                        for _ in range(3):
                            await page.evaluate("window.scrollBy(0, 2500)")
                            await page.wait_for_timeout(500)
                        await page.evaluate("window.scrollTo(0, 0)")
                        try: await page.wait_for_load_state("networkidle", timeout=3000)
                        except: await page.wait_for_timeout(2000)

                        safe_cat_name = "".join(c for c in cat_name if c.isalnum())
                        
                        img_filename = f"{today_str}_{safe_cat_name}_rank{i+1}.jpg"
                        img_path = os.path.join(SAVE_DIR, img_filename)
                        
                        await page.screenshot(path=img_path, type="jpeg", quality=50)

                        title = await page.title()
                        content_text = await page.content()
                        page_height = await page.evaluate("document.body.scrollHeight")
                        
                        review_url = ""
                        try:
                            review_link_loc = page.locator("a[href*='review.rakuten.co.jp']").first
                            if await review_link_loc.count() > 0:
                                review_url = await review_link_loc.get_attribute("href")
                        except: pass
                        
                        catch_copy = ""
                        try:
                            catch_loc = page.locator(".catch_copy, .item_catch_copy, [class*='catch']").first
                            if await catch_loc.count() > 0:
                                txt = await catch_loc.text_content()
                                catch_copy = txt.strip()[:60] + "..."
                        except: pass

                        sns_score = 0
                        found_keywords = []
                        for kw in SNS_KEYWORDS:
                            if kw in content_text:
                                sns_score += 1
                                found_keywords.append(kw)

                        review_summary = "なし"
                        review_keywords_list = []
                        if review_url:
                            try:
                                await page.goto(review_url, timeout=30000, wait_until="domcontentloaded")
                                review_text_all = await page.content()
                                for k in REVIEW_KEYWORDS:
                                    if k in review_text_all:
                                        review_keywords_list.append(k)
                                if review_keywords_list:
                                    unique = list(set(review_keywords_list))
                                    review_summary = " ".join(unique[:5])
                                else:
                                    review_summary = "特徴なし"
                            except:
                                review_summary = "取得失敗"

                        prediction = "不明"
                        reason = ""
                        tag_color = "gray"
                        if sns_score >= 1:
                            prediction = "SNS型"
                            reason = f"KW:{','.join(found_keywords)}"
                            tag_color = "#e1306c"
                        elif page_height > 25000:
                            prediction = "説得型LP"
                            reason = f"長尺"
                            tag_color = "#bf0000"
                        else:
                            prediction = "シンプル"
                            reason = f"短尺"
                            tag_color = "#555"
                        
                        all_data_list.append({
                            "category": cat_name,
                            "rank": i+1,
                            "title": title,
                            "catch_copy": catch_copy,
                            "review_url": review_url,
                            "review_summary": review_summary,
                            "type": prediction,
                            "reason": reason,
                            "url": url,
                            "img": img_filename,
                            "thumb_url": thumb_url,
                            "color": tag_color
                        })

                    except Exception as e:
                        print(f"   エラー: {e}")
                        continue
            except Exception as e:
                print(f"   カテゴリーエラー: {e}")
                continue
        
        await browser.close()

    if len(all_data_list) > 0:
        df = pd.DataFrame(all_data_list)
        csv_filename = f"rakuten_lp_list_{today_str}.csv"
        df.to_csv(os.path.join(SAVE_DIR, csv_filename), index=False, encoding="utf-8-sig")

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>楽天LP分析レポート ({today_str})</title>
            <style>
                body {{ font-family: "Helvetica Neue", Arial, sans-serif; background: #f0f2f5; padding: 20px; display: none; color: #333; }}
                h1 {{ text-align: center; margin-bottom: 30px; }}
                .nav-link {{ display:block; text-align:center; margin-bottom:20px; font-weight:bold; color:#003366; }}
                
                h2.cat-title {{ 
                    margin-top: 50px; margin-bottom: 20px; padding-left: 15px; 
                    border-left: 5px solid #bf0000; font-size: 24px; background: #fff;
                    padding: 10px 15px; border-radius: 0 5px 5px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                }}

                /* サムネイルマトリックス */
                .thumb-matrix-container {{
                    background: white; padding: 20px; border-radius: 10px; margin-bottom: 40px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
                }}
                .matrix-title {{ font-size:16px; font-weight:bold; margin-bottom:15px; color:#555; border-bottom:1px solid #eee; padding-bottom:5px; }}
                .thumb-matrix {{ 
                    display: grid; 
                    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); 
                    gap: 15px; 
                }}
                .matrix-item {{ 
                    display: flex; flex-direction: column; align-items: center; 
                    text-decoration: none; color: #333; transition: transform 0.2s;
                }}
                .matrix-item:hover {{ transform: scale(1.05); }}
                .matrix-img {{ 
                    width: 100px; height: 100px; object-fit: cover; 
                    border-radius: 8px; border: 1px solid #ddd; 
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                    background-color: #eee;
                }}
                .matrix-rank {{ 
                    margin-top: 5px; font-size: 14px; font-weight: bold; 
                    background: #bf0000; color: white; padding: 2px 8px; border-radius: 10px; 
                }}

                .gallery {{ display: flex; flex-wrap: wrap; gap: 20px; justify-content: flex-start; }}
                .card {{ background: white; width: 320px; padding: 15px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); transition: transform 0.2s; display: flex; flex-direction: column; scroll-margin-top: 20px; }}
                .card:hover {{ transform: translateY(-5px); box-shadow: 0 8px 15px rgba(0,0,0,0.15); }}
                .tag {{ display: inline-block; padding: 4px 12px; border-radius: 20px; color: white; font-size: 11px; font-weight: bold; margin-bottom: 10px; align-self: flex-start; }}
                
                .rank-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
                .rank-num {{ font-size: 16px; font-weight: bold; color: #333; }}

                .thumb-wrapper {{ cursor: zoom-in; overflow: hidden; border-radius: 6px; border: 1px solid #eee; height: 350px; position: relative; }}
                .thumb {{ width: 100%; height: 100%; object-fit: cover; object-position: top; transition: opacity 0.3s; }}
                .thumb:hover {{ opacity: 0.8; }}
                .catch-copy {{ font-size: 12px; color: #bf0000; font-weight: bold; margin: 10px 0 5px; line-height: 1.4; min-height: 34px; }}
                .title {{ font-size: 13px; margin-bottom: 10px; height: 38px; overflow: hidden; line-height: 1.4; font-weight: bold; }}
                .review-box {{ font-size: 11px; background: #eef9ff; color: #0056b3; padding: 8px; border-radius: 6px; margin-bottom: 10px; font-weight:bold; }}
                .btn-area {{ margin-top: auto; display: flex; gap: 5px; }}
                a.link {{ flex: 1; text-align: center; background: #333; color: white; text-decoration: none; font-size: 11px; padding: 10px 0; border-radius: 6px; font-weight: bold; transition: opacity 0.2s; }}
                a.review-link {{ flex: 1; text-align: center; background: #ff9900; color: white; text-decoration: none; font-size: 11px; padding: 10px 0; border-radius: 6px; font-weight: bold; transition: opacity 0.2s; }}
                a:hover {{ opacity: 0.8; }}
                .modal {{ display: none; position: fixed; z-index: 999; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.85); backdrop-filter: blur(5px); }}
                .modal-content-wrapper {{ position: relative; margin: 20px auto; width: 95%; max-width: 600px; background: white; border-radius: 8px; overflow: hidden; }}
                .modal-header {{ background: #fff; padding: 15px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 100; }}
                .close-btn {{ color: #333; font-size: 28px; font-weight: bold; cursor: pointer; line-height: 1; background: #f0f0f0; width: 40px; height: 40px; border-radius: 50%; text-align: center; display: flex; align-items: center; justify-content: center; }}
                .modal-img {{ width: 100%; display: block; }}
            </style>
            <script>
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
                function openModal(imgSrc, title) {{
                    var modal = document.getElementById("imageModal");
                    document.getElementById("modalImg").src = imgSrc;
                    document.getElementById("modalTitle").innerText = title;
                    modal.style.display = "block";
                    document.body.style.overflow = "hidden";
                }}
                function closeModal() {{
                    document.getElementById("imageModal").style.display = "none";
                    document.body.style.overflow = "auto";
                }}
                window.onclick = function(event) {{
                    if (event.target == document.getElementById("imageModal")) {{ closeModal(); }}
                }}
            </script>
        </head>
        <body>
            <h1>📅 分析レポート ({today_str})</h1>
            <div style="text-align:center; margin-bottom:20px;">
                <a href="../index.html" class="nav-link">🏠 ホームに戻る</a>
                <a href="index.html" style="color:#666; text-decoration:underline;">← 過去の日付一覧に戻る</a>
            </div>

            <div id="imageModal" class="modal">
                <div class="modal-content-wrapper">
                    <div class="modal-header">
                        <div id="modalTitle" style="font-size:14px; font-weight:bold; width:85%;"></div>
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
                
                # サムネイルマトリックスエリア
                html_content += f"""
                <div class="thumb-matrix-container">
                    <div class="matrix-title">🖼 {cat} サムネイル早見表 (1位〜{len(cat_items)}位)</div>
                    <div class="thumb-matrix">
                """
                for item in cat_items:
                    safe_cat_id = "".join(c for c in cat if c.isalnum())
                    item_id = f"{safe_cat_id}_{item['rank']}"
                    
                    thumb_src = item['thumb_url'] if item['thumb_url'] else "https://placehold.co/200x200?text=No+Img"
                    
                    html_content += f"""
                    <a href="#{item_id}" class="matrix-item">
                        <img src="{thumb_src}" class="matrix-img">
                        <span class="matrix-rank">{item['rank']}位</span>
                    </a>
                    """
                html_content += '</div></div>'

                html_content += '<div class="gallery">'
                for item in cat_items:
                    review_btn = ""
                    if item['review_url']:
                        review_btn = f'<a href="{item["review_url"]}" target="_blank" class="review-link">⭐️ レビュー</a>'
                    else:
                        review_btn = '<span style="flex:1; text-align:center; font-size:11px; padding:10px 0; color:#ccc;">(レビューなし)</span>'
                    
                    safe_cat_id = "".join(c for c in cat if c.isalnum())
                    item_id = f"{safe_cat_id}_{item['rank']}"

                    html_content += f"""
                        <div class="card" id="{item_id}">
                            <span class="tag" style="background: {item['color']}">{item['type']}</span>
                            <div class="rank-header">
                                <span class="rank-num">{item['rank']}位</span>
                            </div>
                            <div class="thumb-wrapper" onclick="openModal('{item['img']}', '{item['title']}')">
                                <img src="{item['img']}" class="thumb" loading="lazy">
                            </div>
                            <div class="catch-copy">{item['catch_copy']}</div>
                            <div class="title">{item['title'][:35]}...</div>
                            
                            <div class="review-box">💬 口コミ: {item['review_summary']}</div>
                            
                            <div class="btn-area">
                                <a href="{item['url']}" target="_blank" class="link">商品ページ</a>
                                {review_btn}
                            </div>
                        </div>
                    """
                html_content += '</div>'
        html_content += "</body></html>"

        report_filename = f"report_{today_str}.html"
        with open(os.path.join(SAVE_DIR, report_filename), "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"\n✨ レポート作成完了: {report_filename}")

        # --- アーカイブページ生成 ---
        report_files = glob.glob(os.path.join(SAVE_DIR, "report_*.html"))
        report_files.sort(reverse=True)
        
        index_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>楽天LP分析アーカイブ</title>
            <style>
                body {{ font-family: "Helvetica Neue", Arial, sans-serif; background: #f4f4f4; padding: 20px; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }}
                h1 {{ text-align: center; color: #bf0000; }}
                ul {{ list-style: none; padding: 0; }}
                li {{ margin-bottom: 15px; }}
                a.report-link {{ display: block; padding: 15px; background: #f8f9fa; border-left: 5px solid #bf0000; text-decoration: none; color: #333; font-weight: bold; transition: 0.2s; border-radius: 4px; }}
                a.report-link:hover {{ background: #bf0000; color: white; }}
                .date {{ font-size: 14px; color: #666; font-weight: normal; margin-left: 10px; }}
                .home-btn {{ display:block; text-align:center; margin-bottom:20px; font-weight:bold; color:#003366; text-decoration:none; padding:10px; background:#e0e0e0; border-radius:5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <a href="../index.html" class="home-btn">🏠 総合トップページに戻る</a>
                <h1>📚 デイリーランキング<br>画像レポート一覧</h1>
                <p style="text-align:center; margin-bottom:30px;">過去{KEEP_DAYS}日分のデータを保存中</p>
                <ul>
        """
        for filepath in report_files:
            filename = os.path.basename(filepath)
            date_str = filename.replace("report_", "").replace(".html", "")
            index_html += f"""
                <li>
                    <a href="{filename}" class="report-link">
                        📂 {date_str} のレポート
                        <span class="date">クリックして閲覧</span>
                    </a>
                </li>
            """
        index_html += "</ul></div></body></html>"
        
        with open(os.path.join(SAVE_DIR, "index.html"), "w", encoding="utf-8") as f:
            f.write(index_html)
        print("✅ アーカイブページ更新完了")

    else:
        print("\n❌ データが取れませんでした")

    # --- 総合トップページ (index.html) ---
    top_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>楽天分析ツール ポータル</title>
        <style>
            body {{ font-family: "Helvetica Neue", Arial, sans-serif; background: #f0f2f5; padding: 40px; color: #333; display: flex; justify-content: center; align-items: center; min-height: 80vh; }}
            .container {{ text-align: center; max-width: 600px; width: 100%; }}
            h1 {{ color: #bf0000; margin-bottom: 40px; font-size: 28px; }}
            .menu-grid {{ display: grid; gap: 20px; }}
            .menu-card {{ 
                background: white; padding: 30px; border-radius: 15px; 
                box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-decoration: none; color: #333; 
                transition: transform 0.2s, box-shadow 0.2s; border-left: 8px solid #ccc;
                display: flex; flex-direction: column; align-items: center;
            }}
            .menu-card:hover {{ transform: translateY(-5px); box-shadow: 0 8px 25px rgba(0,0,0,0.15); }}
            
            .card-lp {{ border-left-color: #bf0000; }}
            .card-review {{ border-left-color: #003366; }}
            
            .icon {{ font-size: 40px; margin-bottom: 10px; }}
            .card-title {{ font-size: 20px; font-weight: bold; margin-bottom: 5px; }}
            .card-desc {{ font-size: 14px; color: #666; }}
            .timestamp {{ margin-top: 40px; font-size: 12px; color: #999; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 楽天市場 分析ツール v2</h1>
            
            <div class="menu-grid">
                <a href="{SAVE_DIR}/index.html" class="menu-card card-lp">
                    <div class="icon">📊</div>
                    <div class="card-title">デイリーランキング画像</div>
                    <div class="card-desc">毎日のランキング商品LPを画像で保存・一覧化</div>
                </a>

                <a href="{REVIEW_DIR}/index.html" class="menu-card card-review">
                    <div class="icon">🧐</div>
                    <div class="card-title">レビュー深掘り分析</div>
                    <div class="card-desc">「良い点・悪い点・本音」をAIが抽出して要約</div>
                </a>
            </div>

            <div class="timestamp">最終更新: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
        </div>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(top_html)
    print("✅ 総合トップページ生成完了 (index.html)")

if __name__ == "__main__":
    asyncio.run(run_fixed())