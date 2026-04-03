import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import os
import datetime
import glob
import re

# --- 🛠 設定エリア 🛠 ---
TARGET_CATEGORIES = {
    "👛 レディース財布(デイリー)": "https://ranking.rakuten.co.jp/daily/502368/",
    "💼 メンズ財布(デイリー)": "https://ranking.rakuten.co.jp/daily/552710/",
    "🛋 インテリア(デイリー)": "https://ranking.rakuten.co.jp/daily/100804/",
    "🍳 キッチン用品(デイリー)": "https://ranking.rakuten.co.jp/daily/558944/",
    "💄 美容・コスメ(デイリー)": "https://ranking.rakuten.co.jp/daily/100939/",
}
GET_LIMIT = 10
LP_LIMIT = 5
SAVE_DIR = "lp_stock"
REVIEW_DIR = "review_report"
KEEP_DAYS = 60

REVIEW_KEYWORDS = [
    "早い", "遅い", "丁寧", "雑", "可愛い", "かわいい", "おしゃれ", "シンプル", "高見え", "安っぽい",
    "使いやすい", "便利", "軽い", "重い", "小さい", "大きい", "リピ", "プレゼント", "満足", "残念", 
    "おすすめ", "サイズ感", "ちょうどいい", "到着", "リピート", "美味", "不味", "香り", "肌触り", 
    "柔らかい", "硬い", "コスパ", "お得", "セール", "割引", "値上げ", "値下げ"
]
SNS_KEYWORDS = ["インスタ", "Instagram", "instagram", "SNS", "インフルエンサー", "見て購入", "紹介"]

def log(text): print(text, flush=True)

