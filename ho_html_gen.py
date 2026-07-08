#!/usr/bin/env python3
"""
HarmonyOS API HTML 生成脚本
将 hoapi.md 转换为带样式的 HTML 页面，同时整合设备支持清单 (hodevice.md)。

可选 AI 翻译：提供 AI_BASE_URL / AI_MODEL / AI_API_KEY（环境变量或入参）时，
构建时将中文 HTML 整文件翻译为英文，生成单文件双语版（按钮切换中/英）；
未配置时仅生成中文版（不渲染语言按钮）。
"""

import datetime
import html
import os
import re
import time

import requests  # AI 翻译调用（OpenAI 兼容）


# ============================================================================
# 工具函数
# ============================================================================

def get_last_updated(*files):
    """取数据文件最近修改时间（YYYY-MM-DD），用于页面显示「最近更新」"""
    latest = 0
    for f in files:
        if os.path.exists(f):
            latest = max(latest, os.path.getmtime(f))
    if not latest:
        return ''
    return datetime.datetime.fromtimestamp(latest).strftime('%Y-%m-%d')


def load_env(env_file='.env'):
    """简单解析脚本同目录下的 .env 文件并加载到 os.environ（不覆盖已存在的值）。
    避免引入 python-dotenv 依赖。优先级：generate_html 入参 > 系统/Shell 环境变量 > .env。"""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), env_file)
    if not os.path.exists(path):
        return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, _, val = line.partition('=')
                key = key.strip()
                val = val.strip()
                # 去除两端成对引号
                if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                    val = val[1:-1]
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


def find_latest_api(lines, section_start_idx, section_end_idx):
    """在指定范围内找出 API 数字最大的版本"""
    max_api = -1
    max_api_line_idx = -1

    for i in range(section_start_idx, section_end_idx):
        line = lines[i].strip()
        if line.startswith('|') and '|-----' not in line:
            cells = [c.strip() for c in line.split('|')]
            cells = [c for c in cells if c]
            if len(cells) >= 4 and cells[0] not in ['API', '']:
                api_cell = cells[0]
                link_match = re.match(r'\[(\d+)\]', api_cell)
                if link_match:
                    api_num = int(link_match.group(1))
                else:
                    api_match = re.match(r'(\d+)', api_cell)
                    if api_match:
                        api_num = int(api_match.group(1))
                    else:
                        continue
                if api_num > max_api:
                    max_api = api_num
                    max_api_line_idx = i

    return max_api, max_api_line_idx


# ============================================================================
# 内容解析
# ============================================================================

def parse_device_md(md_content):
    """解析设备支持清单 MD 文件，返回 (主标题, HTML 内容)"""
    lines = md_content.split('\n')
    html_parts = []

    in_table = False
    current_series = None
    is_first_row = False  # 标记是否是表头后的第一行
    main_title = None  # 存储一级标题

    for line in lines:
        stripped = line.strip()

        if stripped.startswith('# '):
            main_title = stripped[2:]  # 去掉 "# "
            continue
        elif stripped.startswith('> '):
            continue
        elif stripped.startswith('## '):
            if in_table:
                html_parts.append('</tbody></table></div>')
                in_table = False
            section_title = stripped[3:]
            html_parts.append(f'<h3 id="device-{section_title.lower()}">{section_title}</h3>')
            html_parts.append('<div class="table-responsive"><table>')
            in_table = True
            current_series = None
            is_first_row = True  # 新表格开始，下一行为表头
        elif stripped.startswith('|') and in_table:
            raw_cells = stripped.split('|')
            if raw_cells and raw_cells[0] == '':
                raw_cells = raw_cells[1:]
            if raw_cells and raw_cells[-1] == '':
                raw_cells = raw_cells[:-1]
            cells = [c.strip() for c in raw_cells]

            # 跳过分隔行
            if not cells or all(set(c) <= set('-:|') for c in cells):
                continue

            # 第一行是 MD 表头，转成 HTML thead
            if is_first_row:
                th = ''.join(f'<th>{html.escape(c)}</th>' for c in cells)
                html_parts.append(f'<thead><tr>{th}</tr></thead><tbody>')
                is_first_row = False
                continue

            if len(cells) >= 4:
                series = html.escape(cells[0]) if cells[0] else ''
                model = html.escape(cells[1])
                code = html.escape(cells[2])
                version = html.escape(cells[3])
                if series:
                    current_series = series
                    html_parts.append(f'<tr><td><b>{series}</b></td><td>{model}</td><td>{code}</td><td>{version}</td></tr>')
                else:
                    html_parts.append(f'<tr><td></td><td>{model}</td><td>{code}</td><td>{version}</td></tr>')

            is_first_row = False

    if in_table:
        html_parts.append('</tbody></table></div>')

    return main_title, '\n'.join(html_parts)


