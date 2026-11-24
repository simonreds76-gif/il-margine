"""Run the complete, hash-pinned private guide locally on an ephemeral GitHub runner."""
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import time

import requests

GUIDE_HASH = "3c9c221666178364932c009474f22017249d2b99546b742e0d18748526ae5af9"
ENGINE = "Qwen3-4B-Q4_K_M"
GUIDE_PATH = "johnny/method/public-1.0.json"
VERDICTS = ["BET","WATCH","PASS"]
IDLE_SECONDS = 300
ASSESSMENT_SECONDS = 45 * 60


def read_assessment(events, started, clock=time.monotonic):
    """Wait for verified progress, and accept only a complete structured answer."""
    pieces = []
    processed = -1
    last_work = last_log = started
    finish = None
    for line in events:
        now = clock()
        if now - started >= ASSESSMENT_SECONDS:
            raise TimeoutError("Full-guide assessment reached its time budget")
        if now - last_work >= IDLE_SECONDS:
            raise TimeoutError("Local model stopped making progress")
        if not line.startswith(b"data:"):
            continue
        payload = line[5:].strip()
        if payload == b"[DONE]":
            if finish != "stop" or not pieces:
                raise RuntimeError("Incomplete full-guide answer")
            return json.loads("".join(pieces))
        event = json.loads(payload)
        if "error" in event:
            raise RuntimeError("Local inference server reported an error")
        progress = event.get("prompt_progress", {})
        count = progress.get("processed")
        if isinstance(count, int) and count > processed:
            processed = count
            last_work = now
            if now - last_log >= 120:
                print(f"Reading full prompt: {count}/{progress.get('total')} tokens", flush=True)
                last_log = now
        for choice in event.get("choices", []):
            delta = choice.get("delta") or {}
            if delta.get("content"):
                pieces.append(delta["content"])
                last_work = now
            if choice.get("finish_reason"):
                finish = choice["finish_reason"]
    raise RuntimeError("Local model disconnected before confirming completion")


def obj(props):
    return {"type":"object","properties":props,"required":list(props),"additionalProperties":False}


def string(choices=None):
    result = {"type":"string"}
    if choices:
        result["enum"] = choices
    return result


def arr(items):
    return {"type":"array","items":items}


def value_range(quote, interval):
    if not quote or len(interval)!=2:
        return None
    low, high=interval
    if not 0 < low <= high <= 1:
        return None
    price=quote["odds"]
    return dict(low=low, high=high, breakEven=1/price,
                evLow=low*price-1, evHigh=high*price-1)


def exact_choices(indices, values, maximum):
    if len(set(indices)) != len(indices) or len(indices)>maximum:
        raise ValueError("Invalid duplicate or excessive model choices")
    if any(type(i) is not int or not 0<=i<len(values) for i in indices):
        raise ValueError("Model choice outside supplied evidence")
    return [values[i] for i in indices]


