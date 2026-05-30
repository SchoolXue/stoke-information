import customtkinter as ctk
import yfinance as yf
from threading import Thread
import webbrowser
from deep_translator import GoogleTranslator
import mplfinance as mpf
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib
import json
import os
import requests

# Set matplotlib to aggressive backend for thread safety
matplotlib.use('Agg')

# Initialize CustomTkinter (Force Dark Mode)
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(data, fast=12, slow=26, signal=9):
    exp1 = data['Close'].ewm(span=fast, adjust=False).mean()
    exp2 = data['Close'].ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def resolve_symbol(query):
    if all(ord(c) < 128 for c in query):
        return query
    try:
        url = f"https://tw.stock.yahoo.com/_td-stock/api/resource/AutocompleteService;query={query}"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).json()
        results = res.get('ResultSet', {}).get('Result', [])
        for r in results:
            if r['type'] == 'S' and r['exch'] in ['TAI', 'TWO']:
                if "購" not in r['name'] and "售" not in r['name'] and "牛" not in r['name'] and "熊" not in r['name']:
                    return r['symbol']
        translator = GoogleTranslator(source='zh-TW', target='en')
        translated = translator.translate(query)
        url_en = f"https://tw.stock.yahoo.com/_td-stock/api/resource/AutocompleteService;query={translated}"
        res_en = requests.get(url_en, headers={'User-Agent': 'Mozilla/5.0'}).json()
        results_en = res_en.get('ResultSet', {}).get('Result', [])
        for r in results_en:
            if r['type'] == 'S':
                return r['symbol']
    except Exception:
        pass
    return query

class StockApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("股票資訊查詢與技術分析系統")
        self.geometry("900x950")
        self.eval('tk::PlaceWindow . center')

        # History setup
        self.history_file = "search_history.json"
        self.search_history = self.load_history()

        # Title Label
        self.title_label = ctk.CTkLabel(self, text="📊 股票即時資訊與技術分析", font=ctk.CTkFont(family="Microsoft JhengHei", size=26, weight="bold"))
        self.title_label.pack(pady=(15, 5))

        # Input Frame
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.pack(pady=5, padx=20, fill="x")

        self.entry = ctk.CTkEntry(self.input_frame, placeholder_text="請輸入代號 (例如: AAPL 或 2330)", font=ctk.CTkFont(family="Microsoft JhengHei", size=16), height=40)
        self.entry.pack(side="left", padx=(10, 10), fill="x", expand=True)
        self.entry.bind("<Return>", lambda event: self.query_stock())

        self.search_btn = ctk.CTkButton(self.input_frame, text="查詢", width=90, height=40, font=ctk.CTkFont(family="Microsoft JhengHei", size=16, weight="bold"), command=self.query_stock)
        self.search_btn.pack(side="right", padx=(0, 10))

        # History Frame
        self.history_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.history_frame.pack(pady=(0, 5), padx=30, fill="x")
        self.history_buttons_frame = ctk.CTkFrame(self.history_frame, fg_color="transparent")
        self.history_buttons_frame.pack(side="left")
        
        self.update_history_ui()

        self.status_label = ctk.CTkLabel(self, text="請輸入股票代號並點擊查詢", font=ctk.CTkFont(family="Microsoft JhengHei", size=15), text_color="gray")
        self.status_label.pack(pady=(0, 5))

        # Scrollable Result Frame
        self.scroll_frame = ctk.CTkScrollableFrame(self, corner_radius=15, fg_color="#121212")
        self.scroll_frame.pack(pady=5, padx=20, fill="both", expand=True)

    def load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_history(self, symbol):
        if symbol in self.search_history:
            self.search_history.remove(symbol)
        self.search_history.insert(0, symbol)
        self.search_history = self.search_history[:10]  # Keep last 10
        
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.search_history, f, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save history: {e}")
            
        self.after(0, self.update_history_ui)

    def update_history_ui(self):
        for widget in self.history_buttons_frame.winfo_children():
            widget.destroy()
            
        if self.search_history:
            ctk.CTkLabel(self.history_buttons_frame, text="歷史紀錄: ", font=ctk.CTkFont(family="Microsoft JhengHei", size=13)).pack(side="left", padx=(0, 5))
            for sym in self.search_history:
                btn = ctk.CTkButton(self.history_buttons_frame, text=sym, width=40, height=24, 
                                    font=ctk.CTkFont(family="Microsoft JhengHei", size=12),
                                    command=lambda s=sym: self.quick_search(s))
                btn.pack(side="left", padx=2)

    def quick_search(self, symbol):
        self.entry.delete(0, 'end')
        self.entry.insert(0, symbol)
        self.query_stock()

    def clear_results(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

    def format_large_number(self, num):
        if num is None:
            return "N/A"
        try:
            num = float(num)
            if num >= 1e12:
                return f"{num/1e12:.2f} 兆"
            elif num >= 1e8:
                return f"{num/1e8:.2f} 億"
            elif num >= 1e4:
                return f"{num/1e4:.2f} 萬"
            else:
                return f"{num:,.2f}"
        except:
            return str(num)

    def query_stock(self):
        symbol = self.entry.get().strip().upper()
        if not symbol:
            return

        self.save_history(symbol)

        self.search_btn.configure(state="disabled")
        self.status_label.configure(text=f"正在查詢 {symbol} 的資料，這可能需要幾秒鐘...", text_color="#E67E22")
        self.clear_results()

        Thread(target=self._fetch_data, args=(symbol,), daemon=True).start()

    def _fetch_data(self, raw_symbol):
        symbol = resolve_symbol(raw_symbol)
        is_tw = False
        if symbol.isdigit():
            symbol = f"{symbol}.TW"
            is_tw = True
        elif ".TW" in symbol or ".TWO" in symbol:
            is_tw = True

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if (not info or ('currentPrice' not in info and 'regularMarketPrice' not in info and 'previousClose' not in info)) and is_tw:
                symbol = f"{raw_symbol}.TWO"
                ticker = yf.Ticker(symbol)
                info = ticker.info

            if not info or ('currentPrice' not in info and 'regularMarketPrice' not in info and 'previousClose' not in info):
                self.after(0, self._show_error, f"找不到 {raw_symbol} 的資料，請確認代號是否正確。")
                return

            # Basic Data
            industry_en = info.get('industryDisp') or info.get('industry') or info.get('sectorDisp') or info.get('sector', '未知產業')
            try:
                industry_zh = GoogleTranslator(source='auto', target='zh-TW').translate(industry_en) if industry_en != '未知產業' else industry_en
            except:
                industry_zh = industry_en

            data = {
                "symbol": symbol,
                "name": info.get('shortName', info.get('longName', symbol)),
                "currency": info.get('currency', 'TWD' if is_tw else 'USD'),
                "price": info.get('currentPrice') or info.get('previousClose') or info.get('regularMarketPrice', 'N/A'),
                "eps": info.get('trailingEps', 'N/A'),
                "pe": info.get('trailingPE', 'N/A'),
                "margin": info.get('grossMargins'),
                "revenue": info.get('totalRevenue'),
                "market_cap": info.get('marketCap'),
                "high_low": f"{info.get('fiftyTwoWeekHigh', 'N/A')} / {info.get('fiftyTwoWeekLow', 'N/A')}",
                "industry": industry_zh,
            }
            
            # Peers Data
            industry_key = info.get('industryKey')
            peer_data = []
            if industry_key:
                try:
                    region = "TW" if is_tw else "US"
                    ind = yf.Industry(industry_key, region=region)
                    peer_symbols = ind.top_companies.index.tolist() if hasattr(ind, 'top_companies') else []
                    peer_symbols = [p for p in peer_symbols if p != symbol][:5]
                    
                    if peer_symbols:
                        translator = GoogleTranslator(source='auto', target='zh-TW')
                        for p in peer_symbols:
                            p_ticker = yf.Ticker(p)
                            p_info = p_ticker.info
                            p_price = p_info.get('currentPrice') or p_info.get('previousClose') or p_info.get('regularMarketPrice', 'N/A')
                            p_name = p_info.get('shortName', p_info.get('longName', p))
                            try:
                                p_name = translator.translate(p_name)
                            except:
                                pass
                                
                            change_str = "N/A"
                            try:
                                hist = p_ticker.history(period="3mo")
                                if not hist.empty and len(hist) > 1:
                                    old_price = hist['Close'].iloc[0]
                                    curr_close = hist['Close'].iloc[-1]
                                    if old_price > 0:
                                        change_pct = ((curr_close - old_price) / old_price) * 100
                                        change_str = f"▲ +{change_pct:.1f}%" if change_pct >= 0 else f"▼ {change_pct:.1f}%"
                            except:
                                pass
                                
                            peer_data.append({'symbol': p, 'name': p_name, 'price': p_price, 'change_3mo': change_str})
                except Exception as e:
                    print(f"Failed to fetch peers: {e}")
            
            data["peers"] = peer_data
            
            # Historical Data for K-line & Technical Analysis
            df = ticker.history(period="6mo")
            
            # Analyst Recommendations
            recs = []
            mean_target = info.get('targetMeanPrice')
            try:
                upgrades = ticker.upgrades_downgrades
                if upgrades is not None and not upgrades.empty:
                    latest_upgrades = upgrades.head(8)
                    for idx, row in latest_upgrades.iterrows():
                        firm = row.get('Firm', 'Unknown')
                        grade = row.get('ToGrade', '')
                        target = row.get('currentPriceTarget')
                        if pd.isna(target):
                            target = row.get('priorPriceTarget')
                        target_val = f"{target:.2f} {data['currency']}" if pd.notna(target) else "未公開"
                        recs.append(f"• {firm} ({grade}) - 目標價：{target_val}")
            except:
                pass
            
            if not recs and mean_target:
                recs.append(f"• 市場平均目標價：{mean_target:.2f} {data['currency']}")

            # Calendar
            try:
                calendar = ticker.calendar
            except:
                calendar = {}
                
            # News with AI Translation
            try:
                raw_news = ticker.news
                news_data = []
                translator = GoogleTranslator(source='auto', target='zh-TW')
                
                for n in raw_news[:4]:
                    content = n.get('content', {})
                    if not content:
                        continue
                    
                    orig_title = content.get('title', '無標題')
                    orig_summary = content.get('summary', '')
                    
                    try:
                        zh_title = translator.translate(orig_title)
                    except:
                        zh_title = orig_title
                    try:
                        zh_summary = translator.translate(orig_summary) if orig_summary else "無摘要"
                    except:
                        zh_summary = orig_summary or "無摘要"

                    pub_time = content.get('pubDate', '')[:10]
                    provider = content.get('provider', {}).get('displayName', '未知')
                    url = content.get('clickThroughUrl', {}).get('url') or content.get('canonicalUrl', {}).get('url', '')
                        
                    news_data.append({
                        'title': zh_title, 'summary': zh_summary,
                        'pub_time': pub_time, 'provider': provider, 'url': url
                    })
            except:
                news_data = []

            self.after(0, self._render_results, data, df, recs, calendar, news_data)

        except Exception as e:
            self.after(0, self._show_error, f"發生錯誤：\n{str(e)}")

    def _show_error(self, error_msg):
        self.search_btn.configure(state="normal")
        self.status_label.configure(text="查詢失敗", text_color="#E74C3C")
        error_lbl = ctk.CTkLabel(self.scroll_frame, text=error_msg, text_color="#E74C3C", font=ctk.CTkFont(family="Microsoft JhengHei", size=16), justify="left")
        error_lbl.pack(pady=20, padx=20, anchor="w")

    def _render_results(self, data, df, recs, calendar, news):
        self.search_btn.configure(state="normal")
        self.status_label.configure(text="查詢成功！", text_color="#2ECC71")

        # 1. Basic Info Section
        info_frame = ctk.CTkFrame(self.scroll_frame, corner_radius=10, fg_color="#1E1E1E")
        info_frame.pack(fill="x", pady=(0, 10), padx=5)
        
        name_lbl = ctk.CTkLabel(info_frame, text=f"🏷️ {data['name']} ({data['symbol']})", font=ctk.CTkFont(family="Microsoft JhengHei", size=20, weight="bold"))
        name_lbl.pack(pady=(15, 5), padx=15, anchor="w")
        
        if data.get('industry'):
            ind_lbl = ctk.CTkLabel(info_frame, text=f"🏭 產業類別：{data['industry']}", font=ctk.CTkFont(family="Microsoft JhengHei", size=14), text_color="#AAB7B8")
            ind_lbl.pack(pady=(0, 5), padx=15, anchor="w")
        
        price_lbl = ctk.CTkLabel(info_frame, text=f"💵 最新收盤價：{data['price']} {data['currency']}", font=ctk.CTkFont(family="Microsoft JhengHei", size=18, weight="bold"), text_color="#F1C40F")
        price_lbl.pack(pady=(0, 10), padx=15, anchor="w")

        metrics_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        metrics_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        margin_str = f"{data['margin']*100:.2f}%" if data['margin'] else "N/A"
        pe_str = f"{data['pe']:.2f}" if data['pe'] != "N/A" else "N/A"

        metrics = [
            ("📈 近一年 EPS", str(data['eps'])),
            ("⚖️ 本益比 (P/E)", pe_str),
            ("💰 毛利率", margin_str),
            ("📦 近一年營收", f"{self.format_large_number(data['revenue'])} {data['currency']}"),
            ("🏢 市值", f"{self.format_large_number(data['market_cap'])} {data['currency']}"),
            ("📉 52週最高/最低", data['high_low'])
        ]

        for i, (label, val) in enumerate(metrics):
            lbl = ctk.CTkLabel(metrics_frame, text=f"{label}： {val}", font=ctk.CTkFont(family="Microsoft JhengHei", size=14))
            lbl.grid(row=i//2, column=i%2, sticky="w", padx=(0, 30), pady=3)

        # 1.5 Peers Section
        if data.get('peers'):
            peers_frame = ctk.CTkFrame(self.scroll_frame, corner_radius=10, fg_color="#1E1E1E")
            peers_frame.pack(fill="x", pady=5, padx=5)
            
            p_title = ctk.CTkLabel(peers_frame, text="🤝 同產業其他公司", font=ctk.CTkFont(family="Microsoft JhengHei", size=18, weight="bold"), text_color="#E67E22")
            p_title.pack(pady=(10, 5), padx=15, anchor="w")
            
            peers_btn_frame = ctk.CTkFrame(peers_frame, fg_color="transparent")
            peers_btn_frame.pack(fill="x", padx=15, pady=(0, 10))
            
            for peer in data['peers']:
                p_text = f"{peer['name']}\n{peer['price']} {data['currency']}\n3個月: {peer['change_3mo']}"
                
                t_color = "white"
                if "▲" in peer['change_3mo']:
                    t_color = "#E74C3C" if data['currency'] == 'TWD' else "#2ECC71"
                elif "▼" in peer['change_3mo']:
                    t_color = "#2ECC71" if data['currency'] == 'TWD' else "#E74C3C"

                btn = ctk.CTkButton(peers_btn_frame, text=p_text, 
                                    font=ctk.CTkFont(family="Microsoft JhengHei", size=13),
                                    fg_color="#2B2B2B", hover_color="#3A3A3A",
                                    text_color=t_color, border_width=1, border_color="#444444",
                                    command=lambda s=peer['symbol']: self.quick_search(s))
                btn.pack(side="left", padx=(0, 8), fill="x", expand=True)

        # 2. Analyst Recommendations Section
        if recs:
            rec_frame = ctk.CTkFrame(self.scroll_frame, corner_radius=10, fg_color="#1E1E1E")
            rec_frame.pack(fill="x", pady=5, padx=5)
            
            r_title = ctk.CTkLabel(rec_frame, text="💼 外資與投信投資建議與目標價", font=ctk.CTkFont(family="Microsoft JhengHei", size=18, weight="bold"), text_color="#3498DB")
            r_title.pack(pady=(10, 5), padx=15, anchor="w")
            
            for r in recs:
                lbl = ctk.CTkLabel(rec_frame, text=r, font=ctk.CTkFont(family="Microsoft JhengHei", size=14))
                lbl.pack(padx=20, pady=2, anchor="w")
            ctk.CTkFrame(rec_frame, height=10, fg_color="transparent").pack()

        # 3. K-line Chart & Technical Analysis Section
        if df is not None and not df.empty:
            chart_frame = ctk.CTkFrame(self.scroll_frame, corner_radius=10, fg_color="#1E1E1E")
            chart_frame.pack(fill="x", pady=5, padx=5)
            
            c_title = ctk.CTkLabel(chart_frame, text="📈 K線圖與技術分析 (MA, RSI, MACD)", font=ctk.CTkFont(family="Microsoft JhengHei", size=18, weight="bold"), text_color="#9B59B6")
            c_title.pack(pady=(10, 0), padx=15, anchor="w")

            try:
                df['RSI'] = calculate_rsi(df)
                macd, signal = calculate_macd(df)
                df['MACD'] = macd
                df['Signal'] = signal
                
                apds = [
                    mpf.make_addplot(df['RSI'], panel=2, color='lime', ylabel='RSI', secondary_y=False),
                    mpf.make_addplot(df['MACD'], panel=3, color='fuchsia', ylabel='MACD', secondary_y=False),
                    mpf.make_addplot(df['Signal'], panel=3, color='b', secondary_y=False)
                ]
                
                mc = mpf.make_marketcolors(up='#2ECC71', down='#E74C3C', inherit=True)
                s  = mpf.make_mpf_style(marketcolors=mc, base_mpf_style='nightclouds', facecolor='#1E1E1E', edgecolor='white', figcolor='#1E1E1E', gridcolor='#333333')
                
                fig, axes = mpf.plot(df, type='candle', volume=True, style=s, returnfig=True, mav=(5, 20),
                                     figratio=(10, 7), figscale=0.9, addplot=apds)
                
                # Make labels white
                for ax in axes:
                    ax.tick_params(colors='white')
                    ax.yaxis.label.set_color('white')
                
                canvas = FigureCanvasTkAgg(fig, master=chart_frame)
                canvas.draw()
                widget = canvas.get_tk_widget()
                widget.pack(fill="both", expand=True, padx=10, pady=10)

                # Add Interactive Crosshair and Tooltip for all panels
                panels = [axes[0], axes[2], axes[4], axes[6]]
                
                vlines = []
                hlines = []
                annots = []
                
                for p_ax in panels:
                    vl = p_ax.axvline(0, color='white', lw=1, ls='--', alpha=0.6)
                    hl = p_ax.axhline(0, color='white', lw=1, ls='--', alpha=0.6)
                    vl.set_visible(False)
                    hl.set_visible(False)
                    
                    an = p_ax.annotate(
                        "", xy=(0,0), xytext=(15,15), textcoords="offset points",
                        bbox=dict(boxstyle="round", fc="#2B2B2B", ec="#3498DB", lw=2),
                        arrowprops=dict(arrowstyle="->", color="#3498DB"), color="white",
                        fontfamily="Microsoft JhengHei", fontsize=12, fontweight="bold",
                        zorder=100
                    )
                    an.set_visible(False)
                    
                    vlines.append(vl)
                    hlines.append(hl)
                    annots.append(an)

                def on_mouse_move(event):
                    active_idx = -1
                    for i, p_ax in enumerate(panels):
                        if event.inaxes == p_ax:
                            active_idx = i
                            break
                            
                    if active_idx != -1:
                        x, y = event.xdata, event.ydata
                        idx = int(round(x))
                        
                        if 0 <= idx < len(df):
                            date_str = df.index[idx].strftime('%Y-%m-%d')
                            price = df['Close'].iloc[idx]
                            vol = df['Volume'].iloc[idx] if 'Volume' in df.columns else 0
                            rsi = df['RSI'].iloc[idx]
                            macd_val = df['MACD'].iloc[idx]
                            
                            for i, (vl, hl, an) in enumerate(zip(vlines, hlines, annots)):
                                vl.set_xdata([x, x])
                                vl.set_visible(True)
                                
                                if i == active_idx:
                                    hl.set_ydata([y, y])
                                    hl.set_visible(True)
                                    an.xy = (x, y)
                                    
                                    if i == 0:
                                        text = f"📅 {date_str}\n💵 收盤: {price:.2f}"
                                    elif i == 1:
                                        text = f"📅 {date_str}\n📊 成交量: {self.format_large_number(vol)}"
                                    elif i == 2:
                                        text = f"📅 {date_str}\n📈 RSI: {rsi:.2f}"
                                    elif i == 3:
                                        text = f"📅 {date_str}\n📉 MACD: {macd_val:.2f}"
                                        
                                    an.set_text(text)
                                    an.set_visible(True)
                                else:
                                    hl.set_visible(False)
                                    an.set_visible(False)
                                    
                            canvas.draw_idle()
                    else:
                        any_visible = False
                        for vl, hl, an in zip(vlines, hlines, annots):
                            if vl.get_visible():
                                any_visible = True
                            vl.set_visible(False)
                            hl.set_visible(False)
                            an.set_visible(False)
                        if any_visible:
                            canvas.draw_idle()

                canvas.mpl_connect("motion_notify_event", on_mouse_move)

            except Exception as e:
                err_lbl = ctk.CTkLabel(chart_frame, text=f"無法產生圖表：{e}", text_color="red")
                err_lbl.pack(pady=10)

        # 4. News Section
        if news:
            news_frame = ctk.CTkFrame(self.scroll_frame, corner_radius=10, fg_color="#1E1E1E")
            news_frame.pack(fill="x", pady=10, padx=5)

            n_title = ctk.CTkLabel(news_frame, text="📰 最近新聞與 AI 重點摘要", font=ctk.CTkFont(family="Microsoft JhengHei", size=18, weight="bold"))
            n_title.pack(pady=(15, 10), padx=15, anchor="w")

            for item in news:
                item_frame = ctk.CTkFrame(news_frame, fg_color="#2B2B2B", corner_radius=8)
                item_frame.pack(fill="x", padx=15, pady=(0, 15))

                title_lbl = ctk.CTkLabel(item_frame, text=f"➤ {item['title']}", font=ctk.CTkFont(family="Microsoft JhengHei", size=16, weight="bold"), wraplength=550, justify="left")
                title_lbl.pack(anchor="w", padx=15, pady=(10, 5))
                
                if item['url']:
                    title_lbl.configure(text_color="#3498DB", cursor="hand2")
                    title_lbl.bind("<Button-1>", lambda e, link=item['url']: webbrowser.open_new(link))

                meta_lbl = ctk.CTkLabel(item_frame, text=f"來源：{item['provider']} | 日期：{item['pub_time']}", font=ctk.CTkFont(family="Microsoft JhengHei", size=12), text_color="gray")
                meta_lbl.pack(anchor="w", padx=15, pady=(0, 5))
                
                summary_lbl = ctk.CTkLabel(item_frame, text=f"💡 AI 重點摘要：\n{item['summary']}", font=ctk.CTkFont(family="Microsoft JhengHei", size=14), text_color="#E67E22", wraplength=550, justify="left")
                summary_lbl.pack(anchor="w", padx=15, pady=(0, 10))
            
            ctk.CTkFrame(news_frame, height=5, fg_color="transparent").pack()

if __name__ == "__main__":
    app = StockApp()
    app.mainloop()