def render_md(md_content, device_content):
    """渲染 hoapi.md 的标题/表格/段落 + 设备清单 + 数据来源章节为 HTML
    （不含 site-title/intro/toc/footer/chrome）。"""
    lines = md_content.split('\n')

    # 扫描单框架部分的最大 API（用于自动 NEW 标签）
    single_start = -1
    single_end = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == '## 单框架':
            single_start = i
        elif single_start >= 0 and stripped.startswith('## '):
            single_end = i
            break
    if single_start >= 0 and single_end < 0:
        single_end = len(lines)

    latest_api = -1
    if single_start >= 0 and single_end > single_start:
        latest_api, _ = find_latest_api(lines, single_start, single_end)

    html_parts = []
    in_table = False
    current_section = ''
    current_api = None
    source_links = []

    for line in lines:
        stripped = line.strip()

        if stripped.startswith('# '):
            continue
        elif stripped.startswith('## '):
            if in_table:
                html_parts.append('</table>')
                html_parts.append('</div>')
                in_table = False
            section_title = stripped[3:]
            current_section = section_title
            if section_title == '数据来源':
                continue
            html_parts.append(f'<h2 id="{section_title.lower().replace(" ", "-")}">{section_title}</h2>')
        elif stripped.startswith('### '):
            html_parts.append(f'<h3>{stripped[4:]}</h3>')
        elif stripped.startswith('#### '):
            html_parts.append(f'<h4 id="{stripped[5:].lower().replace(" ", "-")}">{stripped[5:]}</h4>')
        elif stripped.startswith('|'):
            cells = [c.strip() for c in stripped.split('|')]
            cells = [c for c in cells if c]
            if not cells:
                continue
            if all(set(c) <= set('-:|') for c in cells):
                continue

            if not in_table:
                html_parts.append('<div class="table-responsive">')
                html_parts.append('<table>')
                in_table = True

            is_header = cells[0] in ['API', 'Version', '类型'] if cells else False
            row_parts = ['<thead><tr>'] if is_header else ['<tr>']

            # 提取当前行 API 数字
            if not is_header and current_section == '单框架' and len(cells) > 0:
                api_cell = cells[0]
                link_match = re.match(r'\[(\d+)\]', api_cell)
                if link_match:
                    current_api = int(link_match.group(1))
                else:
                    api_match = re.match(r'(\d+)', api_cell)
                    current_api = int(api_match.group(1)) if api_match else None

            for i, cell in enumerate(cells):
                # 转义原始文本，防止 <、>、& 被当作 HTML；后续 markdown 标记（**、[link](url)、emoji）不受影响
                cell = html.escape(cell)
                cell_processed = cell.replace('🔸', '<span class="beta">PREVIEW</span>')
                cell_processed = cell_processed.replace('🔹', '<span class="stable">LATEST</span>')
                cell_processed = cell_processed.replace('✅', '<span class="stable">ACTIVE</span>')
                cell_processed = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', cell_processed)

                # 处理超链接（仅第一列）
                link_match = re.match(r'\[(.+?)\]\((.+?)\)', cell)
                if link_match and i == 0:
                    cell_processed = f'<a href="{link_match.group(2)}" target="_blank" rel="noopener">{link_match.group(1)}</a>'

                # 版本名称标签处理（自动给最新 API 添加 NEW 标签）
                if i == 1 and not is_header and current_section not in ['版本类型说明']:
                    version_name = cell
                    note_col = cells[-1] if cells else ''
                    has_milestone = bool(re.search(r'\*\*[^*]+\*\*', note_col))

                    is_latest = (current_section == '单框架' and current_api is not None and current_api == latest_api)

                    version_match = re.match(r'^HarmonyOS\s+\d+(?:\.(\d+|x|X))*(?:/\w+)?', version_name)
                    next_match = re.match(r'^NEXT\s+', version_name)

                    def extract_paren_tags(text):
                        paren_tags = re.findall(r'\(([^)]+)\)', text)
                        main_text = re.sub(r'\s*\([^)]+\)', '', text).strip()
                        return main_text, paren_tags

                    milestone_tag = ' <sup class="milestone">里程碑</sup>' if has_milestone else ''

                    if version_match:
                        pure_version = version_match.group()
                        suffix = version_name[len(pure_version):].strip()
                        if suffix.upper() in ['NEW']:
                            suffix = ''
                        if suffix:
                            main_suffix, paren_tags = extract_paren_tags(suffix)
                            tag_parts = []
                            if main_suffix:
                                tag_parts.append(f' <sup class="beta">{main_suffix.upper()}</sup>')
                            for pt in paren_tags:
                                tag_parts.append(f' <sup class="paren">{pt.upper()}</sup>')
                            if is_latest:
                                tag_parts.append(f' <sup class="beta">NEW</sup>')
                            cell_processed = f'<b>{pure_version}</b>{"".join(tag_parts)}{milestone_tag}'
                        else:
                            new_tag = f' <sup class="beta">NEW</sup>' if is_latest else ''
                            cell_processed = f'<b>{pure_version}</b>{new_tag}{milestone_tag}'
                    elif next_match:
                        suffix = version_name[5:].strip()
                        main_suffix, paren_tags = extract_paren_tags(suffix)
                        tag_parts = []
                        if main_suffix:
                            tag_parts.append(f' <sup class="beta">{main_suffix.upper()}</sup>')
                        for pt in paren_tags:
                            tag_parts.append(f' <sup class="paren">{pt.upper()}</sup>')
                        cell_processed = f'<b>NEXT</b>{"".join(tag_parts)}{milestone_tag}'
                    else:
                        cell_processed = f'<b>{version_name}</b>{milestone_tag}'

                # 使用率进度条
                if current_section == '单框架' and i == 3 and not is_header:
                    pct_match = re.match(r'(\d+(?:\.\d+)?)\s*%?', cell)
                    if pct_match:
                        pct = float(pct_match.group(1))
                        row_parts.append(f'<td class="usage-bar" style="background: linear-gradient(to right, var(--usage-bar-start) {pct}%, var(--usage-bar-end) {pct}%);">{pct}%</td>')
                    else:
                        row_parts.append(f'<td>{cell_processed}</td>')
                else:
                    tag = 'th' if is_header else 'td'
                    row_parts.append(f'<{tag}>{cell_processed}</{tag}>')

            row_parts.append('</tr>')
            if is_header:
                row_parts.append('</thead><tbody>')
            html_parts.append(''.join(row_parts))
        elif stripped and not in_table:
            if current_section == '数据来源' and stripped.startswith('- https://'):
                url = stripped[2:].strip()
                link_text = 'Wikipedia: HarmonyOS version history' if 'wikipedia' in url else '华为开发者文档：SDK 版本使用率'
                source_links.append({'url': url, 'text': link_text})
                continue
            html_parts.append(f'<p>{stripped}</p>')
        elif not stripped and in_table:
            html_parts.append('</tbody>')
            html_parts.append('</table>')
            html_parts.append('</div>')
            in_table = False

    if in_table:
        html_parts.append('</tbody>')
        html_parts.append('</table>')
        html_parts.append('</div>')

    # 设备支持清单
    if device_content:
        device_title, device_html = parse_device_md(device_content)
        html_parts.append(f'<h2>{device_title}</h2>')
        html_parts.append(device_html)

    # 数据来源章节
    html_parts.append('<h2>数据来源</h2>')
    html_parts.append('<p class="source-links">')
    for link in source_links:
        html_parts.append(f'<a href="{link["url"]}" target="_blank" rel="noopener">{link["text"]}</a>')
    html_parts.append('<a href="https://developer.huawei.com/consumer/cn/doc/harmonyos-releases/support-device" target="_blank" rel="noopener">华为开发者文档：支持设备型号清单</a>')
    html_parts.append('</p>')

    return '\n'.join(html_parts)


