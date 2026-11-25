"""Read-only release gate; visual review is a separate, explicit recorded input."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
BASE = 'f7e94654d8c3759c100a2813292f67fb20d42d22'
STEMS = ['revised_01_dual_framework','revised_02_mid_contrasts','revised_03_fmg_results']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-dir', required=True, type=Path)
    parser.add_argument('--visual-review', required=True, type=Path)
    parser.add_argument('--test-log', required=True, type=Path)
    args = parser.parse_args()
    issues, checks = [], {}
    def require(ok, message):
        if not ok:
            issues.append(message)
    for relative in ['results/sequential_20261125/analysis_qa.json',
                     'results/sequential_20261125/offline_replay_qa.json',
                     'results/sequential_20261125/independent_publication_audit.json',
                     'results/sequential_20261125/publication_writer_qa.json',
                     'results/sequential_workbook_validation.json',
                     'results/sequential_figures_qa.json']:
        obj = json.loads((ROOT/relative).read_text(encoding='utf8'))
        require(str(obj.get('status')).upper() == 'PASS', relative+' failed')
        checks[relative] = hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()
        if relative.endswith('sequential_workbook_validation.json'):
            workbook = ROOT/'data/workbooks/MiD2023_MUC_LLM_Comprehensive_EN_20261125.xlsx'
            require(obj['output_sha256'] == hashlib.sha256(workbook.read_bytes()).hexdigest(), 'Workbook changed after validation')
    visual = json.loads(args.visual_review.read_text(encoding='utf8'))
    require(visual.get('status') == 'PASS', 'Visual review did not pass')
    test_text = args.test_log.read_text(encoding='utf-8-sig')
    test_match = re.search(r'Ran (\d+) tests?', test_text)
    require(bool(test_match) and re.search(r'\bOK\b', test_text) and 'FAILED' not in test_text, 'Test run did not pass')
    sources = '\n'.join((ROOT/'manuscript'/name).read_text(encoding='utf8') for name in ['main.tex','supplement.tex'])
    figures = len(re.findall(r'\\begin\{figure\*?\}', sources))
    tables = len(re.findall(r'\\begin\{table\*?\}', sources))
    require(figures == 3 and tables == 3, 'Expected exactly three figures and three tables')
    require('Exact MiD overall-rate hint' in sources and 'colback=gray!8' in sources, 'Main gray hint box missing')
    require('generated/exact_prompts_appendix.tex' in sources, 'Exact prompt appendix missing')
    pdfs = []
    for stem in ['main','supplement']:
        path = ROOT/'manuscript'/f'{stem}.pdf'
        reader = PdfReader(path)
        text = '\n'.join(p.extract_text() or '' for p in reader.pages)
        require(bool(text.strip()), stem+' has no extractable text')
        require(not re.search(r'PAUSED REVIEW DRAFT|results placeholders|results are pending|will be generated from|Review draft:', text, re.I), stem+' has unfinished-result placeholders')
        log = (args.build_dir/f'{stem}.log').read_text(encoding='utf8', errors='replace')
        require(not re.search(r'Overfull \\[hv]box|undefined references|Citation .+ undefined|Reference .+ undefined', log), stem+' layout or reference warning')
        pdfs.append({'path':str(path.relative_to(ROOT)), 'pages':len(reader.pages),
                     'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        reviewed = visual.get('pdf_sha256',{}).get(stem+'.pdf')
        require(reviewed == pdfs[-1]['sha256'], stem+' differs from visually reviewed PDF')
    for stem in STEMS:
        for suffix in ['pdf','png','svg']:
            require((ROOT/'figures'/f'{stem}.{suffix}').is_file(), 'Missing figure '+stem+'.'+suffix)
    protected = 0
    tree = subprocess.check_output(['git','ls-tree','-rz',BASE],cwd=ROOT).decode()
    for entry in tree.split('\0'):
        if not entry:
            continue
        meta,name = entry.split('\t',1)
        if not name.startswith(('data/','config/','results/raw/','results/processed/')):
            continue
        path = ROOT/name
        if not path.is_file():
            issues.append('Original scientific file missing: '+name)
            continue
        data = path.read_bytes()
        digest = hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()
        require(digest == meta.split()[2], 'Original scientific file changed: '+name)
        protected += 1
    report = {'status':'PASS' if not issues else 'FAIL', 'checked_utc':datetime.now(timezone.utc).isoformat(),
        'figure_count':figures,'table_count':tables,'tests_passed':int(test_match[1]) if test_match else None,
        'original_scientific_files_preserved':protected,'baseline_commit':BASE,
        'component_report_hashes':checks,'pdfs':pdfs,'visual_review':visual,
        'scope':'Extended author-review paper; the user waived a 1,000-word ceiling. No journal submission.',
        'issues':issues}
    (ROOT/'results/sequential_revision_qa.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('visual_review','component_report_hashes')},indent=2))
    raise SystemExit(bool(issues))


if __name__ == '__main__':
    main()
