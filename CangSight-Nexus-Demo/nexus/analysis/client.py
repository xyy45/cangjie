"""Fixed read-only analysis calls and bounded same-origin native SVG retrieval."""
import json
import asyncio
import os
import re
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit,urljoin,parse_qsl
from xml.etree import ElementTree

from dotenv import dotenv_values
import httpx
from nexus.analysis.normalize import SUPPORTED_TOOLS

ROOT=Path(__file__).resolve().parents[2]
DEFAULT_URL='http://47.94.83.64:6240'
MAX_RESPONSE=2*1024*1024
REQUEST_SECONDS=45
SVG_SECONDS=8


class AnalysisUnavailable(RuntimeError):pass


def config():
    local=dotenv_values(ROOT/'.env',interpolate=False) if (ROOT/'.env').is_file() else {}
    return (os.getenv('CANGSIGHT_ANALYSIS_URL') or local.get('CANGSIGHT_ANALYSIS_URL') or DEFAULT_URL,
            os.getenv('CANGSIGHT_ANALYSIS_TOKEN') or local.get('CANGSIGHT_ANALYSIS_TOKEN') or '')


def sanitize(value,secret='',depth=0):
    if isinstance(value,dict):
        return {(str(k).replace(secret,'[REDACTED]') if secret else str(k)):('[REDACTED]' if re.search(r'authorization|api[_-]?key|password|secret|access_token|^token$',str(k),re.I)
                        else sanitize(v,secret,depth+1)) for k,v in value.items()}
    if isinstance(value,list):return [sanitize(v,secret,depth+1) for v in value]
    if isinstance(value,str):
        if depth<12:
            try:nested=json.loads(value)
            except ValueError:nested=None
            if isinstance(nested,(dict,list)):return json.dumps(sanitize(nested,secret,depth+1),ensure_ascii=False)
        if secret:value=value.replace(secret,'[REDACTED]')
        return re.sub(r'((?:https?://|/?artifacts/)[^\s"<>?]+)\?[^\s"<>]+',r'\1?[REDACTED]',value)
    return value


class ResearchClient:
    def __init__(self,*,url=None,token=None,transport=None):
        default_url,default_token=config()
        self.url=(url or default_url).rstrip('/');self.token=default_token if token is None else token
        parsed=urlsplit(self.url)
        # This demo is approved for the known group service, not arbitrary URLs.
        if parsed.hostname!='47.94.83.64' or parsed.port!=6240 or parsed.scheme not in ('http','https') or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
            raise AnalysisUnavailable('分析服务地址不在允许范围')
        self.last=0.0;self.paced=transport is None
        self.transport=transport

    def __enter__(self):return self
    def __exit__(self,*args):pass

    def analyze(self,tool,arguments):
        if tool not in SUPPORTED_TOOLS:raise ValueError('Tool is not permitted')
        if self.paced:time.sleep(max(0,1.4-(time.monotonic()-self.last)))
        try:return asyncio.run(self._request(tool,arguments))
        except (httpx.HTTPError,TimeoutError) as exc:
            raise AnalysisUnavailable('分析服务连接失败或超时；未自动重试') from exc

    async def _request(self,tool,arguments):
        started=time.monotonic();request_id='analysis_'+uuid.uuid4().hex
        async with httpx.AsyncClient(timeout=httpx.Timeout(REQUEST_SECONDS,connect=10),
                    follow_redirects=False,trust_env=False,transport=self.transport,
                    headers={'Authorization':'Bearer '+self.token} if self.token else {}) as client:
            async with asyncio.timeout(REQUEST_SECONDS):
                async with client.stream('POST',self.url+'/tools/'+tool,json=arguments,params={'session_id':request_id}) as response:
                    raw=bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(raw)+len(chunk)>MAX_RESPONSE:raise AnalysisUnavailable('分析响应超过2MiB')
                        raw.extend(chunk)
                    try:payload=json.loads(raw)
                    except (ValueError,UnicodeError):payload={'status':'error','message':'上游未返回有效JSON'}
                    status=response.status_code
            extra=await self._callgraph(client,payload) if tool=='sympas_dep_graph' and status==200 else {}
            self.last=time.monotonic()
            return dict(http_status=status,response=sanitize(payload,self.token),**extra,
                elapsed_ms=round((time.monotonic()-started)*1000),transport='group_http_tools',transport_request_id=request_id)

    async def _callgraph(self,client,payload):
        def find(value,depth=0):
            if depth>12:return None
            if isinstance(value,dict):
                svg=value.get('svg')
                if value.get('graph_type')=='Cg' and isinstance(svg,dict):
                    url=svg.get('download_url') or svg.get('url')
                    if isinstance(url,str):return url
                for child in value.values():
                    found=find(child,depth+1)
                    if found:return found
            if isinstance(value,list):
                for child in value:
                    found=find(child,depth+1)
                    if found:return found
            return None
        unavailable=dict(callgraph=dict(status='UNAVAILABLE',reason='上游未提供可保存的调用图 SVG；未自动重试'))
        link=find(payload)
        if not link:return unavailable
        try:
            parsed=urlsplit(urljoin(self.url+'/',link));base=urlsplit(self.url)
            if (parsed.scheme,parsed.netloc)!=(base.scheme,base.netloc) or parsed.fragment or not re.fullmatch(r'/artifacts/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+\.svg',parsed.path) or '..' in parsed.path:
                return unavailable
            async with asyncio.timeout(SVG_SECONDS):
                async with client.stream('GET',parsed.geturl()) as response:
                    if response.status_code!=200:return unavailable
                    raw=bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(raw)+len(chunk)>MAX_RESPONSE:return unavailable
                        raw.extend(chunk)
            raw=bytes(raw)
            if b'<!ENTITY' in raw.upper():return unavailable
            if ElementTree.fromstring(raw).tag!='{http://www.w3.org/2000/svg}svg':return unavailable
            secrets=[v for k,v in parse_qsl(parsed.query) if v and re.search(r'key|token|secret|signature|authorization',k,re.I)]+([self.token] if self.token else [])
            if any(value.encode() in raw for value in secrets):return unavailable
            return dict(_callgraph_bytes=raw,callgraph=dict(status='SAVED',upstream_path=parsed.path))
        except (httpx.HTTPError,TimeoutError,ElementTree.ParseError,ValueError,LookupError):
            return unavailable