# ============================================================================
# 外壳（chrome）：head/CSS/按钮/JS —— 语言无关，中英共用
# ============================================================================

def get_head():
    """返回文档头部：DOCTYPE + html + head（含 <style>），到 </head>"""
    return [
        '<!DOCTYPE html>',
        '<html>',
        '<head>',
        '<meta charset="utf-8">',
        '<meta http-equiv="X-UA-Compatible" content="IE=edge">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<title>HarmonyOS API Levels</title>',
        '<style>',
        '* { box-sizing: border-box; }',
        'html { font-size: 16px; }',

        # 浅色主题
        ':root {',
        '    --bg-color: #fff;',
        '    --text-color: #333;',
        '    --text-secondary: #666;',
        '    --border-color: #dee2e6;',
        '    --table-bg: #fff;',
        '    --table-hover: #f8f9fa;',
        '    --table-header-bg: #f8f9fa;',
        '    --usage-bar-start: #60ECAD;',
        '    --usage-bar-end: #fff;',
        '    --code-bg: #f4f4f4;',
        '    --title-color: #1a1a1a;',
        '    --link-color: #007DFF;',
        '    --beta-color: #007DFF;',
        '    --beta-bg: #e7f3ff;',
        '    --stable-color: #28a745;',
        '    --stable-bg: #e8f5e9;',
        '    --paren-color: #9c27b0;',
        '    --paren-bg: #f3e5f5;',
        '    --milestone-color: #e65100;',
        '    --milestone-bg: #fff3e0;',
        '    --title-gradient-1: rgba(0, 125, 255, 0.08);',
        '    --title-gradient-2: rgba(96, 236, 173, 0.08);',
        '}',

        # 深色主题
        '[data-theme="dark"] {',
        '    --bg-color: #1a1a2e;',
        '    --text-color: #e0e0e0;',
        '    --text-secondary: #a0a0a0;',
        '    --border-color: #3a3a4a;',
        '    --table-bg: #1a1a2e;',
        '    --table-hover: #2a2a3e;',
        '    --table-header-bg: #2a2a3e;',
        '    --usage-bar-start: #00C853;',
        '    --usage-bar-end: transparent;',
        '    --code-bg: #2a2a3e;',
        '    --title-color: #e0e0e0;',
        '    --link-color: #64B5F6;',
        '    --beta-color: #64B5F6;',
        '    --beta-bg: #1e3a5f;',
        '    --stable-color: #81C784;',
        '    --stable-bg: #1b3d1b;',
        '    --paren-color: #ce93d8;',
        '    --paren-bg: #4a148c;',
        '    --milestone-color: #ffb74d;',
        '    --milestone-bg: #e65100;',
        '    --title-gradient-1: rgba(100, 181, 246, 0.15);',
        '    --title-gradient-2: rgba(0, 200, 83, 0.15);',
        '}',

        'body {',
        '    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;',
        '    line-height: 1.5;',
        '    color: var(--text-color);',
        '    background-color: var(--bg-color);',
        '    margin: 0;',
        '    padding: 0;',
        '    transition: background-color 0.3s ease, color 0.3s ease;',
        '}',

        '.container { max-width: 960px; margin: 0 auto; }',
        '#site-title { font-size: 2.5rem; font-weight: 600; margin-bottom: 0.5rem; text-align: center; margin-top: 1rem; }',
        '#site-title a { color: var(--title-color); text-decoration: none; }',
        'h2 { font-size: 1.5rem; font-weight: 600; margin-top: 2rem; margin-bottom: 1rem; padding: 0.75rem 1rem 0.5rem; background: linear-gradient(135deg, var(--title-gradient-1) 0%, var(--title-gradient-2) 100%); border-radius: 8px; }',
        'h3 { font-size: 1.25rem; font-weight: 600; margin-top: 1.5rem; margin-bottom: 0.75rem; }',
        'h4 { font-size: 1rem; font-weight: 600; margin-top: 1rem; margin-bottom: 0.5rem; }',
        '#intro { font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 1.5rem; padding: 0.75rem 1rem 0.75rem 1.25rem; line-height: 1.7; border-left: 3px solid var(--link-color); background: linear-gradient(90deg, rgba(0, 125, 255, 0.05), transparent); text-align: left; }',

        # 主题切换按钮
        '#theme-toggle { position: fixed; top: 1rem; right: 1rem; background: var(--table-header-bg); border: 1px solid var(--border-color); border-radius: 50%; width: 44px; height: 44px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 1.25rem; transition: all 0.3s ease; z-index: 1000; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }',
        '#theme-toggle:hover { transform: scale(1.1); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }',
        '#theme-toggle svg { width: 22px; height: 22px; }',
        '#theme-toggle svg line, #theme-toggle svg circle, #theme-toggle svg path { stroke: var(--text-color); }',
        '[data-theme="dark"] #sun-icon { display: block; }',
        '[data-theme="dark"] #moon-icon { display: none; }',
        '[data-theme="light"] #sun-icon { display: none; }',
        '[data-theme="light"] #moon-icon { display: block; }',

        # 语言切换按钮（仅双语版渲染按钮，CSS 始终保留）
        '#lang-toggle { position: fixed; top: 1rem; right: 4rem; background: var(--table-header-bg); border: 1px solid var(--border-color); border-radius: 50%; width: 44px; height: 44px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 0.875rem; font-weight: 600; transition: all 0.3s ease; z-index: 1000; box-shadow: 0 2px 8px rgba(0,0,0,0.15); color: var(--text-color); }',
        '#lang-toggle:hover { transform: scale(1.1); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }',

        # 表格样式
        '.table-responsive { overflow-x: auto; margin-bottom: 1.5rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }',
        'table { width: 100%; border-collapse: collapse; background-color: var(--table-bg); border-radius: 8px; overflow: hidden; }',
        'th, td { padding: 0.875rem 1rem; text-align: left; border: none; vertical-align: middle; }',
        'thead { border-bottom: 2px solid var(--border-color); }',
        'tbody tr { border-bottom: 1px solid var(--border-color); transition: background-color 0.2s ease; }',
        'tbody tr:last-child { border-bottom: none; }',
        'th { font-weight: 600; background-color: var(--table-header-bg); border-bottom: 2px solid var(--border-color); white-space: nowrap; }',
        'th:nth-child(1), td:nth-child(1) { min-width: 3.5rem; text-align: center; }',
        'th:nth-child(2), td:nth-child(2) { min-width: 12rem; }',
        'th:nth-child(3), td:nth-child(3) { min-width: 7rem; white-space: nowrap; }',
        'th:nth-child(4), td:nth-child(4) { min-width: 5rem; text-align: center; }',
        'th:last-child, td:last-child { min-width: 10rem; }',
        'tr:hover { background-color: var(--table-hover); }',
        '.table-notes td { background-color: var(--table-hover); font-size: 0.875rem; color: var(--text-secondary); }',
        '.usage-cell { position: relative; min-width: 80px; }',
        '.usage-bar { border-radius: 4px; font-weight: 500; }',

        # 代码样式
        'code { background-color: var(--code-bg); padding: 0.2rem 0.4rem; border-radius: 3px; font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; font-size: 0.875em; }',

        # 标签样式
        '.beta { font-size: 0.75rem; font-weight: 600; color: var(--beta-color); background-color: var(--beta-bg); padding: 0.2rem 0.4rem; border-radius: 3px; margin-left: 0.25rem; white-space: nowrap; }',
        '.stable { font-size: 0.75rem; font-weight: 600; color: var(--stable-color); background-color: var(--stable-bg); padding: 0.2rem 0.4rem; border-radius: 3px; margin-left: 0.25rem; white-space: nowrap; }',
        '.paren { font-size: 0.75rem; font-weight: 600; color: var(--paren-color); background-color: var(--paren-bg); padding: 0.2rem 0.4rem; border-radius: 3px; margin-left: 0.25rem; white-space: nowrap; }',
        '.milestone { font-size: 0.75rem; font-weight: 600; color: var(--milestone-color); background-color: var(--milestone-bg); padding: 0.2rem 0.4rem; border-radius: 3px; margin-left: 0.25rem; white-space: nowrap; }',
        '.subversion { font-size: 0.875rem; color: var(--text-secondary); display: block; }',

        # 页脚样式
        '#site-footer { text-align: center; margin-top: 50px; padding: 40px 20px; color: var(--text-secondary); font-size: 0.85rem; }',
        '#site-footer p { margin: 5px 0; display: flex; align-items: center; justify-content: center; gap: 10px; flex-wrap: wrap; }',
        '#site-footer a { color: var(--link-color); text-decoration: none; }',
        '#site-footer a:hover { text-decoration: underline; }',
        '.separator { color: var(--text-secondary); }',
        '.github-link { display: inline-flex; align-items: center; gap: 5px; }',
        '.github-icon { width: 16px; height: 16px; }',
        'table a { color: var(--link-color); text-decoration: none; font-weight: 600; }',
        'table a:hover { text-decoration: underline; }',
        '.nowrap { white-space: nowrap; }',
        '.footnote { font-size: 0.75rem; vertical-align: super; }',
        '.source-links { margin-bottom: 1rem; font-size: 0.9rem; color: var(--text-secondary); }',
        '.source-links a { color: var(--link-color); text-decoration: none; display: inline-block; margin-right: 1.5rem; }',
        '.source-links a:hover { text-decoration: underline; }',
        '.source-links a::before { content: "→ "; color: var(--text-secondary); }',

        # 目录样式
        '#toc { background-color: var(--table-header-bg); border: 1px solid var(--border-color); border-radius: 8px; padding: 1rem 1.5rem; margin-bottom: 2rem; }',
        '#toc h3 { font-size: 1rem; font-weight: 600; margin: 0 0 0.75rem 0; color: var(--text-color); }',
        '#toc ul { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 0.5rem 1.5rem; }',
        '#toc li { margin: 0; }',
        '#toc a { color: var(--link-color); text-decoration: none; font-size: 0.9rem; }',
        '#toc a:hover { text-decoration: underline; }',
        '#toc .toc-section { font-weight: 600; }',
        '#toc .toc-sub { color: var(--text-secondary); font-weight: 400; }',

        # 移动端响应式样式
        '@media (max-width: 768px) {',
        '    html { font-size: 14px; }',
        '    .container { padding: 0 1rem; }',
        '    #site-title { font-size: 1.75rem; margin-bottom: 0.75rem; margin-top: 0.5rem; }',
        '    h2 { font-size: 1.25rem; margin-top: 1.5rem; padding: 0.5rem 0.75rem; }',
        '    #intro { padding: 0.5rem 0.75rem; margin-bottom: 1rem; }',
        '    #theme-toggle { top: 0.5rem; right: 0.5rem; width: 36px; height: 36px; }',
        '    #theme-toggle svg { width: 18px; height: 18px; }',
        '    #lang-toggle { top: 0.5rem; right: 3rem; width: 36px; height: 36px; font-size: 0.75rem; }',
        '    th, td { padding: 0.5rem 0.75rem; }',
        '    th:nth-child(1), td:nth-child(1) { min-width: 2.5rem; }',
        '    th:nth-child(2), td:nth-child(2) { min-width: 8rem; }',
        '    th:nth-child(3), td:nth-child(3) { min-width: 5rem; }',
        '    th:nth-child(4), td:nth-child(4) { min-width: 4rem; }',
        '    th:last-child, td:last-child { min-width: 6rem; }',
        '    #toc { padding: 0.75rem 1rem; margin-bottom: 1rem; }',
        '    #toc ul { gap: 0.25rem 1rem; }',
        '    #toc a { font-size: 0.85rem; }',
        '    .beta, .stable, .paren, .milestone { font-size: 0.65rem; padding: 0.15rem 0.3rem; }',
        '    #site-footer { margin-top: 30px; padding: 20px 15px; }',
        '    .source-links a { margin-right: 0.75rem; font-size: 0.85rem; }',
        '}',
        '@media (max-width: 480px) {',
        '    html { font-size: 13px; }',
        '    #site-title { font-size: 1.5rem; }',
        '    h2 { font-size: 1.1rem; padding: 0.4rem 0.5rem; }',
        '    th, td { padding: 0.4rem 0.5rem; font-size: 0.9rem; }',
        '    #lang-toggle { right: 2.5rem; }',
        '    #toc ul { flex-direction: column; gap: 0.25rem; }',
        '}',
        '</style>',
        '</head>',
    ]


