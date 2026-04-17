#!/usr/bin/env python3
"""
HarmonyOS API HTML 生成脚本
将 hoapi.md 转换为带样式的 HTML 页面
同时整合设备支持清单 (hodevice.md)
"""

import re


def parse_device_md(md_content):
    """解析设备支持清单 MD 文件，返回 HTML 内容"""
    lines = md_content.split('\n')
    html_parts = []

    in_table = False
    current_series = None
    is_first_row = False  # 标记是否是表头后的第一行
    main_title = None  # 存储一级标题

    for line in lines:
        stripped = line.strip()

        # 提取一级标题
        if stripped.startswith('# '):
            main_title = stripped[2:]  # 去掉 "# "
            continue
        elif stripped.startswith('> '):
            continue

        # 处理章节标题
        elif stripped.startswith('## '):
            if in_table:
                html_parts.append('</tbody></table></div>')
                in_table = False
            section_title = stripped[3:]
            html_parts.append(f'<h2 id="device-{section_title.lower()}">{section_title}</h2>')
            html_parts.append('<div class="table-responsive"><table>')
            html_parts.append('<thead><tr><th>设备系列</th><th>设备型号</th><th>型号代码</th><th>支持版本</th></tr></thead><tbody>')
            in_table = True
            current_series = None
            is_first_row = True  # 新表格开始，等待跳过表头行

        # 处理表格行
        elif stripped.startswith('|') and in_table:
            # 拆分并保留空单元格位置
            raw_cells = stripped.split('|')
            # 去掉首尾的空元素（由|开头和结尾产生）
            if raw_cells and raw_cells[0] == '':
                raw_cells = raw_cells[1:]
            if raw_cells and raw_cells[-1] == '':
                raw_cells = raw_cells[:-1]
            cells = [c.strip() for c in raw_cells]

            # 跳过分隔行（如 |----|----|）
            if not cells or all(set(c) <= set('-:|') for c in cells):
                continue

            # 跳过MD中的表头行（第一个数据行且包含"设备系列"等标题）
            if is_first_row and cells[0] == '设备系列':
                is_first_row = False
                continue

            # 判断是否有设备系列（非空的第一列）
            if len(cells) >= 4:
                series = cells[0] if cells[0] else ''
                model = cells[1]
                code = cells[2]
                version = cells[3]

                if series:
                    current_series = series
                    html_parts.append(f'<tr><td><b>{series}</b></td><td>{model}</td><td>{code}</td><td>{version}</td></tr>')
                else:
                    html_parts.append(f'<tr><td></td><td>{model}</td><td>{code}</td><td>{version}</td></tr>')

            is_first_row = False

    if in_table:
        html_parts.append('</tbody></table></div>')

    return main_title, '\n'.join(html_parts)


