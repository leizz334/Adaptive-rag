"""P0-only recovery, source validation and isolated AST probes; standard library only.

No application imports, pytest fixtures, DB, network, model or dependency operations.
Writes are atomic and restricted to the audit state/evidence directory.
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import copy
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace

EVIDENCE = Path(__file__).resolve().parent
STATE = EVIDENCE.parent
ROOT = EVIDENCE.parents[3]
PREFIX = "research/docs/agent_engineering_upgrade/"
REPORTS = dict(zip(("P0-" + x for x in "BCDEFG"), (
    "audits/memory_context.md", "audits/evaluation.md", "audits/tracing.md",
    "audits/experience_memory.md", "audits/security.md", "P0_AUDIT_REPORT.md")))


def git(*args: str, raw: bool = False):
    value = subprocess.check_output(["git", "-C", str(ROOT), *args])
    return value if raw else value.decode("utf-8").strip()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value):
    assert path.resolve().is_relative_to(STATE)
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scope_check():
    assert Path(sys.executable).resolve().parent.name.lower() == "adaptive-rag"
    base = read(EVIDENCE / "initial-workspace.json")
    exceptions = read(EVIDENCE / "continuation-authorization.json")["allowed_modified_baseline_paths"]
    counts = {}
    for group in ("tracked_sha256", "preexisting_untracked_sha256"):
        for path, digest in base[group].items():
            expected = exceptions.get(path, {}).get("authorized_sha256", digest)
            assert (ROOT / path).is_file() and sha(ROOT / path) == expected, path
        counts[group] = len(base[group])
    allowed = set(exceptions)
    new_outside = [p for p in git("ls-files", "--others", "--exclude-standard").splitlines()
                   if not p.startswith(PREFIX) and p not in base["preexisting_untracked_sha256"]]
    assert not new_outside, new_outside
    changed = [p for p in git("diff", base["git_head"], "--name-only").splitlines()
               if not p.startswith(PREFIX) and p not in allowed]
    assert not changed, changed
    for path in ("audits/architecture.md", "evidence/validate_p0_a.py", "evidence/P0-A-validation.json", "evidence/P0-A-source-index.json"):
        committed = git("show", "6fbd7deefbaed209b4b7e73c9d63a7d8f693340a:" + PREFIX + path, raw=True)
        assert (STATE / path).read_bytes() == committed, "Historical P0-A changed: " + path
    return {"result": "PASS", "baseline_counts": counts, "authorized_exception": sorted(allowed), "historical_P0_A_unchanged": True}


def state_check(data):
    assert data["phase"] == "P0" and data["initializer"]["status"] == "completed"
    assert [t["task_id"] for t in data["tasks"]] == ["P0-" + x for x in "ABCDEFG"]
    by_id = {t["task_id"]: t for t in data["tasks"]}
    for t in data["tasks"]:
        assert type(t["passes"]) is bool
        assert {"description", "dependencies", "status", "acceptance_criteria", "evidence_files", "validation_results", "commit_hash", "next_action"} <= t.keys()
        if t["passes"]:
            assert t["status"] == "completed" and all(by_id[d]["passes"] for d in t["dependencies"])
            assert all((STATE / f).is_file() for f in t["evidence_files"])
        if t["commit_hash"]:
            git("cat-file", "-e", t["commit_hash"] + "^{commit}")
    return by_id


def extracted(relative, names, namespace):
    parsed = ast.parse((ROOT / relative).read_text(encoding="utf-8-sig"))
    nodes = [copy.deepcopy(n) for n in parsed.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name in names]
    assert len(nodes) == len(names)
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *nodes], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), relative, "exec"), namespace)
    return namespace


def isolated(task):
    results = []
    if task == "P0-B":
        class Level(str, Enum):
            NONE="none"; SOFT_TRUNCATE="soft"; HARD_COMPRESS="hard"; AUTO_COMPACT="auto"
        @dataclass
        class Message:
            role: str
            content: str
        class Tool:
            def __init__(self, output): self.output=output; self.truncated=False
            def model_copy(self, deep=False): return copy.deepcopy(self)
        ns={"CompressionLevel":Level, "ChatMessage":Message, "KEEP_RECENT_TURNS":4, "TOOL_SOFT_CHARS":400, "TOOL_HARD_CHARS":160}
        extracted("app/memory/budget.py", {"estimate_tokens","messages_tokens","chunks_tokens","utilization","decide_level"}, ns)
        extracted("app/memory/compression.py", {"compress_tool_results","sliding_window","apply_compression"}, ns)
        settings=SimpleNamespace(token_budget=1000, compress_soft_ratio=.5, compress_hard_ratio=.7, auto_compact_ratio=.85)
        assert ns["estimate_tokens"]("x"*150)==100
        assert [ns["decide_level"](x,settings) for x in [100,600,800,900]]==[Level.NONE,Level.SOFT_TRUNCATE,Level.HARD_COMPRESS,Level.AUTO_COMPACT]
        _,_,level,_=ns["apply_compression"]([Message("user","short")],[Tool({"blob":"x"*200000})],"",settings)
        assert level==Level.NONE
        results += [{"probe":"actual budget thresholds","result":"PASS"},{"probe":"200k-character tool payload excluded from budget decision","result":"REPRODUCED"}]
        extracted("app/agents/nodes/memory.py", {"memory_node"}, ns)
        class Summarizer:
            seen=None
            async def summarize(self,messages): self.seen=list(messages); return "bounded summary"
        summary=Summarizer()
        small=SimpleNamespace(token_budget=10,compress_soft_ratio=.5,compress_hard_ratio=.7,auto_compact_ratio=.85)
        history=[Message("user",f"old-{i}-"+"x"*300) for i in range(12)]
        asyncio.run(ns["memory_node"]({"messages":history,"user_query":"new","final_answer":"reply"},settings=small,summarizer=summary))
        assert len(summary.seen)==8 and not any(m.content.startswith("old-0-") for m in summary.seen)
        results.append({"probe":"actual memory_node summarizes after sliding-window truncation","result":"REPRODUCED","summarizer_input_messages":len(summary.seen)})
    if task == "P0-C":
        parsed=ast.parse((ROOT/"eval/metrics.py").read_text(encoding="utf-8"))
        names={n.name for n in parsed.body if isinstance(n,ast.FunctionDef)}
        ns=extracted("eval/metrics.py",names,{"defaultdict":defaultdict})
        assert ns['precision_at_k']({'a'},['a'],3)==1.0
        assert ns['recall_at_k']({'a','b'},['a'],3)==.5
        e2e=next(n for n in ast.walk(ast.parse((ROOT/'eval/runner.py').read_text(encoding='utf-8'))) if isinstance(n,ast.AsyncFunctionDef) and n.name=='eval_e2e')
        loop=next(n for n in ast.walk(e2e) if isinstance(n,ast.For) and isinstance(n.iter,ast.Name) and n.iter.id=='rows')
        selected=[n for n in loop.body if isinstance(n,ast.If) and ('expect_refused' in ast.unparse(n.test) or '"ORD"' in ast.unparse(n.test) or "'ORD'" in ast.unparse(n.test))]
        assert len(selected)==2
        for row,response,expected in [({'query':'ORD10001','expect_refused':False},SimpleNamespace(answer='ORD99999',pending_action=None,refused=True),(1,0)),({'query':'inventory has stock','expect_refused':False},SimpleNamespace(answer='',pending_action=None,refused=True),(0,0))]:
            env={'row':row,'response':response,'toolish_ok':0,'toolish_n':0,'refuse_ok':0,'refuse_n':0}
            exec(compile(ast.fix_missing_locations(ast.Module(body=copy.deepcopy(selected),type_ignores=[])),'eval_e2e_scoring','exec'),env)
            assert (env['toolish_ok'],env['refuse_n'])==expected
        results += [{"probe":"actual E2E scoring credits wrong order ID","result":"REPRODUCED"},{"probe":"unexpected refusal on non-refusal case excluded from refusal denominator","result":"REPRODUCED"},{"probe":"actual metric denominator on short retrieval","result":"PASS"}]
    if task == "P0-F":
        module=ast.parse((ROOT/'app/core/security.py').read_text(encoding='utf-8'))
        ns={'re':re,'PII_MASK':'***'}
        assignments=[copy.deepcopy(n) for n in module.body if isinstance(n,ast.Assign)]
        exec(compile(ast.fix_missing_locations(ast.Module(body=assignments,type_ignores=[])),'security_constants','exec'),ns)
        extracted('app/core/security.py',{'redact_mapping','mask_pii'},ns)
        value=ns['redact_mapping']({'items':[{'password':'SYNTHETIC_SECRET'}]})
        assert value['items'][0]['password']=='SYNTHETIC_SECRET'
        assert ns['mask_pii']('ORD10001')=='ORD10001'
        from contextvars import ContextVar
        ns.update(logging=logging,trace_id_var=ContextVar('trace',default='-'),request_id_var=ContextVar('request',default='-'))
        extracted('app/observability/logging.py',{'ContextFilter'},ns)
        record=logging.LogRecord('probe',20,'probe',1,'phone=%s',('13800138000',),None)
        ns['ContextFilter']().filter(record)
        assert '13800138000' in record.getMessage()
        results += [{'probe':'nested-list secret not redacted by actual redact_mapping','result':'REPRODUCED'},{'probe':'short ORD10001 identifier not masked','result':'REPRODUCED'},{'probe':'logging args bypass msg-only mask','result':'REPRODUCED'}]
    return results


def validate(task, data):
    by_id=state_check(data); current=by_id[task]
    assert all(by_id[d]['passes'] for d in current['dependencies'])
    scope=scope_check(); report=STATE/REPORTS[task]; text=report.read_text(encoding='utf-8')
    assert len(text)>2500 and len(re.findall(r'^```',text,re.M))%2==0
    for i in range(1,len(current['acceptance_criteria'])+1): assert f'acceptance: {task}.{i}' in text
    for label in ['SOURCE_VERIFIED','TEST_VERIFIED','DOCUMENTED_ONLY','HYPOTHESIS','BLOCKED']: assert label in text
    refs={}; external=[]; local=0; test_files=set()
    for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)',text):
        if target.startswith(('https://','http://')): external.append(target); continue
        path,_,anchor=target.partition('#'); p=(report.parent/path).resolve()
        assert p.is_relative_to(ROOT) and p.is_file(), target
        local+=1; rel=p.relative_to(ROOT).as_posix()
        if rel.startswith(PREFIX): continue
        lines=p.read_text(encoding='utf-8-sig').splitlines()
        entry=refs.setdefault(rel,{'sha256':sha(p),'anchors':[]})
        if anchor:
            assert re.fullmatch(r'L[1-9][0-9]*',anchor),target
            n=int(anchor[1:]); assert 0<n<=len(lines),target
            entry['anchors'].append({'line':n,'source':lines[n-1].strip()})
        if rel.startswith('tests/'): test_files.add(rel)
        if p.suffix=='.py': ast.parse(p.read_text(encoding='utf-8-sig'))
    assert len(refs)>=3 and test_files
    if task in ('P0-B','P0-C','P0-D','P0-E'): assert external
    if task=='P0-G':
        assert all(by_id['P0-'+x]['passes'] and by_id['P0-'+x]['commit_hash'] for x in 'ABCDEF')
    probes=isolated(task)
    datasets={}
    if task=='P0-C':
        for p in sorted((ROOT/'eval/dataset').glob('*.jsonl')):
            rows=[json.loads(line) for line in p.read_text(encoding='utf-8').splitlines() if line.strip()]
            assert len({r['id'] for r in rows})==len(rows)
            datasets[p.name]={'rows':len(rows),'sha256':sha(p)}
        assert {k:v['rows'] for k,v in datasets.items()}=={'e2e_eval.jsonl':16,'intent_100.jsonl':100,'rag_eval.jsonl':65}
    result={'task_id':task,'result':'PASS','validation_kind':'source_document_and_isolated_AST_validation','python':sys.executable,'git_head_at_validation':git('rev-parse','HEAD'),'report_sha256':sha(report),'scope_integrity':scope,'local_link_occurrences':local,'source_references':refs,'test_source_files':sorted(test_files),'external_primary_references':sorted(set(external)),'isolated_probes':probes,'datasets':datasets,'acceptance_results':[{'criterion':c,'result':'PASS','report_marker':f'{task}.{i}'} for i,c in enumerate(current['acceptance_criteria'],1)],'not_run':['original pytest/TestClient/app imports','DB operations/migrations/order writes','paid LLM/model download/training','trace or business data upload','proposed M/E experiments and platform integration'],'evidence_limits':'Isolated AST probes use actual extracted function bodies with in-memory stubs. They do not prove full application, provider, DB, ASGI or model behavior.'}
    write(EVIDENCE/(task+'-validation.json'),result)
    return result


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('action',choices=['start','finish','register','check']); parser.add_argument('task',nargs='?'); parser.add_argument('--commit')
    args=parser.parse_args(); data=read(STATE/'feature-list.json'); by_id=state_check(data); scope_check()
    if args.action=='check':
        for task in data['tasks']:
            if not task['passes']: continue
            if task['task_id']!='P0-A':
                v=read(EVIDENCE/(task['task_id']+'-validation.json')); assert v['report_sha256']==sha(STATE/REPORTS[task['task_id']])
            if task['commit_hash']:
                report=task['evidence_files'][0]; assert git('show',task['commit_hash']+':'+PREFIX+report,raw=True)==(STATE/report).read_bytes()
        print(json.dumps({'result':'PASS','completed':[t['task_id'] for t in data['tasks'] if t['passes']],'head':git('rev-parse','HEAD'),'production_changes':0},indent=2)); return
    task=by_id[args.task]
    if args.action=='start':
        assert not task['passes'] and all(by_id[d]['passes'] for d in task['dependencies'])
        first=next(t for t in data['tasks'] if not t['passes'] and all(by_id[d]['passes'] for d in t['dependencies']))
        assert first['task_id']==args.task
        task['status']='in_progress'
    elif args.action=='finish':
        assert task['status']=='in_progress' and not task['passes']
        result=validate(args.task,data)
        task.update(status='completed',passes=True,evidence_files=[REPORTS[args.task],'evidence/'+args.task+'-validation.json'])
        task['validation_results']=[{'result':'PASS','kind':result['validation_kind'],'evidence_file':'evidence/'+args.task+'-validation.json','isolated_probe_count':len(result['isolated_probes']),'original_pytest_run':False}]
        task['next_action']='Commit this task and register its actual delivery hash; continue to the next authorized dependency-ready task.'
    elif args.action=='register':
        assert task['passes'] and task['commit_hash'] is None and args.commit
        git('cat-file','-e',args.commit+'^{commit}')
        for path in task['evidence_files']: assert git('show',args.commit+':'+PREFIX+path,raw=True)==(STATE/path).read_bytes()
        task['commit_hash']=args.commit
        task['next_action']='Verified complete; do not repeat. Continue next authorized ready task, or STOP after P0-G.'
    write(STATE/'feature-list.json',data)
    previous=(STATE/'progress.txt').read_text(encoding='utf-8')
    previous+=f'\nCHECKPOINT action={args.action} task={args.task} status={task["status"]} passes={task["passes"]}\nGIT_HEAD_AT_CHECK={git("rev-parse","HEAD")}\nDELIVERY_COMMIT={task["commit_hash"] or "pending; record only after commit"}\n'
    if args.action=='finish': previous+=f'FILES={REPORTS[args.task]}, evidence/{args.task}-validation.json, feature-list.json, progress.txt\nVALIDATION=PASS (source/static plus isolated probes if present; original pytest and runtime experiments NOT RUN)\n'
    ready=next((t['task_id'] for t in data['tasks'] if not t['passes'] and all(by_id[d]['passes'] for d in t['dependencies'])),None)
    previous+='NEXT_ACTION='+('STOP. All P0 tasks completed; await user review and P1 authorization.' if ready is None else 'After checkpoint, continue '+ready+'; do not rerun completed tasks.')+'\n'
    write(STATE/'progress.txt',previous)
    print(json.dumps({'action':args.action,'task':args.task,'status':task['status'],'passes':task['passes'],'next':ready},indent=2))


if __name__=='__main__': main()