def get_theme_toggle_button():
    """主题切换按钮"""
    return (
        '<button id="theme-toggle" title="切换主题">'
        '<svg id="moon-icon" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" stroke="currentColor" stroke-width="2" fill="none"/></svg>'
        '<svg id="sun-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="5" stroke="currentColor" stroke-width="2" fill="none"/><line x1="12" y1="1" x2="12" y2="3" stroke="currentColor" stroke-width="2"/><line x1="12" y1="21" x2="12" y2="23" stroke="currentColor" stroke-width="2"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64" stroke="currentColor" stroke-width="2"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" stroke="currentColor" stroke-width="2"/><line x1="1" y1="12" x2="3" y2="12" stroke="currentColor" stroke-width="2"/><line x1="21" y1="12" x2="23" y2="12" stroke="currentColor" stroke-width="2"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36" stroke="currentColor" stroke-width="2"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" stroke="currentColor" stroke-width="2"/></svg>'
        '</button>'
    )


def get_lang_toggle_button():
    """语言切换按钮（仅双语版使用）"""
    return '<button id="lang-toggle" title="切换语言">中</button>'


def get_theme_js():
    """主题切换 JS"""
    return '''<script>
(function() {
    const savedTheme = localStorage.getItem("theme");
    if (savedTheme) {
        document.documentElement.setAttribute("data-theme", savedTheme);
    } else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
        document.documentElement.setAttribute("data-theme", "dark");
    } else {
        document.documentElement.setAttribute("data-theme", "light");
    }

    const toggleTheme = () => {
        const currentTheme = document.documentElement.getAttribute("data-theme");
        const newTheme = currentTheme === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", newTheme);
        localStorage.setItem("theme", newTheme);
    };

    document.getElementById("theme-toggle").addEventListener("click", toggleTheme);

    if (window.matchMedia) {
        window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (e) => {
            if (!localStorage.getItem("theme")) {
                document.documentElement.setAttribute("data-theme", e.matches ? "dark" : "light");
            }
        });
    }
})();
</script>'''