def md_to_html(md_content, device_content=None):
    """将Markdown内容转换为HTML"""
    lines = md_content.split('\n')

    # HTML 样式模板
    html_parts = get_html_template()

    in_table = False
    current_section = ''
    source_links = []  # 收集数据来源链接

    for line in lines:
        stripped = line.strip()

        # 处理标题
        if stripped.startswith('# '):
            continue
        elif stripped.startswith('## '):
            if in_table:
                html_parts.append('</table>')
                html_parts.append('</div>')
                in_table = False
            section_title = stripped[3:]
            current_section = section_title
            # 跳过数据来源章节，稍后处理
            if section_title == '数据来源':
                continue
            i18n_key = None
            if section_title == '单框架':
                i18n_key = 'section-single'
            elif section_title == '双框架':
                i18n_key = 'section-dual'
            elif section_title == '版本类型说明':
                i18n_key = 'section-notes'
            if i18n_key:
                html_parts.append(f'<h2 id="{section_title.lower().replace(" ", "-")}" data-i18n="{i18n_key}">{section_title}</h2>')
            else:
                html_parts.append(f'<h2 id="{section_title.lower().replace(" ", "-")}">{section_title}</h2>')
        elif stripped.startswith('### '):
            html_parts.append(f'<h3>{stripped[4:]}</h3>')
        elif stripped.startswith('#### '):
            html_parts.append(f'<h4 id="{stripped[5:].lower().replace(" ", "-")}">{stripped[5:]}</h4>')
        # 处理表格
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

            if is_header:
                row_parts = ['<thead><tr>']
            else:
                row_parts = ['<tr>']

            for i, cell in enumerate(cells):
                cell_processed = cell.replace('🔸', '<span class="beta">PREVIEW</span>')
                cell_processed = cell_processed.replace('🔹', '<span class="stable">LATEST</span>')
                cell_processed = cell_processed.replace('✅', '<span class="stable">ACTIVE</span>')
                cell_processed = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', cell_processed)

                # 处理超链接
                link_match = re.match(r'\[(.+?)\]\((.+?)\)', cell)
                if link_match:
                    link_text = link_match.group(1)
                    link_url = link_match.group(2)
                    if i == 0:
                        cell_processed = f'<a href="{link_url}" target="_blank" rel="noopener">{link_text}</a>'

                # 表头 i18n
                if is_header:
                    th_i18n_key = None
                    if cell == 'API':
                        th_i18n_key = 'th-api'
                    elif cell == '对应系统版本':
                        th_i18n_key = 'th-version'
                    elif cell == '发布时间':
                        th_i18n_key = 'th-date'
                    elif cell == '使用率':
                        th_i18n_key = 'th-usage'
                    elif cell == '支持的 Android 版本':
                        th_i18n_key = 'th-android'
                    elif cell == '备注':
                        th_i18n_key = 'th-note'
                    elif cell == '类型':
                        th_i18n_key = 'th-type'
                    elif cell == '说明':
                        th_i18n_key = 'th-desc'
                    elif cell == '作用':
                        th_i18n_key = 'th-purpose'

                    if th_i18n_key:
                        cell_processed = f'<span data-i18n="{th_i18n_key}">{cell}</span>'

                # 版本名称标签处理
                if i == 1 and not is_header and current_section not in ['版本类型说明']:
                    version_name = cell
                    note_col = cells[-1] if cells else ''
                    has_milestone = bool(re.search(r'\*\*[^*]+\*\*', note_col))

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

                        if suffix:
                            main_suffix, paren_tags = extract_paren_tags(suffix)
                            tag_parts = []
                            if main_suffix:
                                tag_parts.append(f' <sup class="beta">{main_suffix.upper()}</sup>')
                            for pt in paren_tags:
                                tag_parts.append(f' <sup class="paren">{pt.upper()}</sup>')
                            cell_processed = f'<b>{pure_version}</b>{"".join(tag_parts)}{milestone_tag}'
                        else:
                            cell_processed = f'<b>{pure_version}</b>{milestone_tag}'
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
        # 处理段落
        elif stripped and not in_table:
            # 收集数据来源链接，而不是输出
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

    # 添加设备支持清单
    if device_content:
        html_parts.append('<hr style="margin-top: 3rem; margin-bottom: 2rem; border: none; border-top: 1px solid var(--border-color);">')
        device_title, device_html = parse_device_md(device_content)
        html_parts.append(f'<h2>{device_title}</h2>')
        html_parts.append(device_html)

    # 添加数据来源章节（放到最后）
    html_parts.append('<hr style="margin-top: 3rem; margin-bottom: 2rem; border: none; border-top: 1px solid var(--border-color);">')
    html_parts.append('<h2>数据来源</h2>')
    html_parts.append('<p class="source-links">')
    for link in source_links:
        html_parts.append(f'<a href="{link["url"]}" target="_blank" rel="noopener">{link["text"]}</a>')
    # 添加设备支持清单来源链接
    html_parts.append(f'<a href="https://developer.huawei.com/consumer/cn/doc/harmonyos-releases/support-device" target="_blank" rel="noopener">华为开发者文档：支持设备型号清单</a>')
    html_parts.append('</p>')

    # 页脚
    html_parts.extend(get_html_footer())

    return '\n'.join(html_parts)


def get_html_template():
    """返回 HTML 模板（样式和头部）"""
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
        '#site-title { font-size: 2.5rem; font-weight: 600; margin-bottom: 0.5rem; text-align: center; }',
        '#site-title a { color: var(--title-color); text-decoration: none; }',
        'h2 { font-size: 1.5rem; font-weight: 600; margin-top: 2rem; margin-bottom: 1rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem; }',
        'h4 { font-size: 1.25rem; font-weight: 600; margin-top: 1.5rem; margin-bottom: 0.75rem; }',
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

        # 语言切换按钮
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
        '</style>',
        '</head>',
        '<body>',

        # 主题切换按钮
        '<button id="theme-toggle" title="切换主题">',
        '<svg id="moon-icon" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" stroke="currentColor" stroke-width="2" fill="none"/></svg>',
        '<svg id="sun-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="5" stroke="currentColor" stroke-width="2" fill="none"/><line x1="12" y1="1" x2="12" y2="3" stroke="currentColor" stroke-width="2"/><line x1="12" y1="21" x2="12" y2="23" stroke="currentColor" stroke-width="2"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64" stroke="currentColor" stroke-width="2"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" stroke="currentColor" stroke-width="2"/><line x1="1" y1="12" x2="3" y2="12" stroke="currentColor" stroke-width="2"/><line x1="21" y1="12" x2="23" y2="12" stroke="currentColor" stroke-width="2"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36" stroke="currentColor" stroke-width="2"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" stroke="currentColor" stroke-width="2"/></svg>',
        '</button>',
        '<button id="lang-toggle" title="切换语言">中</button>',

        # JavaScript
        get_javascript(),

        '<div class="container">',
        '<h1 id="site-title"><a href="#" data-i18n="site-title">HarmonyOS API Levels</a></h1>',
        '<p id="intro" data-i18n="intro">这是鸿蒙系统 API 和系统版本映射关系参考表，涵盖单框架与双框架两个技术路线。单框架代表纯鸿蒙架构，双框架则兼容 Android 应用生态。使用率数据来源于华为官方，定期更新。</p>',
        '</div>',
        '<div class="container">',
        '<div id="page-content">',
    ]


