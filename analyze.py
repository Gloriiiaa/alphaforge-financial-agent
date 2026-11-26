"""Mateo company screening prototype. Python 3.10+, standard library only."""
import argparse
from bisect import bisect_right
from collections import defaultdict
import csv
from datetime import date, timedelta
from difflib import get_close_matches
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
from statistics import stdev
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
DEFAULT_DATA = Path.home() / 'Downloads/Datathon2026/alphaforge_starter'
ALIASES = {
    '苹果': 'AAPL', '微软': 'MSFT', '英伟达': 'NVDA', '谷歌': 'GOOGL',
    '亚马逊': 'AMZN', '特斯拉': 'TSLA', '埃克森美孚': 'XOM',
    '加拿大自然资源': 'CNQ.TO', 'canadian natural': 'CNQ.TO',
    '道明银行': 'TD.TO', 'td bank': 'TD.TO', 'enbridge': 'ENB.TO',
    '加拿大皇家银行': 'RY.TO', 'rbc': 'RY.TO',
}
TOPICS = {
    'Energy': 'Review emissions, incidents, tailings or spill remediation, and feedback from affected communities and Indigenous peoples.',
    'Financials': 'Review anti-money laundering remediation, consumer protection, and the environmental impact of financing.',
    'Information Technology': 'Review supply chain labor practices, Scope 3 emissions, and governance disclosures.',
}


def load_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def key(value):
    return re.sub(r'[\W_]+', '', value.casefold())


def drawdown(prices):
    peak, worst = prices[0], 0.0
    for price in prices:
        peak = max(peak, price)
        worst = min(worst, price / peak - 1)
    return worst