def get_lang_js():
    """语言切换 JS：在中/英文内容块之间切换（仅双语版注入）"""
    return '''<script>
(function() {
    const zh = document.getElementById("page-zh");
    const en = document.getElementById("page-en");
    const toggle = document.getElementById("lang-toggle");
    if (!zh || !en || !toggle) return;

    function applyLang(lang) {
        document.documentElement.setAttribute("data-lang", lang);
        localStorage.setItem("lang", lang);
        zh.hidden = lang !== "zh";
        en.hidden = lang !== "en";
        toggle.textContent = lang === "zh" ? "EN" : "中";
        toggle.title = lang === "zh" ? "English" : "中文";
    }

    applyLang(localStorage.getItem("lang") || "zh");

    toggle.addEventListener("click", () => {
        const cur = document.documentElement.getAttribute("data-lang");
        applyLang(cur === "zh" ? "en" : "zh");
    });
})();
</script>'''


# ============================================================================
# 内容片段（语言相关，会被翻译）
# ============================================================================

def get_toc_html():
    """目录 HTML"""
    return [
        '<div id="toc">',
        '<h3>目录</h3>',
        '<ul>',
        '<li><a href="#单框架" class="toc-section">单框架</a></li>',
        '<li><a href="#双框架" class="toc-section">双框架</a></li>',
        '<li><a href="#版本类型说明" class="toc-section">版本类型说明</a></li>',
        '<li><a href="#device-手机" class="toc-sub">手机</a></li>',
        '<li><a href="#device-平板" class="toc-sub">平板</a></li>',
        '<li><a href="#device-pc" class="toc-sub">PC</a></li>',
        '<li><a href="#device-穿戴" class="toc-sub">穿戴</a></li>',
        '<li><a href="#device-iot" class="toc-sub">IoT</a></li>',
        '<li><a href="#device-预览版支持" class="toc-sub">预览版支持</a></li>',
        '</ul>',
        '</div>',
    ]


