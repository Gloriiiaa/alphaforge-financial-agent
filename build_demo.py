"""Export a standalone browser demo from the exact reports served by agent.py."""
import argparse
import json
from pathlib import Path
from agent import DEFAULT_DATA, ROOT, ResearchAgent

parser = argparse.ArgumentParser()
parser.add_argument('--data', type=Path, default=DEFAULT_DATA)
parser.add_argument('--output', type=Path, default=ROOT.parent / 'mateo-demo.html')
args = parser.parse_args()
agent = ResearchAgent(args.data.expanduser())
reports = {}
for ticker in agent.assets:
    reports[ticker] = {}
    for window in (90, 365, 1095, 1826):
        reports[ticker][window] = {}
        for risk in ('moderate', 'strict'):
            report = agent.analyze(ticker, window, risk)
            # Export at most roughly 150 evenly spaced chart points, preserving endpoints.
            chart = report['market']['chart']
            indices = range(0, len(chart)-1, max(1, (len(chart)+149)//150))
            report['market']['chart'] = [chart[i] for i in indices] + [chart[-1]]
            reports[ticker][window][risk] = report
snapshot = json.dumps(
    dict(names=agent.names, companies=list(agent.assets.values()), reports=reports),
    ensure_ascii=False, separators=(',', ':'),
).replace('<', '\\u003c')
html = (ROOT / 'index.html').read_text(encoding='utf-8')
args.output.write_text(
    html.replace('<script>', '<script>globalThis.MATEO_SNAPSHOT='+snapshot+';</script>\n<script>', 1),
    encoding='utf-8',
)
print(args.output)