class ResearchAgent:
    def __init__(self, folder):
        self.assets = {r['ticker']: r for r in load_csv(folder / 'assets_universe.csv')
                       if r['asset_class'] == 'equity'}
        self.names = {}
        for ticker, asset in self.assets.items():
            for name in (ticker, ticker.removesuffix('.TO'), asset['name']):
                self.names[key(name)] = ticker
        self.names.update({key(k): v for k, v in ALIASES.items() if v in self.assets})
        self.prices = defaultdict(dict)
        for row in load_csv(folder / 'prices_daily.csv'):
            day, ticker = date.fromisoformat(row['date']), row['ticker']
            close, adj = float(row['close']), float(row['adj_close'])
            if day in self.prices[ticker] or not all(math.isfinite(x) and x > 0 for x in (close, adj)):
                raise ValueError(f'Invalid or duplicate price: {ticker} {day}')
            self.prices[ticker][day] = (close, adj)
        fx = sorted((date.fromisoformat(r['date']), float(r['usdcad']))
                    for r in load_csv(folder / 'fx_usdcad_daily.csv'))
        if any(not math.isfinite(value) or value <= 0 for _, value in fx):
            raise ValueError('Invalid USD/CAD rate.')
        self.fx_dates, self.fx = zip(*fx)
        self.metadata = {r['file']: r for r in load_csv(folder / 'sources_metadata.csv')}
        self.evidence = json.loads((ROOT / 'evidence.json').read_text(encoding='utf-8'))

    def cad_rate(self, day, currency):
        if currency == 'CAD':
            return 1.0
        if currency != 'USD':
            raise ValueError(f'Unsupported currency {currency}')
        i = bisect_right(self.fx_dates, day) - 1
        if i < 0 or (day - self.fx_dates[i]).days > 7:
            raise ValueError(f'{day} has no available USD/CAD rate.')
        return self.fx[i]

    def market(self, ticker, currency, days):
        benchmark = 'XIU.TO' if currency == 'CAD' else 'SPY'
        stock, index = self.prices[ticker], self.prices[benchmark]
        if not stock or not index:
            raise ValueError('Price data is missing for the stock or benchmark.')
        end = min(max(stock), max(index))
        start = end - timedelta(days=days)
        common = sorted(d for d in stock.keys() & index.keys() if start <= d <= end)
        if len(common) < 30:
            raise ValueError('Fewer than 30 shared trading days are available.')
        cad = [stock[d][1] * self.cad_rate(d, currency) for d in common]
        bench = [index[d][1] * self.cad_rate(d, currency) for d in common]
        # Use the stock's own trading sessions for risk, including those the benchmark skips.
        risk_days = sorted(d for d in stock if common[0] <= d <= common[-1])
        risk_series = [stock[d][1] * self.cad_rate(d, currency) for d in risk_days]
        volatility = stdev(b / a - 1 for a, b in zip(risk_series, risk_series[1:])) * math.sqrt(252)
        max_dd = drawdown(risk_series)
        total, bench_total = cad[-1] / cad[0] - 1, bench[-1] / bench[0] - 1
        return dict(
            start=str(common[0]), end=str(common[-1]), samples=len(common), risk_samples=len(risk_days),
            price_change=stock[common[-1]][0] / stock[common[0]][0] - 1,
            total=total, benchmark=benchmark, benchmark_total=bench_total,
            excess=total-bench_total, volatility=volatility, drawdown=max_dd,
            shock_10=-0.10, shock_fx_10=-0.19 if currency == 'USD' else None,
            chart=[[str(d), round(100*a/cad[0], 3), round(100*b/bench[0], 3)]
                   for d,a,b in zip(common,cad,bench)],
        )

    def esg(self, ticker, as_of):
        cutoff = date.fromisoformat(as_of)
        records = [e for e in self.evidence.get(ticker, ()) if date.fromisoformat(e['date']) <= cutoff]
        material = any(e['kind'] == 'confirmed' and any(p in ('E', 'S') for p in e['pillars'].split('/'))
                       for e in records)
        status = 'Material controversy' if material else 'Review required' if any(
            e['kind'] in ('open', 'confirmed', 'historical') for e in records
        ) else 'Insufficient evidence'
        covered = {p for e in records for p in e['pillars'].split('/')}
        return dict(records=records, status=status, missing=[p for p in 'ESG' if p not in covered])

    def analyze(self, company, window=365, tolerance='moderate'):
        ticker = self.names.get(key(company))
        if ticker is None:
            suggestions = sorted({self.names[k] for k in get_close_matches(key(company), self.names, n=4)})
            suffix = '. Possible matches: ' + ', '.join(suggestions) if suggestions else '. Choose a company from the list.'
            raise ValueError('Company not found' + suffix)
        if window not in (90, 365, 1095, 1826) or tolerance not in ('moderate', 'strict'):
            raise ValueError('Unsupported lookback period or risk threshold.')
        asset = self.assets[ticker]
        market = self.market(ticker, asset['currency'], window)
        esg = self.esg(ticker, market['end'])
        vol_limit, dd_limit = (0.30, 0.35) if tolerance == 'moderate' else (0.22, 0.25)
        high = market['volatility'] >= vol_limit or -market['drawdown'] >= dd_limit
        reasons = []
        if market['volatility'] >= vol_limit:
            reasons.append(f"Historical annualized volatility of {market['volatility']:.1%} meets or exceeds the {vol_limit:.0%} threshold.")
        if -market['drawdown'] >= dd_limit:
            reasons.append(f"Historical maximum drawdown of {market['drawdown']:.1%} meets or exceeds the {dd_limit:.0%} loss threshold in magnitude.")
        if not high:
            reasons.append('Volatility and drawdown are both below the demo thresholds for the selected period.')
        if esg['status'] == 'Material controversy':
            verdict, rationale = 'Excluded in simulation', 'The regulator’s decision triggers Mateo’s exclusion rule for material environmental or social controversies. The rule applies regardless of historical returns.'
            next_step = 'Review remediation and subsequent regulatory findings. Consider researching diversified ESG funds after reviewing holdings and screening criteria.'
        elif esg['status'] == 'Review required':
            verdict, rationale = 'Pause for manual review', 'The evidence includes an unresolved controversy, historical incident, or governance concern. Check the current status and remediation before reassessing suitability.'
            next_step = 'Read the original source and check for updates from the regulator and company.'
        elif high:
            verdict, rationale = 'Pause due to elevated risk', 'Historical risk meets or exceeds a demo threshold, and more ESG evidence is needed to complete the screen.'
            next_step = 'Compare different lookback periods and use diversified assets as a risk comparison.'
        else:
            verdict, rationale = 'Continue due diligence', 'Historical market risk is below the demo thresholds. More ESG evidence is needed to complete the screen.'
            next_step = 'Review regulatory records and company disclosures, then assess valuation, financial quality, and existing holdings.'
        return dict(
            asset=asset, market=market, esg=esg,
            risk=dict(level='Elevated' if high else 'Within thresholds', reasons=reasons,
                      vol_limit=vol_limit, dd_limit=dd_limit),
            decision=dict(verdict=verdict, rationale=rationale, next=next_step),
            followup=TOPICS.get(asset['sector'], 'Review sector-specific environmental impacts, risks to employees and customers, regulatory events, and governance disclosures.'),
            sources=[self.metadata[f] for f in ('prices_daily.csv', 'fx_usdcad_daily.csv')],
        )


def serve(agent, port):
    class Handler(BaseHTTPRequestHandler):
        def send(self, status, mime, content):
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def json(self, status, payload):
            self.send(status, 'application/json; charset=utf-8', json.dumps(payload, ensure_ascii=False).encode())

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == '/':
                self.send(200, 'text/html; charset=utf-8', (ROOT / 'index.html').read_bytes())
            elif url.path == '/api/companies':
                self.json(200, list(agent.assets.values()))
            elif url.path == '/api/analyze':
                args = parse_qs(url.query)
                try:
                    self.json(200, agent.analyze(args.get('company', [''])[0],
                                                  int(args.get('window', ['365'])[0]),
                                                  args.get('risk', ['moderate'])[0]))
                except ValueError as exc:
                    self.json(400, {'error': str(exc)})
            else:
                self.json(404, {'error': 'Page not found.'})

    with ThreadingHTTPServer(('127.0.0.1', port), Handler) as server:
        print(f'Mateo Agent · http://127.0.0.1:{server.server_port}', flush=True)
        server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('company', nargs='?', help='Company name or ticker. Omit to start the web app.')
    parser.add_argument('--data', type=Path, default=DEFAULT_DATA)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--window', type=int, choices=(90, 365, 1095, 1826), default=365)
    parser.add_argument('--risk', choices=('moderate','strict'), default='moderate')
    args = parser.parse_args()
    try:
        agent = ResearchAgent(args.data.expanduser())
        if args.company:
            report = agent.analyze(args.company, args.window, args.risk)
            report['market'].pop('chart')
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            serve(agent, args.port)
    except (FileNotFoundError, ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')

