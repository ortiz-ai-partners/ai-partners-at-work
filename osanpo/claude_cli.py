"""claude コマンドの場所を OS ごとに解決する。

Windows では npm が入れる `claude` は `claude.cmd` という起動ファイルで、
Python の subprocess から `claude` とだけ呼んでも見つからない。しかも .cmd 経由だと
日本語や改行を含む引数が壊れることがあるので、隣にある本体 (cli.js) を node で直接呼ぶ。
"""
import os
import shutil


def claude_command():
    """subprocess に渡す先頭部分を返す。例: ['claude'] / ['node', 'C:/.../cli.js']"""
    exe = shutil.which('claude') or shutil.which('claude.cmd')
    if not exe:
        return None
    if exe.lower().endswith(('.cmd', '.bat')):
        cli = os.path.join(os.path.dirname(exe), 'node_modules', '@anthropic-ai', 'claude-code', 'cli.js')
        node = shutil.which('node')
        if node and os.path.exists(cli):
            return [node, cli]
    return [exe]