def get_footer_content():
    """页脚内容（container），不含 </body></html>"""
    return [
        '<div class="container">',
        '<div id="site-footer">',
        '<p>',
        '© 2026 <a href="https://github.com/secnotes" target="_blank">Security Notes</a>',
        '<span class="separator">|</span>',
        '<a href="https://github.com/secnotes/hoapi" target="_blank" class="github-link">',
        '<svg class="github-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.938 9.9 9.207 11.387.68.113.893-.261.893-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.218.694.825.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>',
        'Star on GitHub',
        '</a>',
        '</p>',
        '<p>',
        'Inspired by <a href="https://apilevels.com/" target="_blank">Android API Levels</a>',
        '</p>',
        '</div>',
        '</div>',
    ]


def build_content(md_content, device_content, last_updated):
    """构建页面正文内容（site-title + intro + toc + 表格 + 数据来源 + 页脚）。
    用 <!--content--> 注释包裹，便于 AI 翻译后整文件提取。不含 head/按钮/JS。"""
    updated_tag = f'（最近更新：{last_updated}）' if last_updated else ''
    parts = []

    # 顶部容器：标题 + 简介 + 目录
    parts.append('<div class="container">')
    parts.append('<h1 id="site-title"><a href="#">HarmonyOS API Levels</a></h1>')
    parts.append(
        f'<p id="intro">这是鸿蒙系统 API 和系统版本映射关系参考表，涵盖单框架与双框架两个技术路线。'
        f'单框架代表纯鸿蒙架构，双框架则兼容 Android 应用生态。'
        f'使用率数据来源于华为官方，定期更新。{updated_tag}</p>'
    )
    parts.extend(get_toc_html())
    parts.append('</div>')

    # 内容容器：表格/设备清单/数据来源
    parts.append('<div class="container">')
    parts.append('<div id="page-content">')
    parts.append(render_md(md_content, device_content))
    parts.append('</div>')
    parts.append('</div>')

    # 页脚
    parts.extend(get_footer_content())

    return '\n'.join(parts)


