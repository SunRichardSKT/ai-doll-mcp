"""Fetch exact upstream sources for a registration check; never bundle them publicly."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import textwrap

ROOT = Path(__file__).resolve().parents[1]
COMMIT = 'dbf71916fae9750cfdc9f9a774f5a0fee56633fb'  # Official v1.12.2 tag
FILES = ('JsExecutionScriptBuilder.kt', 'JsInitRuntimeScriptBuilder.kt',
         'JsToolPkgApiRuntime.kt', 'JsToolPkgRegistration.kt', 'JsComposeDslBridge.kt')


def prepare():
    import httpx
    folder = ROOT / 'build/integration-research/operit-1.12.2'
    folder.mkdir(parents=True, exist_ok=True)

    def fetch(name):
        path = folder / name
        # Resolve the immutable commit, even when another tag's cache is present.
        url = ('https://api.github.com/repos/AAswordman/Operit/contents/'
               'app/src/main/java/com/ai/assistance/operit/core/tools/javascript/' + name)
        response = httpx.get(url, params={'ref': COMMIT}, trust_env=False, timeout=25)
        response.raise_for_status()
        raw = base64.b64decode(response.json()['content'])
        path.write_bytes(raw)
        return name, hashlib.sha256(raw).hexdigest()

    sources = dict(ThreadPoolExecutor(4).map(fetch, FILES))
    output = folder / 'runtime'
    output.mkdir(exist_ok=True)

    def part(file, function):
        text = (folder / file).read_text(encoding='utf-8')
        function_body = text[text.index('fun ' + function + '('):]
        result = function_body.split('return """', 1)[1].split('""".trimIndent()', 1)[0]
        return textwrap.dedent(result).strip()

    prelude = part('JsExecutionScriptBuilder.kt', 'buildExecutionPreludeSource')
    execution = part('JsExecutionScriptBuilder.kt', 'buildExecutionRuntimeBridgeScript')
    execution = execution.replace('$TOOLPKG_EXECUTION_ENTRY_FUNCTION', '__operitExecuteScriptFunction')
    execution = execution.replace('$preludeSource', json.dumps(prelude))
    scripts = {
        'execution.js': execution,
        'expose.js': part('JsInitRuntimeScriptBuilder.kt', 'buildRuntimeExposeScript'),
        'registry.js': part('JsInitRuntimeScriptBuilder.kt', 'buildRuntimeCallRegistryScript'),
        'api.js': part('JsToolPkgApiRuntime.kt', 'buildToolPkgApiRuntimeScript'),
        'registration.js': part('JsToolPkgRegistration.kt', 'buildToolPkgRegistrationBridgeScript'),
        'context.js': part('JsComposeDslBridge.kt', 'buildComposeDslContextBridgeDefinition'),
    }
    for name, script in scripts.items():
        if re.search(r'\$(?:TOOLPKG_EXECUTION_ENTRY_FUNCTION|preludeSource)', script):
            raise ValueError('Unresolved Kotlin interpolation')
        (output / name).write_text(script, encoding='utf-8')
    (folder / 'UPSTREAM.json').write_text(json.dumps(dict(version='1.12.2', commit=COMMIT, sources=sources),
                                                    indent=2), encoding='utf-8')
    return output


if __name__ == '__main__':
    print(prepare())
