"""Private storage, OAuth and delivery for the bounded StatsHub pilot."""
import json
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

import requests
from cryptography.fernet import Fernet

BUCKET = "statshub-daily-private"
BASE = "https://www.statshub.com"
http = requests.Session()

def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

class RemoteError(RuntimeError):
    def __init__(self, status_code):
        super().__init__(f"Remote request failed, HTTP {status_code}")
        self.status_code = status_code


def payload(response):
    if not response.ok:
        raise RemoteError(response.status_code)
    return response.json()

class Store:
    def __init__(self):
        self.base=os.environ["SUPABASE_URL"].rstrip("/")+"/storage/v1"
        host=urlsplit(self.base)
        if host.scheme!="https" or not host.hostname.endswith(".supabase.co"):
            raise ValueError("Unexpected storage destination")
        key=os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        self.headers={"apikey":key,"Authorization":"Bearer "+key}
        def bucket():
            return http.get(self.base+"/bucket/"+BUCKET,headers=self.headers,timeout=15)
        r=bucket()
        if self.missing(r):
            payload(http.post(self.base+"/bucket",headers=self.headers,json={"id":BUCKET,"name":BUCKET,"public":False},timeout=15))
            r=bucket()
        meta=payload(r)
        if meta.get("public") is not False or meta.get("id")!=BUCKET:
            raise ValueError("Private storage boundary not verified")

    @staticmethod
    def missing(r):
        if r.status_code not in (400,404):
            return False
        try:
            body=r.json()
            return str(body.get("statusCode",""))=="404" or body.get("error") in ("not_found","NoSuchKey","NoSuchBucket") or body.get("message","").lower() in ("object not found","bucket not found")
        except ValueError:
            return False

    def get(self,name,default=None):
        r=http.get(self.base+"/object/authenticated/"+BUCKET+"/"+name,headers=self.headers,timeout=15)
        return default if self.missing(r) else payload(r)

    def put(self,name,value,replace=True):
        r=http.post(self.base+"/object/"+BUCKET+"/"+name,headers={**self.headers,"x-upsert":str(replace).lower(),"cache-control":"no-store"},json=value,timeout=20)
        if not replace and r.status_code in (400,409) and ("already exists" in r.text.lower() or "duplicate" in r.text.lower()):
            return False
        payload(r)
        return True

class Provider:
    def __init__(self,store):
        self.store=store
        self.headers=None
        self.sequence=0

    def login(self):
        bundle=json.loads(os.environ["STATSHUB_DAILY_AUTH"])
        cipher=Fernet(bundle["wrap_key"].encode())
        previous=self.store.get("oauth/rotation.json")
        refresh=cipher.decrypt(previous["sealed"].encode()).decode() if previous else bundle["refresh_token"]
        grant=payload(http.post(BASE+"/oauth/token",data=dict(grant_type="refresh_token",client_id=bundle["client_id"],refresh_token=refresh,resource=BASE+"/mcp"),allow_redirects=False,timeout=15))
        if grant.get("refresh_token") and grant["refresh_token"]!=refresh:
            self.store.put("oauth/rotation.json",{"sealed":cipher.encrypt(grant["refresh_token"].encode()).decode()})
        self.headers={"Authorization":"Bearer "+grant["access_token"],"Accept":"application/json, text/event-stream"}
        init=self.rpc("initialize",{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"Il Margine matchweek pilot","version":"1"}})
        self.headers["MCP-Protocol-Version"]=init["protocolVersion"]
        self.rpc("notifications/initialized",{},False)

    def rpc(self,method,params,reply=True):
        self.sequence+=1
        msg={"jsonrpc":"2.0","method":method,"params":params}
        if reply: msg["id"]=self.sequence
        r=http.post(BASE+"/mcp",json=msg,headers=self.headers,timeout=30,allow_redirects=False)
        if not r.ok: raise RuntimeError("StatsHub returned HTTP "+str(r.status_code))
        if r.headers.get("Mcp-Session-Id"): self.headers["Mcp-Session-Id"]=r.headers["Mcp-Session-Id"]
        if not reply: return
        if "event-stream" in r.headers.get("Content-Type",""):
            packets=(json.loads(l[5:].strip()) for l in r.text.splitlines() if l.startswith("data:"))
            obj=next((o for o in packets if o.get("id")==self.sequence),{})
        else: obj=r.json()
        if "result" not in obj: raise RuntimeError("StatsHub RPC unavailable")
        return obj["result"]

    def read(self,name,arguments):
        if not self.headers: self.login()
        time.sleep(2.15)
        result=self.rpc("tools/call",{"name":name,"arguments":arguments})
        if result.get("isError"): raise RuntimeError("StatsHub tool unavailable: "+name)
        return json.loads(next(c["text"] for c in result["content"] if c["type"]=="text"))

def telegram_private():
    endpoint="https://api.telegram.org/bot"+os.environ["TELEGRAM_BOT_TOKEN"]
    chat=os.environ["TELEGRAM_CHAT_ID"]
    result=payload(http.post(endpoint+"/getChat",json={"chat_id":chat},timeout=12)).get("result",{})
    if result.get("type")!="private" or str(result.get("id"))!=chat:
        raise RuntimeError("Configured Telegram destination is not a verified direct chat")
    return endpoint,chat

def send_digest(store,day,parts,document_name=None):
    endpoint,chat=telegram_private()
    for i,part in enumerate(parts):
        key=f"receipts/{day}-{i}.json"
        if not store.put(key,{"state":"sending","at":timestamp()},replace=False):
            if store.get(key,{}).get("state")!="sent":
                raise RuntimeError("Delivery uncertain; inspect the receipt before retrying")
            continue
        def send():
            if document_name:
                return http.post(endpoint+"/sendDocument",data={"chat_id":chat,"caption":"Johnny's full daily bookings and fouls digest"},
                                 files={"document":(document_name,part.encode("utf-8"),"text/plain")},timeout=20)
            return http.post(endpoint+"/sendMessage",json={"chat_id":chat,"text":part,"link_preview_options":{"is_disabled":True}},timeout=20)
        r=send()
        if r.status_code==429:
            time.sleep(min(60,r.json().get("parameters",{}).get("retry_after",3)))
            r=send()
        msg=payload(r)
        if not msg.get("ok"): raise RuntimeError("Telegram did not acknowledge delivery")
        store.put(key,{"state":"sent","at":timestamp(),"message_id":msg["result"]["message_id"]})