def get_javascript():
    """返回 JavaScript 代码"""
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

    const translations = {
        "site-title": { zh: "HarmonyOS API Levels", en: "HarmonyOS API Levels" },
        "intro": { zh: "这是鸿蒙系统 API 和系统版本映射关系参考表，涵盖单框架与双框架两个技术路线。单框架代表纯鸿蒙架构，双框架则兼容 Android 应用生态。使用率数据来源于华为官方，定期更新。", en: "This reference table documents the mapping between HarmonyOS API levels and system versions across both single-framework and dual-framework architectures. The single-framework represents pure HarmonyOS, while dual-framework maintains Android compatibility. Usage statistics are sourced from Huawei's official developer documentation and updated periodically." },
        "section-single": { zh: "单框架", en: "Single Framework" },
        "section-dual": { zh: "双框架", en: "Dual Framework" },
        "section-notes": { zh: "版本类型说明", en: "Version Types" },
        "section-device": { zh: "设备支持清单", en: "Device Support List" },
        "device-intro": { zh: "支持 HarmonyOS 的设备型号列表，数据来源于华为开发者网站。", en: "List of devices supporting HarmonyOS, sourced from Huawei's developer website." },
        "th-api": { zh: "API", en: "API" },
        "th-version": { zh: "对应系统版本", en: "System Version" },
        "th-date": { zh: "发布时间", en: "Release Date" },
        "th-usage": { zh: "使用率", en: "Usage" },
        "th-android": { zh: "支持的 Android 版本", en: "Android Version" },
        "th-note": { zh: "备注", en: "Notes" },
        "th-type": { zh: "类型", en: "Type" },
        "th-desc": { zh: "说明", en: "Description" },
        "th-purpose": { zh: "作用", en: "Purpose" },
    };

    const savedLang = localStorage.getItem("lang") || "zh";
    document.documentElement.setAttribute("data-lang", savedLang);
    document.getElementById("lang-toggle").textContent = savedLang === "zh" ? "EN" : "中";

    const applyLanguage = (lang) => {
        document.querySelectorAll("[data-i18n]").forEach(el => {
            const key = el.getAttribute("data-i18n");
            if (translations[key] && translations[key][lang]) {
                el.textContent = translations[key][lang];
            }
        });
        document.getElementById("lang-toggle").textContent = lang === "zh" ? "EN" : "中";
    };

    applyLanguage(savedLang);

    document.getElementById("lang-toggle").addEventListener("click", () => {
        const currentLang = document.documentElement.getAttribute("data-lang");
        const newLang = currentLang === "zh" ? "en" : "zh";
        document.documentElement.setAttribute("data-lang", newLang);
        localStorage.setItem("lang", newLang);
        applyLanguage(newLang);
    });
})();
</script>'''


def get_html_footer():
    """返回 HTML 页脚"""
    return [
        '</div>',
        '</div>',
        '<div class="container">',
        '<div id="site-footer">',
        '<p>',
        '© 2026 <a href="https://github.com/secnotes" target="_blank">Security Notes</a>',
        '<span class="separator">|</span>',
        '<a href="https://github.com/secnotes/harmonyoslevel" target="_blank" class="github-link">',
        '<svg class="github-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.938 9.9 9.207 11.387.68.113.893-.261.893-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.218.694.825.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>',
        'Star on GitHub',
        '</a>',
        '</p>',
        '</div>',
        '</div>',
        '</body>',
        '</html>',
    ]


def generate_html(md_file='hoapi.md', device_file='hodevice.md', html_file='index.html'):
    """从 MD 文件生成 HTML 文件"""
    try:
        with open(md_file, 'r', encoding='utf-8') as f:
            md_content = f.read()

        # 读取设备支持清单
        device_content = None
        try:
            with open(device_file, 'r', encoding='utf-8') as f:
                device_content = f.read()
        except FileNotFoundError:
            print(f"文件 {device_file} 不存在，跳过设备支持清单")

        html_content = md_to_html(md_content, device_content)

        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"已生成 {html_file}")
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