"""claude コマンドの場所を OS ごとに解決する。

Windows では npm が入れる `claude` は `claude.cmd` / `claude.ps1` という起動ファイルで、
本体は `node_modules/@anthropic-ai/claude-code/bin/claude.exe`（実機で確認: 2026-09-17）。
Python の subprocess からは起動ファイルを経由せず、本体を直接呼ぶ（引数の文字化けも避けられる）。
"""
import os
import shutil


def claude_command():
    """subprocess に渡す先頭部分を返す。例: ['claude'] / ['C:/.../bin/claude.exe'] / ['node', '.../cli.js']"""
    exe = shutil.which('claude') or shutil.which('claude.cmd')
    if not exe:
        return None
    if exe.lower().endswith(('.cmd', '.bat', '.ps1')):
        pkg = os.path.join(os.path.dirname(exe), 'node_modules', '@anthropic-ai', 'claude-code')
        native = os.path.join(pkg, 'bin', 'claude.exe')
        if os.path.exists(native):
            return [native]
        cli = os.path.join(pkg, 'cli.js')
        node = shutil.which('node')
        if node and os.path.exists(cli):
            return [node, cli]
    return [exe]


if __name__ == '__main__':
    print(claude_command())