# ============================================================================
# 外壳组装
# ============================================================================

def wrap_single(content):
    """单语（中文）完整 HTML 文档：head + theme 按钮/JS + 内容。无语言按钮。"""
    parts = []
    parts.extend(get_head())
    parts.append('<body>')
    parts.append(get_theme_toggle_button())
    parts.append(content)
    parts.append(get_theme_js())
    parts.append('</body>')
    parts.append('</html>')
    return '\n'.join(parts)


def wrap_bilingual(zh_content, en_content):
    """双语完整 HTML 文档：head + theme/lang 按钮/JS + page-zh + page-en(hidden)。"""
    parts = []
    parts.extend(get_head())
    parts.append('<body>')
    parts.append(get_theme_toggle_button())
    parts.append(get_lang_toggle_button())
    parts.append('<div id="page-zh">')
    parts.append(zh_content)
    parts.append('</div>')
    parts.append('<div id="page-en" hidden>')
    parts.append(en_content)
    parts.append('</div>')
    parts.append(get_theme_js())
    parts.append(get_lang_js())
    parts.append('</body>')
    parts.append('</html>')
    return '\n'.join(parts)


# ============================================================================
# AI 翻译
# ============================================================================

# 结构性 id（CSS 钩子）——namespace 时不加前缀；浏览器对重复 id 仍应用样式
STRUCTURAL_IDS = {'site-title', 'intro', 'toc', 'page-content', 'site-footer'}


def translate_html_to_english(html_text, base_url, model, api_key):
    """用 OpenAI 兼容 API 将中文 HTML 整文件翻译为英文，严格保留结构。失败返回 None。"""
    endpoint = base_url.rstrip('/') + '/chat/completions'
    system_prompt = (
        "You are a professional translator. Translate all human-visible Chinese text in the HTML into natural English. "
        "STRICTLY preserve the entire HTML structure byte-for-byte: every tag, attribute, id, class, inline CSS, "
        "JavaScript code, and HTML comments (including <!--content--> / <!--/content--> markers) must remain unchanged. "
        "Do NOT translate or alter URLs, code, version numbers, or brand/model names "
        "(e.g., HarmonyOS, ArkTS, ArkUI, Mate, nova, Pura, HUAWEI, MatePad, MateBook, WATCH, MateTV). "
        "Only translate the visible Chinese text content. "
        "Output the complete HTML document only, with no markdown fences and no explanations."
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": html_text},
        ],
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    max_retries = 3
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=600)
            if resp.status_code == 429 or resp.status_code >= 500:
                last_err = f"HTTP {resp.status_code}"
                if attempt < max_retries:
                    wait = 20 * (attempt + 1)
                    print(f"⚠️ AI 返回 {resp.status_code}（限流/服务异常），{wait}s 后重试（第 {attempt+1}/{max_retries} 次）...")
                    time.sleep(wait)
                    continue
                break
            resp.raise_for_status()
            content = resp.json()['choices'][0]['message']['content'].strip()
            # 去除可能的 markdown 代码块包裹
            if content.startswith('```'):
                content = re.sub(r'^```[a-zA-Z]*\s*', '', content)
                content = re.sub(r'\s*```$', '', content)
            return content.strip()
        except requests.exceptions.Timeout:
            last_err = "请求超时"
            if attempt < max_retries:
                wait = 20 * (attempt + 1)
                print(f"⚠️ AI 超时，{wait}s 后重试（第 {attempt+1}/{max_retries} 次）...")
                time.sleep(wait)
                continue
            break
        except Exception as e:
            print(f"⚠️ AI 翻译失败，将回退到中文单语版：{e}")
            return None
    print(f"⚠️ AI 翻译多次失败（{last_err}），将回退到中文单语版")
    return None


