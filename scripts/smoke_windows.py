import argparse
import json
import platform
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass


def emit(text):
    print(text.encode('utf-8', 'replace').decode('utf-8', 'replace'))

from app_build import BuildVariant, add_variant_argument

root = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    add_variant_argument(parser)
    variant = BuildVariant(parser.parse_args().all_sources)
    if platform.system() != 'Windows':
        raise SystemExit('此检查需要 Windows。')
    version = re.search(r'^version:\s*(\S+)', (root / 'pubspec.yaml').read_text(encoding='utf-8'), re.MULTILINE).group(1)
    package = root / 'dist' / 'windows' / f'{variant.slug}-{version}-windows-x64.zip'
    with tempfile.TemporaryDirectory(prefix='zhenguojian-smoke-') as temporary:
        directory = Path(temporary)
        with zipfile.ZipFile(package) as archive:
            archive.extractall(directory)
        media = directory / 'fixture.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi',
                        '-i', 'testsrc2=size=160x90:rate=12', '-t', '3',
                        '-c:v', 'libx264', '-threads', '1', str(media)], check=True)
        report = directory / 'result.json'
        process = subprocess.run(
            [str(directory / (variant.slug + '.exe')), '--package-smoke', str(report), str(media)],
            cwd=directory, timeout=180, capture_output=True, text=True, errors='replace')
        output = (process.stdout or '') + (process.stderr or '')
        if not report.is_file():
            if output.strip():
                emit(output)
            raise SystemExit(f'包内自检进程退出码 {process.returncode}，没有生成报告')
        evidence = json.loads(report.read_text(encoding='utf-8'))
        emit(json.dumps(evidence, ensure_ascii=False))
        if output.strip():
            emit(output)
        required = ('nativeCore', 'ffprobe', 'remux')
        if evidence.get('ok') is not True or any(evidence.get(key) is not True for key in required):
            raise SystemExit('Windows 包启动验收未通过：' + json.dumps(evidence, ensure_ascii=False))
        if evidence.get('mediaKitPlayback') is not True:
            emit('::warning::播放推进自检未通过（构建机常见无音频/图形设备，需实机复验）：'
                 + str(evidence.get('playbackNote', '')))
        output = root / 'build' / 'windows-package-smoke.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(evidence))


if __name__ == '__main__':
    main()
