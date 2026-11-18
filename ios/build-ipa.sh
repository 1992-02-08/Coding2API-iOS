#!/bin/bash
# Run on macOS with full Xcode, after Briefcase create. Does not sign or install.
set -euo pipefail
cd "$(dirname "$0")/.."
test "$(uname -s)" = Darwin
mkdir -p ios/dist
project_list=()
while IFS= read -r project; do project_list+=("$project"); done < <(find ios/staging/build -name '*.xcodeproj' -type d)
if [ "${#project_list[@]}" -ne 1 ]; then
    echo 'Expected exactly one generated Xcode project' >&2
    exit 1
fi
xcodebuild -list -json -project "${project_list[0]}" > ios/dist/xcode-project.json
scheme=$(python -c 'import json; p=json.load(open("ios/dist/xcode-project.json"))["project"]; s=p["schemes"]; assert len(s)==1, s; print(s[0])')
xcodebuild -project "${project_list[0]}" -scheme "${scheme:?}" \
    -configuration Release -sdk iphoneos -destination 'generic/platform=iOS' \
    -archivePath "$PWD/ios/dist/Coding2API.xcarchive" \
    CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO \
    IPHONEOS_DEPLOYMENT_TARGET=16.0 ARCHS=arm64 archive \
    > ios/dist/xcodebuild.log 2>&1
python - <<'PY'
import json
import pathlib
import plistlib
import shutil
import subprocess
import zipfile

root = pathlib.Path('ios/dist')
apps = list((root / 'Coding2API.xcarchive/Products/Applications').glob('*.app'))
if len(apps) != 1:
    raise SystemExit('Expected exactly one archived app')
app = apps[0]
info = plistlib.loads((app / 'Info.plist').read_bytes())
subprocess.run(['lipo', str(app / info['CFBundleExecutable']), '-verify_arch', 'arm64'], check=True)
# These checks catch a hollow shell or wrongly staged resources; imports still require a device.
for pattern in ('**/src/main.py', '**/web/dist/index.html', '**/coding2api/app.py'):
    if not list(app.glob(pattern)):
        raise SystemExit(f'Missing packaged content: {pattern}')
payload = root / 'Payload'
payload.mkdir(exist_ok=False)
shutil.copytree(app, payload / app.name, symlinks=True)
subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(payload),
                str(root / 'Coding2API-unsigned.ipa')], check=True)
with zipfile.ZipFile(root / 'Coding2API-unsigned.ipa') as archive:
    if not any(n.startswith('Payload/') and n.endswith('/Info.plist') for n in archive.namelist()):
        raise SystemExit('Invalid IPA layout')
(root / 'BUILD-STATUS.json').write_text(json.dumps({
    'bundle_id': info['CFBundleIdentifier'], 'signed': False,
    'device_tested': False, 'daemon_included': False,
}, indent=2) + '\n')
PY
