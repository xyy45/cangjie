"""Pinned local SDK and minimum process environment for this supported host."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SDK = ROOT / '.runtime/sdk/cangjie'
MACOS_SDK = Path('/Library/Developer/CommandLineTools/SDKs/MacOSX15.4.sdk')


def sdk_environment() -> dict[str, str]:
    if not (SDK / 'bin/cjc').is_file() or not MACOS_SDK.is_dir():
        raise ValueError('pinned Cangjie/macOS SDK unavailable')
    return {'PATH': f'{SDK}/bin:{SDK}/tools/bin:/usr/bin:/bin',
            'CANGJIE_HOME': str(SDK), 'SDKROOT': str(MACOS_SDK),
            'DYLD_LIBRARY_PATH': f'{SDK}/runtime/lib/darwin_aarch64_cjnative:{SDK}/tools/lib',
            'HOME': str(ROOT / '.runtime/home'), 'TMPDIR': '/tmp', 'LANG': 'en_US.UTF-8'}