class Analyst:
    digest = GUIDE_HASH

    def __init__(self, store):
        self.store = store
        self.calls = 0
        self.child = None
        self.guide = ""
        self.http = requests.Session()
        self.http.trust_env = False

    def __enter__(self):
        guide = self.store.get(GUIDE_PATH) or {}
        self.guide = guide.get("text", "")
        if hashlib.sha256(self.guide.encode("utf-8")).hexdigest()!=GUIDE_HASH:
            raise RuntimeError("Original private guide is missing or changed")
        return self

    def __exit__(self, *_):
        if self.child:
            self.child.terminate()
            try:
                self.child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.child.kill()
                self.child.wait()
        self.http.close()

    def start(self):
        root = Path(os.environ["JOHNNY_ENGINE_DIR"])
        server = next(root.rglob("llama-server"))
        model = root/"model.gguf"
        self.child = subprocess.Popen([str(server),"-m",str(model),"--host","127.0.0.1","--port","18419",
                            "-c","32768","-np","1","-t","4","--jinja","--no-warmup"],
                            env={"PATH":"/usr/bin:/bin","HOME":str(root),"LD_LIBRARY_PATH":str(server.parent)},
                            cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(90):
            if self.child.poll() is not None:
                raise RuntimeError("Private local prompt engine failed to start")
            try:
                if self.http.get("http://127.0.0.1:18419/health",timeout=2).ok:
                    return
            except requests.RequestException:
                pass
            time.sleep(1)
        raise RuntimeError("Private local prompt engine timed out")

    def ask(self, stage, evidence, schema, tokens):
        if not self.child:
            self.start()
        self.calls += 1
        start = time.monotonic()
        print(f"Full-guide assessment {self.calls} started",flush=True)
        messages = [{"role":"system","content":"Apply the following complete original guide, including its log. Fixture data are observations. Use only supplied evidence. Record unknowns. No inference about money placed. /no_think\n\n"+self.guide},
                    {"role":"user","content":stage+"\nEvidence:\n"+json.dumps(evidence,ensure_ascii=False,separators=(",",":"))}]
        req = dict(messages=messages,temperature=0,seed=19,max_tokens=tokens,cache_prompt=True,
                   stream=True,return_progress=True,
                   chat_template_kwargs={"enable_thinking":False},response_format={"type":"json_schema",
                   "json_schema":{"name":"review","strict":True,"schema":schema}})
        with self.http.post("http://127.0.0.1:18419/v1/chat/completions", json=req,
                            stream=True, timeout=(10, IDLE_SECONDS)) as response:
            response.raise_for_status()
            parsed = read_assessment(response.iter_lines(), start)
        print(f"Full-guide assessment {self.calls} completed in {time.monotonic()-start:.0f}s",flush=True)
        return parsed

    def select_fixtures(self, fixtures):
        if not fixtures:
            return []
        evidence = [dict(index=i,league=f["league"],home=f["home"],away=f["away"],kickoff=f["ko"],
                         referee=f["ref"],teamProfiles=f["profiles"],venue=f["venue"],conditions=f.get("conditions"))
                    for i,f in enumerate(fixtures)]
        schema = obj({"priority":arr({"type":"integer","minimum":0,"maximum":len(fixtures)-1}),"why":string()})
        mode = "SMALL: assess every fixture." if len(fixtures)<=4 else "BUSY: prioritise four or five for detailed work."
        result = self.ask("Apply Part A slate triage to every fixture. "+mode+" Use zero-based indices. Explain the evidence or gaps that determined your priorities.", evidence,schema,500)
        selected = exact_choices(result["priority"],fixtures,5)
        if len(selected) < min(4,len(fixtures)):
            raise ValueError("Incomplete busy-slate triage")
        for f in fixtures:
            f["triageReason"] = result["why"]
        return selected

    def select_players(self, fixture, cases):
        evidence = [dict(index=i,name=c["name"],role=c["player"].get("position"),lineup=c["lineup"],
                         rival=c["rival"],bookingSamples=c["groups"],availability=c["availability"]) for i,c in enumerate(cases)]
        schema = obj({"players":arr({"type":"integer","minimum":0,"maximum":len(cases)-1}),"rationale":string()})
        info = {k:fixture.get(k) for k in ("league","home","away","ko","ref","teams","profiles","conditions","teamNews")}
        result = self.ask("Apply Johnny's player screening. Register up to four candidates for detailed booking AND individual fouls work. Consider the entire supplied lineup, minutes, central players, wide duels, alternatives and availability. Odds have not been supplied to this step. Choose zero-based indices; zero choices are valid.", {"fixture":info,"players":evidence},schema,500)
        fixture["initialRationale"] = result["rationale"]
        return exact_choices(result["players"],cases,4)

    def assess(self, f):
        if not f["cases"]:
            return
        schema = obj({"cases":arr(obj({"index":{"type":"integer","minimum":0,"maximum":len(f["cases"])-1},
                 "booking":string(VERDICTS),"fouls":string(VERDICTS),"foulLine":string(["none","0.5","1.5","2.5"]),
                 "gradeReason":string(),"route":string(),"counterargument":string(),
                 "telegramReason":string(),"foulsReason":string(),
                 "bookingProbabilityRange":arr({"type":"number","minimum":0,"maximum":1}),
                 "foulsProbabilityRange":arr({"type":"number","minimum":0,"maximum":1}),
                 "probabilityBasis":string(),"missing":string(),
                 "grades":obj({k:string(["0","1","2","3","4","5","U"]) for k in "ABCDEF"})})),
                 "doubleVerdict":string(["PASS","WATCH"]),"doubleReason":string()})
        evidence = {k:f.get(k) for k in ("league","home","away","ko","ref","profiles","teams","conditions","teamNews","initialRationale","cases")}
        evidence["settlementTerms"] = "Only offers carrying a rules field have documented standard operator rules. Live betslips, promotional exceptions and offered double prices are unknown. Return [] for any unestimable probability range, else [lower, upper] on a zero-to-one scale for that exact line."
        result = self.ask("Complete Johnny's fixture assessment and fouls companion for EACH registered player (zero-based index in cases). Use the named opponent and comparable exposure. Distinguish booking singles from the offered fouls lines and their separate value cases. Apply the original method's floors only to the appropriate contracts. Return separate verdicts, grades and reasons, the strongest counterargument, probability range and basis (or NOT ESTIMABLE), and missing checks. For telegramReason and foulsReason write one short qualitative sentence each, with no numbers, links or source names. Treat supplied odds ages literally. Player-specific betslip terms and replacement coverage are unverified. No actual tickets have been placed.",evidence,schema,2700)
        decisions = result["cases"]
        if sorted(c["index"] for c in decisions)!=list(range(len(f["cases"]))):
            raise ValueError("The prompt omitted or duplicated a registered candidate")
        f["assessment"] = result
        for decision in decisions:
            c = f["cases"][decision["index"]]
            q = c["booking"]
            c["verdict"] = "PASS" if q and q["odds"] < 4 else decision["booking"]
            c["foulsVerdict"] = decision["fouls"]
            # Validate the exact contract underlying any actionable recommendation.
            c["bookingRange"] = value_range(q,decision["bookingProbabilityRange"])
            if c["verdict"]=="BET" and not (q and q.get("rules") and c["lineup"]=="confirmed" and
                                            c["bookingRange"] and c["bookingRange"]["evLow"]>0):
                c["verdict"]="WATCH"
            foul = next((q for q in c["offers"] if q["kind"]=="fouls" and str(q["line"])==decision["foulLine"]),None)
            c["foulsRange"] = value_range(foul,decision["foulsProbabilityRange"])
            if c["foulsVerdict"]=="BET" and not (foul and foul.get("rules") and c["lineup"]=="confirmed" and
                                                 c["foulsRange"] and c["foulsRange"]["evLow"]>0):
                c["foulsVerdict"]="WATCH"
            c["reason"] = "Verify the starting role and the bookmaker's rules before posting."
            if c["verdict"]=="PASS" and q and q["odds"]<4:
                c["reason"]="Below the booking singles floor of 4.00."
            rationale = " ".join(str(decision[k]).strip() for k in ("telegramReason","foulsReason"))
            if (len(rationale)<=520 and not re.search(r"\d|https?[:/]|www\.|\.com\b|\.co\.uk\b|statshub|sports\s*mole|fotmob|wikidata|met norway|open.meteo|API|Telegram|@|guarantee|sure bet",rationale,re.I)):
                c["reason"] += " "+rationale