def namespace_ids(text, prefix='en-'):
    """给英文内容中的锚点 id 与对应 href 加前缀，避免与中文块锚点冲突；
    结构性 id（CSS 钩子）保留。"""
    def keep(val):
        return val in STRUCTURAL_IDS

    def id_repl(m):
        val = m.group(1)
        return m.group(0) if keep(val) else f'id="{prefix}{val}"'

    def href_repl(m):
        val = m.group(1)
        return m.group(0) if keep(val) else f'href="#{prefix}{val}"'

    text = re.sub(r'id="([^"]+)"', id_repl, text)
    text = re.sub(r'href="#([^"]+)"', href_repl, text)
    return text


def extract_content(full_html):
    """从完整 HTML 中提取 <!--content-->…<!--/content--> 之间的内容。失败返回 None。"""
    m = re.search(r'<!--content-->(.*?)<!--/content-->', full_html, re.DOTALL)
    return m.group(1).strip() if m else None


# ============================================================================
# 主入口
# ============================================================================

def generate_html(md_file='hoapi.md', device_file='hodevice.md', html_file='index.html',
                  ai_base_url=None, ai_model=None, api_key=None):
    """从 MD 文件生成 HTML 文件。
    AI 配置优先级：入参 > 系统/Shell 环境变量 > .env 文件（AI_BASE_URL / AI_MODEL / AI_API_KEY）。
    配置齐全时生成双语版（AI 整文件翻译），否则仅中文版。"""
    load_env()  # 加载脚本同目录的 .env（不覆盖已有环境变量）
    try:
        with open(md_file, 'r', encoding='utf-8') as f:
            md_content = f.read()

        device_content = None
        try:
            with open(device_file, 'r', encoding='utf-8') as f:
                device_content = f.read()
        except FileNotFoundError:
            print(f"文件 {device_file} 不存在，跳过设备支持清单")

        last_updated = get_last_updated(md_file, device_file)
        zh_content = build_content(md_content, device_content, last_updated)

        # AI 配置：入参优先，回退环境变量
        base_url = ai_base_url or os.environ.get('AI_BASE_URL')
        model = ai_model or os.environ.get('AI_MODEL')
        key = api_key or os.environ.get('AI_API_KEY')

        if base_url and model and key:
            print("检测到 AI 配置，开始整文件翻译为英文...")
            # 用 content 标记包裹后交给 AI，便于翻译后整文件提取；最终输出不含这些标记
            single_for_ai = wrap_single('<!--content-->\n' + zh_content + '\n<!--/content-->')
            en_full = translate_html_to_english(single_for_ai, base_url, model, key)
            if en_full:
                en_content = extract_content(en_full)
                if en_content:
                    en_content = namespace_ids(en_content)
                    with open(html_file, 'w', encoding='utf-8') as f:
                        f.write(wrap_bilingual(zh_content, en_content))
                    print(f"已生成 {html_file}（中英双语版）")
                    return True
                print("⚠️ 无法从翻译结果中提取内容标记，回退到中文单语版")
        else:
            print("未配置 AI（AI_BASE_URL / AI_MODEL / AI_API_KEY），仅生成中文版")

        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(wrap_single(zh_content))
        print(f"已生成 {html_file}（中文版）")
        return True

    except FileNotFoundError:
        print(f"文件 {md_file} 不存在")
        return False
    except Exception as e:
        print(f"生成 HTML 错误: {e}")
        return False


def main():
    """主函数：生成 HTML"""
    print("=" * 60)
    print("HarmonyOS API HTML 生成脚本")
    print("=" * 60)

    print("\n正在生成 HTML...")
    success = generate_html()

    if success:
        print("\n✅ 完成!")
    else:
        print("\n❌ 生成失败")

    print("=" * 60)


if __name__ == '__main__':
    main()