def create_review_report(all_data, date_str):
    if not os.path.exists(REVIEW_DIR): os.makedirs(REVIEW_DIR)
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="robots" content="noindex"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>レビュー深掘り分析 ({date_str})</title><style>body {{ font-family: "Helvetica Neue", Arial, sans-serif; background: #f4f7f6; padding: 20px; color: #333; }} h1 {{ text-align: center; color: #003366; }} .nav-area {{ text-align: center; margin-bottom: 30px; }} .nav-btn {{ display: inline-block; margin: 5px; padding: 10px 20px; background: #fff; color: #003366; text-decoration: none; border-radius: 20px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.1); transition: 0.2s; }} .nav-btn:hover {{ transform: translateY(-2px); box-shadow: 0 5px 10px rgba(0,0,0,0.15); }} .container {{ max-width: 800px; margin: 0 auto; }} .item-box {{ background: white; padding: 25px; margin-bottom: 25px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }} .cat-name {{ font-size: 12px; color: #666; background: #eee; display: inline-block; padding: 2px 8px; border-radius: 4px; margin-bottom: 8px; }} .item-title {{ font-weight: bold; font-size: 16px; margin-bottom: 12px; color: #333; line-height: 1.5; }} .review-tag {{ display: inline-block; background: #eef9ff; color: #0056b3; padding: 5px 10px; border-radius: 15px; font-size: 12px; margin-right: 5px; margin-bottom: 5px; border: 1px solid #cceeff; }} .link-btn {{ display: inline-block; margin-top: 15px; text-decoration: none; color: white; background: #ff9900; padding: 8px 25px; border-radius: 5px; font-size: 13px; font-weight: bold; transition: opacity 0.2s; }} .link-btn:hover {{ opacity: 0.8; }} .reason-box {{ font-size:13px; color:#555; background:#fafafa; padding:15px; border-radius:8px; margin-top:15px; border-left: 4px solid #003366; }}</style></head><body><h1>🧐 レビュー深掘り分析 ({date_str})</h1><div class="nav-area"><a href="../index.html" class="nav-btn">🏠 ホームに戻る</a><a href="index.html" class="nav-btn">📂 過去の日付一覧に戻る</a></div><div class="container">"""
    for item in all_data:
        if not item.get('is_full'): continue
        keywords_html = "".join([f'<span class="review-tag">{k}</span>' for k in item['review_summary'].split(" ")]) if item['review_summary'] and item['review_summary'] != "なし" else '<span style="color:#999; font-size:12px;">特徴的なキーワードなし</span>'
        html += f"""<div class="item-box"><div class="cat-name">{item['category']} {item['rank']}位</div><div class="item-title">{item['title']}</div><div style="margin:10px 0;"><div style="font-size:12px; font-weight:bold; margin-bottom:5px; color:#666;">抽出キーワード</div>{keywords_html}</div><div class="reason-box">💡 <b>AI分析メモ:</b><br>{item['reason']}</div>{f'<div style="text-align:right;"><a href="{item["review_url"]}" target="_blank" class="link-btn">実際のレビューを見る</a></div>' if item['review_url'] else ''}</div>"""
    html += "</div></body></html>"
    with open(os.path.join(REVIEW_DIR, f"report_{date_str}.html"), "w", encoding="utf-8") as f: f.write(html)
    
    files = sorted(glob.glob(os.path.join(REVIEW_DIR, "report_*.html")), reverse=True)
    idx = """<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="robots" content="noindex"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>レビュー分析アーカイブ</title><style>body { font-family: "Helvetica Neue", Arial, sans-serif; padding: 20px; background: #f4f7f6; color: #333; } .container { max-width: 600px; margin: 0 auto; } h1 { text-align: center; color: #003366; margin-bottom: 30px; } .home-btn { display: block; width: fit-content; margin: 0 auto 30px; padding: 10px 20px; background: #fff; color: #333; text-decoration: none; border-radius: 20px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.1); } .list-group { list-style: none; padding: 0; } .list-item { margin-bottom: 15px; } .report-link { display: block; padding: 20px; background: #fff; border-radius: 10px; text-decoration: none; color: #333; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.05); transition: 0.2s; border-left: 6px solid #003366; } .report-link:hover { transform: translateY(-3px); box-shadow: 0 5px 15px rgba(0,0,0,0.1); } .date-text { font-size: 18px; } .arrow { float: right; color: #ccc; }</style></head><body><div class="container"><h1>🧐 レビュー分析アーカイブ</h1><a href="../index.html" class="home-btn">🏠 ホームに戻る</a><ul class="list-group">"""
    for p in files:
        fname = os.path.basename(p)
        idx += f'<li class="list-item"><a href="{fname}" class="report-link"><span class="date-text">📂 {fname.replace("report_", "").replace(".html", "")} の分析レポート</span><span class="arrow">→</span></a></li>'
    idx += "</ul></div></body></html>"
    with open(os.path.join(REVIEW_DIR, "index.html"), "w", encoding="utf-8") as f: f.write(idx)

async def run_fixed():
    if not os.path.exists(SAVE_DIR): os.makedirs(SAVE_DIR)
    if not os.path.exists(REVIEW_DIR): os.makedirs(REVIEW_DIR)
    all_data_list = []
    today_str = str(datetime.date.today())
    limit_date = datetime.date.today() - datetime.timedelta(days=KEEP_DAYS)

    for d in [SAVE_DIR, REVIEW_DIR]:
        for f in glob.glob(os.path.join(d, "*")):
            match = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(f))
            if match and datetime.datetime.strptime(match.group(1), "%Y-%m-%d").date() < limit_date: os.remove(f)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500, args=['--disable-blink-features=AutomationControlled'])
        pc_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        mobile_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        
        for cat_name, cat_url in TARGET_CATEGORIES.items():
            log(f"\n🔍 【{cat_name}】...")
            context_pc = await browser.new_context(viewport={'width': 1280, 'height': 800}, user_agent=pc_ua)
            page_pc = await context_pc.new_page()
            target_items = []
            try:
                await page_pc.goto(cat_url, timeout=60000, wait_until="domcontentloaded")
                await page_pc.evaluate("window.scrollBy(0, 1000)")
                await page_pc.wait_for_timeout(2000)
                links = await page_pc.locator("div.rnkRanking_image a[href*='item.rakuten.co.jp'], div.rnkRanking_after a[href*='item.rakuten.co.jp']").all()
                imgs = await page_pc.locator("div.rnkRanking_image img, div.rnkRanking_after img").all()
                seen = set()
                for i, link in enumerate(links):
                    if len(target_items) >= GET_LIMIT: break
                    u = await link.get_attribute("href")
                    if u and "item.rakuten.co.jp" in u:
                        clean = u.split('?')[0]
                        if clean not in seen:
                            seen.add(clean)
                            t_src = ""
                            if i < len(imgs):
                                t_src = await imgs[i].get_attribute("src") or await imgs[i].get_attribute("data-src")
                                if t_src and "?_ex=" in t_src: t_src = t_src.split("?_ex=")[0] + "?_ex=200x200"
                            target_items.append({"url": clean, "thumb": t_src})
            except: pass
            finally: await context_pc.close()

            context_mo = await browser.new_context(viewport={'width': 390, 'height': 8000}, user_agent=mobile_ua, is_mobile=True, has_touch=True)
            page_mo = await context_mo.new_page()
            
            for i, item in enumerate(target_items):
                rank = i + 1
                is_full = rank <= LP_LIMIT
                res = {"category": cat_name, "rank": rank, "url": item['url'], "thumb_url": item['thumb'], "is_full": is_full, "title": "", "catch_copy": "", "review_url": "", "review_summary": "なし", "type": "－", "reason": "", "img": "", "color": "#ccc"}
                try:
                    await page_mo.goto(item['url'], timeout=60000, wait_until="domcontentloaded")
                    res['title'] = await page_mo.title()
                    if is_full:
                        try:
                            for sel in ["button[class*='close']", "div[class*='close']", ".rbs-overlay-close", "[aria-label='Close']", "#SC_DefaultClose"]:
                                if await page_mo.locator(sel).count() > 0:
                                    for btn in await page_mo.locator(sel).all():
                                        if await btn.is_visible(): await btn.click()
                        except: pass
                        safe_cat = "".join(c for c in cat_name if c.isalnum())
                        img_name = f"{today_str}_{safe_cat}_rank{rank}.jpg"
                        await page_mo.screenshot(path=os.path.join(SAVE_DIR, img_name), type="jpeg", quality=50, full_page=True)
                        res['img'] = img_name
                        content = await page_mo.content()
                        page_height = await page_mo.evaluate("document.body.scrollHeight")
                        if any(k in content for k in SNS_KEYWORDS): res['type'] = "SNS型"; res['color'] = "#e1306c"; res['reason'] = "SNSキーワードあり"
                        elif page_height > 20000: res['type'] = "説得型LP"; res['color'] = "#bf0000"; res['reason'] = "長尺LP (説得型)"
                        else: res['type'] = "シンプル"; res['color'] = "#555"; res['reason'] = "短尺 (シンプル)"
                        try:
                            rev_link = page_mo.locator("a[href*='review.rakuten.co.jp']").first
                            if await rev_link.count() > 0: res['review_url'] = await rev_link.get_attribute("href")
                        except: pass
                        if res['review_url']:
                            try:
                                await page_mo.goto(res['review_url'], timeout=30000)
                                r_txt = await page_mo.content()
                                f_kws = list(set([k for k in REVIEW_KEYWORDS if k in r_txt]))
                                res['review_summary'] = " ".join(f_kws[:5]) if f_kws else "特徴なし"
                                res['reason'] += f" | レビューKW: {','.join(f_kws[:5])}"
                            except: pass
                except: pass
                all_data_list.append(res)
            await context_mo.close()
        await browser.close()

    if all_data_list:
        pd.DataFrame(all_data_list).to_csv(os.path.join(SAVE_DIR, f"rakuten_lp_list_{today_str}.csv"), index=False, encoding="utf-8-sig")
        create_review_report(all_data_list, today_str)

        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="robots" content="noindex, nofollow"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>楽天LP分析 ({today_str})</title><style>body {{ font-family: "Helvetica Neue", Arial, sans-serif; background: #f0f2f5; padding: 20px; color: #333; }} h1 {{ text-align: center; margin-bottom: 20px; }} .nav-area {{ text-align: center; margin-bottom: 30px; }} .nav-btn {{ display: inline-block; margin: 5px; padding: 10px 20px; background: #fff; color: #bf0000; text-decoration: none; border-radius: 20px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.1); transition: 0.2s; }} .nav-btn:hover {{ transform: translateY(-2px); box-shadow: 0 5px 10px rgba(0,0,0,0.15); }} .thumb-matrix {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 10px; background: white; padding: 15px; border-radius: 10px; margin-bottom: 30px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }} .matrix-item {{ display: flex; flex-direction: column; align-items: center; text-decoration: none; color: #333; font-size: 12px; position: relative; transition: transform 0.2s; }} .matrix-item:hover {{ transform: scale(1.05); }} .matrix-img {{ width: 100px; height: 100px; object-fit: cover; border-radius: 8px; border: 1px solid #ddd; }} .matrix-ext {{ position: absolute; top: 0; right: 0; background: #333; color: white; font-size: 9px; padding: 2px 4px; opacity: 0.8; border-radius: 0 8px 0 4px; }} .gallery {{ display: flex; flex-wrap: wrap; gap: 20px; justify-content: flex-start; }} .card {{ background: white; width: 320px; padding: 15px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); display: flex; flex-direction: column; }} .rank-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }} .thumb-wrapper {{ height: 350px; overflow: hidden; border: 1px solid #eee; cursor: zoom-in; border-radius: 6px; }} .thumb {{ width: 100%; transition: opacity 0.3s; }} .thumb:hover {{ opacity: 0.8; }} .modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 999; backdrop-filter: blur(5px); }} .modal-content {{ position: relative; margin: 30px auto; width: 90%; max-width: 450px; height: 90vh; background: white; overflow-y: auto; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }} .close {{ position: sticky; top: 0; right: 0; background: #fff; padding: 15px; text-align: right; font-size: 24px; cursor: pointer; border-bottom: 1px solid #eee; z-index: 100; }}</style><script>function openModal(src){{document.getElementById('mImg').src=src;document.getElementById('modal').style.display='block';document.body.style.overflow='hidden';}} function closeModal(){{document.getElementById('modal').style.display='none';document.body.style.overflow='auto';}}</script></head><body><h1>📅 LP分析 ({today_str})</h1><div class="nav-area"><a href="../index.html" class="nav-btn">🏠 ホームに戻る</a><a href="index.html" class="nav-btn">📂 過去の日付一覧に戻る</a></div><div id="modal" class="modal" onclick="closeModal()"><div class="modal-content" onclick="event.stopPropagation()"><div class="close" onclick="closeModal()">×</div><img id="mImg" style="width:100%;"></div></div>"""
        for cat in TARGET_CATEGORIES.keys():
            items = [x for x in all_data_list if x['category'] == cat]
            if not items: continue
            html += f"<h2>{cat}</h2><div class='thumb-matrix'>"
            for it in items:
                link = f"#{''.join(c for c in cat if c.isalnum())}_{it['rank']}" if it['is_full'] else it['url']
                target = "" if it['is_full'] else 'target="_blank"'
                ext = "<span class='matrix-ext'>楽天↗</span>" if not it['is_full'] else ""
                html += f"<a href='{link}' class='matrix-item' {target}><img src='{it['thumb_url'] or 'https://placehold.co/100'}' class='matrix-img'><span>{it['rank']}位</span>{ext}</a>"
            html += "</div><div class='gallery'>"
            for it in items:
                if not it['is_full']: continue
                rid = "".join(c for c in cat if c.isalnum()) + f"_{it['rank']}"
                html += f"""<div class="card" id="{rid}"><div class="rank-header"><strong style="font-size:18px;">{it['rank']}位</strong><span style="background:{it['color']};color:white;padding:3px 8px;border-radius:10px;font-size:11px;font-weight:bold;">{it['type']}</span></div><div class="thumb-wrapper" onclick="openModal('{it['img']}')"><img src="{it['img']}" class="thumb"></div><div style="font-size:13px; margin:10px 0; font-weight:bold; line-height:1.4;">{it['title'][:40]}...</div><div style="background:#f0f8ff; padding:8px; font-size:11px; color:#0056b3; border-radius:5px; margin-bottom:10px;">💬 {it['review_summary']}</div><div style="display:flex; gap:5px; margin-top:auto;"><a href="{it['url']}" target="_blank" style="flex:1; text-align:center; background:#333; color:white; padding:10px 0; border-radius:5px; text-decoration:none; font-size:12px; font-weight:bold;">商品ページ</a>{f'<a href="{it["review_url"]}" target="_blank" style="flex:1; text-align:center; background:#f90; color:white; padding:10px 0; border-radius:5px; text-decoration:none; font-size:12px; font-weight:bold;">レビュー</a>' if it['review_url'] else ''}</div></div>"""
            html += "</div>"
        html += "</body></html>"
        with open(os.path.join(SAVE_DIR, f"report_{today_str}.html"), "w", encoding="utf-8") as f: f.write(html)
        
        files = sorted(glob.glob(os.path.join(SAVE_DIR, "report_*.html")), reverse=True)
        idx = """<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="robots" content="noindex"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>LPアーカイブ</title><style>body { font-family: "Helvetica Neue", Arial, sans-serif; padding: 20px; background: #f4f7f6; color: #333; } .container { max-width: 600px; margin: 0 auto; } h1 { text-align: center; color: #bf0000; margin-bottom: 30px; } .home-btn { display: block; width: fit-content; margin: 0 auto 30px; padding: 10px 20px; background: #fff; color: #333; text-decoration: none; border-radius: 20px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.1); } .list-group { list-style: none; padding: 0; } .list-item { margin-bottom: 15px; } .report-link { display: block; padding: 20px; background: #fff; border-radius: 10px; text-decoration: none; color: #333; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.05); transition: 0.2s; border-left: 6px solid #bf0000; } .report-link:hover { transform: translateY(-3px); box-shadow: 0 5px 15px rgba(0,0,0,0.1); } .date-text { font-size: 18px; } .arrow { float: right; color: #ccc; }</style></head><body><div class="container"><h1>📚 LPアーカイブ</h1><a href="../index.html" class="home-btn">🏠 ホームに戻る</a><ul class="list-group">"""
        for p in files:
            fname = os.path.basename(p)
            idx += f'<li class="list-item"><a href="{fname}" class="report-link"><span class="date-text">📂 {fname.replace("report_", "").replace(".html", "")} のレポート</span><span class="arrow">→</span></a></li>'
        idx += "</ul></div></body></html>"
        with open(os.path.join(SAVE_DIR, "index.html"), "w", encoding="utf-8") as f: f.write(idx)
        
    log("✅ 全工程完了！")

if __name__ == "__main__":
    asyncio.run(run_fixed())