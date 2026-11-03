"""Bounded IPC and replay binding for the real stateless Cangjie core.

The service supplies payload digests. The native process echoes these bindings;
it does not sign evidence or independently compute cryptographic hashes.
"""
import asyncio
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import signal
import time
from uuid import uuid4

from nexus.contracts import digest

VERSION = '2.0'
LIMIT = 65536
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate native JSON field')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid JSON constant')))


class NativeCoreClient:
    def __init__(self, project_root=PROJECT_ROOT):
        self.root = Path(project_root)

    def component_identity(self):
        source = self.root / 'cangjie/core/src/main.cj'
        binary = self.root / '.runtime/core'
        compiler = self.root / '.runtime/sdk/cangjie/bin/cjc'
        metadata = self.root / '.runtime/core-build.json'
        paths = (source, binary, compiler, metadata)
        if any(p.is_symlink() or not p.is_file() for p in paths):
            raise ValueError('Native core regular component unavailable')
        if sorted((self.root / 'cangjie/core').rglob('*.cj')) != [source]:
            raise ValueError('Native core source set changed')
        actual = dict(zip(('core_source_hash', 'core_component_hash', 'core_compiler_hash'),
                          (hashlib.sha256(p.read_bytes()).hexdigest() for p in paths[:3])))
        expected = {'schema_version': 1, 'core_version': VERSION, **actual}
        if strict_json(metadata.read_bytes()) != expected:
            raise ValueError('Native core component differs from build record')
        return actual

    def call_sync(self, operation, payload, *, deadline_at=None):
        """Short sync persistence paths call IPC before opening their write txn."""
        try:asyncio.get_running_loop()
        except RuntimeError:return asyncio.run(self.call(operation,payload,deadline_at=deadline_at))
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=1) as worker:
            return worker.submit(lambda:asyncio.run(self.call(operation,payload,deadline_at=deadline_at))).result()

    def verify_proof(self, proof, operation, payload):
        try:
            if type(proof) is not dict or set(proof) != {'request', 'response', 'component'}:
                raise ValueError('Invalid native proof')
            request, response = proof['request'], proof['response']
            if (type(request) is not dict or set(request) != {'schema_version', 'core_version', 'operation', 'request_id', 'payload_hash', 'payload'}
                    or type(request['schema_version']) is not int or request['schema_version'] != 1
                    or request['core_version'] != VERSION or request['operation'] != operation
                    or type(request['request_id']) is not str or not 1 <= len(request['request_id']) <= 128
                    or digest(request['payload']) != digest(payload) or request['payload_hash'] != digest(payload)):
                raise ValueError('Native request binding changed')
            if (type(response) is not dict or set(response) != {'schema_version', 'core_version', 'operation', 'request_id', 'payload_hash', 'status', 'reason', 'data'}
                    or type(response['schema_version']) is not int
                    or any(response[k] != request[k] for k in ('schema_version', 'core_version', 'operation', 'request_id', 'payload_hash'))
                    or response['status'] != 'OK' or response['reason'] != 'COMPLETED' or type(response['data']) is not dict):
                raise ValueError('Native response invalid or rejected')
            if proof['component'] != self.component_identity():
                raise ValueError('Native component changed')
            return deepcopy(response['data'])
        except (KeyError, TypeError, OSError) as exc:
            raise ValueError('Invalid native core proof') from exc

    async def call(self, operation, payload, *, deadline_at=None):
        process = None
        try:
            snapshot = deepcopy(payload)
            request = dict(schema_version=1, core_version=VERSION, operation=operation,
                           request_id=uuid4().hex, payload_hash=digest(snapshot), payload=snapshot)
            message = json.dumps(request, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode() + b'\n'
            if len(message) > LIMIT or type(payload) is not dict:
                raise ValueError('Native core message limit or invalid payload')
            remaining = 2 if deadline_at is None else min(2, (deadline_at - int(time.time() * 1000)) / 1000)
            if remaining <= 0:
                raise ValueError('Native core deadline exceeded')
            identity = self.component_identity()
            sdk = self.root / '.runtime/sdk/cangjie'
            env = {'PATH': '/usr/bin:/bin', 'DYLD_LIBRARY_PATH': str(sdk / 'runtime/lib/darwin_aarch64_cjnative')}
            async with asyncio.timeout(remaining):
                process = await asyncio.create_subprocess_exec(str(self.root / '.runtime/core'),
                    stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL, env=env, start_new_session=True, limit=LIMIT)
                process.stdin.write(message)
                await process.stdin.drain()
                process.stdin.close()
                line = await process.stdout.readline()
                if not line.endswith(b'\n') or len(line) > LIMIT:
                    raise ValueError('Native core response limit')
                if await process.stdout.read(1):
                    raise ValueError('Native core returned multiple responses')
                await process.wait()
                if process.returncode:
                    raise ValueError('Native core exited unsuccessfully')
            proof = dict(request=request, response=strict_json(line), component=identity)
            self.verify_proof(proof, operation, snapshot)
            if digest(payload) != digest(snapshot):
                raise ValueError('Native core arguments changed')
            if deadline_at is not None and deadline_at <= int(time.time() * 1000):
                raise ValueError('Native core deadline exceeded')
            return proof
        except (OSError, TimeoutError, TypeError, KeyError, RecursionError, RuntimeError) as exc:
            raise ValueError('Native core unavailable or invalid IPC') from exc
        finally:
            if process is not None and process.returncode is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await process.wait()


class NativePolicyClient(NativeCoreClient):
    """Explicit policy2 adapter; unavailable core never falls back to policy1.1."""
    def component_identity(self):
        identity=super().component_identity()
        # Keep the existing evidence viewer's field names, bound to core2 bytes.
        return {**identity,'policy_component_hash':identity['core_component_hash'],
                'policy_source_hash':identity['core_source_hash']}

    async def decide(self, request):
        try:
            proof = await self.call('policy.decide', request, deadline_at=request['deadline_at'])
            data = proof['response']['data']
            if (set(data) != {'decision', 'reason'} or data['decision'] not in ('Allow', 'Deny', 'NeedApproval')
                    or type(data['reason']) is not str):
                raise ValueError('Invalid native policy decision')
            return {**{key: request[key] for key in ('schema_version', 'policy_version', 'request_id',
                        'input_tree_hash', 'arguments_hash', 'approval_binding')},
                    **data, **proof['component'], 'native_proof': proof}
        except (ValueError, OSError, KeyError, TypeError):
            return dict(schema_version=1, policy_version=VERSION, decision='Deny', reason='CORE_POLICY_UNAVAILABLE')
