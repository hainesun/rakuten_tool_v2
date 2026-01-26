import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import os
import datetime
import glob
import re
import random

# --- 🛠 設定エリア 🛠 ---
TARGET_CATEGORIES = {
    "🏆 総合": "https://ranking.rakuten.co.jp/daily/",
    "👗 レディースファッション": "https://ranking.rakuten.co.jp/daily/100371/",
    "👛 財布・ポーチ": "https://ranking.rakuten.co.jp/daily/216131/",
    "🛋 インテリア": "https://ranking.rakuten.co.jp/daily/100804/",
    "🍜 食品": "https://ranking.rakuten.co.jp/daily/100227/",
    "💄 美容・コスメ": "https://ranking.rakuten.co.jp/daily/100939/",
}

GET_LIMIT = 5       # 各カテゴリー5位まで
SAVE_DIR = "lp_stock"
PAGE_PASSWORD = "1234" 
KEEP_DAYS = 60      # 過去何日分を残すか
# -----------------------

SNS_KEYWORDS = ["インスタ", "Instagram", "instagram", "SNS", "インフルエンサー", "見て購入", "紹介"]

async def run():
    # 保存フォルダ作成
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    all_data_list = []
    today = datetime.date.today()
    today_str = str(today)

    # ▼▼▼ 1. お掃除機能 ▼▼▼
    print(f"\n🧹 データの整理を開始します（保存期限: {KEEP_DAYS}日）...")
    limit_date = today - datetime.timedelta(days=KEEP_DAYS)
    files = glob.glob(os.path.join(SAVE_DIR, "*"))
    for f in files:
        filename = os.path.basename(f)
        match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
        if match:
            try:
                file_date = datetime.datetime.strptime(match.group(1), "%Y-%m-%d").date()
                if file_date < limit_date:
                    os.remove(f)
            except:
                continue

    async with async_playwright() as p:
        # ★【重要】ステルス設定を追加！
        # args=['--disable-blink-features=AutomationControlled'] でロボット判定を回避します
        browser = await p.chromium.launch(
            headless=False, # まずは画面を出して確認！（動いたら True に戻してください）
            slow_mo=500,    # 少しゆっくり動く（人間っぽく）
            args=['--disable-blink-features=AutomationControlled'] 
        )
        
        context = await browser.new_context(
            viewport={'width': 390, 'height': 844},
            device_scale_factor=2,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        )
        page = await context.new_page()

        # ロボット検出回避のための追加設定
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        for cat_name, cat_url in TARGET_CATEGORIES.items():
            print(f"\n🔍 【{cat_name}】 のランキングを取得中...")
            
            try:
                # ページへ移動
                await page.goto(cat_url, timeout=90000, wait_until="domcontentloaded")
                
                # 表示待ち（長めに待つ）
                try:
                    # 商品リンクが出るまで最大30秒待つ
                    await page.wait_for_selector("a[href*='item.rakuten.co.jp']", state="attached", timeout=30000)
                    await page.wait_for_timeout(2000) 
                except:
                    print("   ⚠️ 商品リストが見つかりません（再読み込みを試します）")
                    await page.reload(wait_until="domcontentloaded")
                    await page.wait_for_timeout(5000)
                    try:
                        await page.wait_for_selector("a[href*='item.rakuten.co.jp']", state="attached", timeout=30000)
                    except:
                        print("   ❌ ダメでした。スキップします。")
                        continue

                all_links = await page.locator("a").all()
                target_urls = []
                seen_items = set()

                for link in all_links:
                    if len(target_urls) >= GET_LIMIT: break
                    try:
                        url = await link.get_attribute("href")
                        if url and "item.rakuten.co.jp" in url:
                            clean_url = url.split('?')[0]
                            if clean_url not in seen_items:
                                seen_items.add(clean_url)
                                target_urls.append(clean_url)
                    except:
                        continue
                
                print(f"   -> {len(target_urls)}個の商品リンクを確保")

                for i, url in enumerate(target_urls):
                    try:
                        print(f"   [{i+1}/{GET_LIMIT}] 分析中...")
                        await page.goto(url, timeout=90000, wait_until="domcontentloaded")
                        
                        # スクロール
                        await page.evaluate("window.scrollTo(0, 0)")
                        prev_height = -1
                        scroll_count = 0
                        while scroll_count < 15: 
                            await page.evaluate("window.scrollBy(0, 1000)")
                            await page.wait_for_timeout(800) 
                            curr_height = await page.evaluate("document.body.scrollHeight")
                            if curr_height == prev_height: break
                            prev_height = curr_height
                            scroll_count += 1
                        
                        await page.evaluate("window.scrollTo(0, 0)")
                        await page.wait_for_timeout(2000)
                        
                        # データ取得
                        title = await page.title()
                        content_text = await page.content()
                        page_height = await page.evaluate("document.body.scrollHeight")

                        review_url = ""
                        try:
                            review_link_loc = page.locator("a[href*='review.rakuten.co.jp']").first
                            if await review_link_loc.count() > 0:
                                review_url = await review_link_loc.get_attribute("href")
                        except:
                            pass
                        
                        catch_copy = ""
                        try:
                            catch_loc = page.locator(".catch_copy, .item_catch_copy, [class*='catch']").first
                            if await catch_loc.count() > 0:
                                txt = await catch_loc.text_content()
                                catch_copy = txt.strip()[:60] + "..."
                        except:
                            pass

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
                            prediction = "説得型LP"
                            reason = f"長尺({page_height}px)"
                            tag_color = "#bf0000"
                        else:
                            prediction = "シンプル型"
                            reason = f"短尺({page_height}px)"
                            tag_color = "#555"

                        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-'))[:15]
                        safe_cat_name = "".join(c for c in cat_name if c.isalnum())
                        
                        img_filename = f"{today_str}_{safe_cat_name}_{i+1}_{safe_title}.jpg"
                        img_path = os.path.join(SAVE_DIR, img_filename)
                        
                        await page.screenshot(path=img_path, full_page=True, type="jpeg", quality=70)
                        
                        all_data_list.append({
                            "category": cat_name,
                            "rank": i+1,
                            "title": title,
                            "catch_copy": catch_copy,
                            "review_url": review_url,
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

    # --- HTML生成 ---
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
                h2.cat-title {{ 
                    margin-top: 50px; margin-bottom: 20px; padding-left: 15px; 
                    border-left: 5px solid #bf0000; font-size: 24px; background: #fff;
                    padding: 10px 15px; border-radius: 0 5px 5px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                }}
                .gallery {{ display: flex; flex-wrap: wrap; gap: 20px; justify-content: flex-start; }}
                .card {{ background: white; width: 320px; padding: 15px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); transition: transform 0.2s; display: flex; flex-direction: column; }}
                .card:hover {{ transform: translateY(-5px); box-shadow: 0 8px 15px rgba(0,0,0,0.15); }}
                .tag {{ display: inline-block; padding: 4px 12px; border-radius: 20px; color: white; font-size: 11px; font-weight: bold; margin-bottom: 10px; align-self: flex-start; }}
                .thumb-wrapper {{ cursor: zoom-in; overflow: hidden; border-radius: 6px; border: 1px solid #eee; height: 350px; position: relative; }}
                .thumb {{ width: 100%; height: 100%; object-fit: cover; object-position: top; transition: opacity 0.3s; }}
                .thumb:hover {{ opacity: 0.8; }}
                .catch-copy {{ font-size: 12px; color: #bf0000; font-weight: bold; margin: 10px 0 5px; line-height: 1.4; min-height: 34px; }}
                .title {{ font-size: 13px; margin-bottom: 10px; height: 38px; overflow: hidden; line-height: 1.4; font-weight: bold; }}
                .reason {{ font-size: 11px; color: #666; background: #f8f8f8; padding: 6px; border-radius: 4px; margin-bottom: 10px; }}
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
                <a href="index.html" style="color:#666; text-decoration:underline;">← トップページ（日付一覧）に戻る</a>
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
                html_content += f'<h2 class="cat-title">{cat}</h2><div class="gallery">'
                for item in cat_items:
                    review_btn = ""
                    if item['review_url']:
                        review_btn = f'<a href="{item["review_url"]}" target="_blank" class="review-link">⭐️ レビュー</a>'
                    else:
                        review_btn = '<span style="flex:1; text-align:center; font-size:11px; padding:10px 0; color:#ccc;">(レビューなし)</span>'
                    html_content += f"""
                        <div class="card">
                            <span class="tag" style="background: {item['color']}">{item['type']}</span>
                            <div class="thumb-wrapper" onclick="openModal('{item['img']}', '{item['title']}')">
                                <img src="{item['img']}" class="thumb" loading="lazy">
                            </div>
                            <div class="catch-copy">{item['catch_copy']}</div>
                            <div class="title"><b>{item['rank']}位:</b> {item['title'][:35]}...</div>
                            <div class="reason">💡 {item['reason']}</div>
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
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📚 LP分析レポート一覧</h1>
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
        print("✅ トップページ更新完了")

    else:
        print("\n❌ データが取れませんでした")

if __name__ == "__main__":
    asyncio.run(run())