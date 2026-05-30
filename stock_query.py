import yfinance as yf
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
import sys
import json
import os
import requests
from deep_translator import GoogleTranslator

# Ensure UTF-8 output for Windows terminals
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

console = Console()

def format_large_number(num):
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

def fetch_stock_data(symbol):
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        # Check if we got valid data
        if 'currentPrice' not in info and 'regularMarketPrice' not in info and 'previousClose' not in info:
            return None
            
        return info
    except Exception:
        return None

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

HISTORY_FILE = "search_history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(history, symbol):
    if symbol in history:
        history.remove(symbol)
    history.insert(0, symbol)
    history = history[:10]
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False)
    except:
        pass
    return history

def main():
    history = load_history()
    
    console.print(Panel.fit("[bold blue]歡迎使用股票資訊查詢系統[/bold blue]\n[green]支援美股 (如 AAPL, TSLA) 與 台股 (如 2330, 2317)[/green]"))
    
    while True:
        try:
            if history:
                console.print(f"[cyan]歷史搜尋紀錄: {', '.join(history)}[/cyan]")
                
            raw_input = Prompt.ask("\n請輸入股票代號 (輸入 'q' 離開)").strip().upper()
            if raw_input == 'Q':
                break
            if not raw_input:
                continue
                
            symbol = raw_input
            history = save_history(history, symbol)
            
            # Resolve chinese symbol
            resolved_symbol = resolve_symbol(symbol)
            
            # Auto-detect TW stocks if only digits are entered
            is_tw = False
            if resolved_symbol.isdigit():
                resolved_symbol = f"{resolved_symbol}.TW"
                is_tw = True
            elif ".TW" in resolved_symbol or ".TWO" in resolved_symbol:
                is_tw = True
                
            with console.status(f"[bold cyan]正在查詢 {resolved_symbol} 的資料...[/bold cyan]"):
                info = fetch_stock_data(resolved_symbol)
                
                # Try .TWO if .TW didn't work for TW stocks
                if info is None and is_tw and ".TW" in resolved_symbol:
                    resolved_symbol = resolved_symbol.replace(".TW", ".TWO")
                    info = fetch_stock_data(resolved_symbol)
                    
            if info is None:
                console.print(f"[bold red]找不到 {raw_input} 的資料，請確認代號或名稱是否正確。[/bold red]")
                continue
                
            # Update symbol to the resolved one for displaying
            symbol = resolved_symbol
                
            # Extract basic info
            stock_name = info.get('shortName', info.get('longName', symbol))
            currency = info.get('currency', 'TWD' if is_tw else 'USD')
            current_price = info.get('currentPrice') or info.get('previousClose') or info.get('regularMarketPrice')
            
            # Extract financial metrics
            eps = info.get('trailingEps')
            pe_ratio = info.get('trailingPE')
            gross_margin = info.get('grossMargins')
            revenue = info.get('totalRevenue')
            market_cap = info.get('marketCap')
            fifty_two_week_high = info.get('fiftyTwoWeekHigh')
            fifty_two_week_low = info.get('fiftyTwoWeekLow')
            
            # Format table
            table = Table(show_header=False, width=60)
            table.add_column("指標", style="bold cyan")
            table.add_column("數值", style="bold white")
            
            industry_en = info.get('industryDisp') or info.get('industry') or info.get('sectorDisp') or info.get('sector', '未知產業')
            try:
                industry_zh = GoogleTranslator(source='auto', target='zh-TW').translate(industry_en) if industry_en != '未知產業' else industry_en
            except:
                industry_zh = industry_en

            table.add_row("股票名稱", f"{stock_name} ({symbol})")
            table.add_row("產業類別", industry_zh)
            table.add_row("最新收盤價", f"{current_price} {currency}")
            table.add_row("近一年EPS", f"{eps}" if eps else "N/A")
            table.add_row("本益比 (P/E)", f"{pe_ratio:.2f}" if pe_ratio else "N/A")
            table.add_row("毛利率", f"{gross_margin*100:.2f}%" if gross_margin else "N/A")
            table.add_row("近一年營收", f"{format_large_number(revenue)} {currency}" if revenue else "N/A")
            table.add_row("市值", f"{format_large_number(market_cap)} {currency}" if market_cap else "N/A")
            table.add_row("52週最高/最低", f"{fifty_two_week_high} / {fifty_two_week_low}" if fifty_two_week_high else "N/A")
            
            console.print(Panel(table, title=f"[bold yellow]{stock_name} 股票資訊[/bold yellow]", border_style="yellow"))
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[bold red]發生錯誤: {e}[/bold red]")

if __name__ == '__main__':
    main()
