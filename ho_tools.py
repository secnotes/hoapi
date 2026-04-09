#!/usr/bin/env python3
"""
HO API Level 文档处理脚本
1. 爬取华为开发者网站获取版本使用率数据（或手动输入）
2. 更新 hoapi.md 文件
3. 将 MD 转换为 HTML
"""

import re
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# HarmonyOS SDK版本使用率数据（手动维护）
# 数据来源: https://developer.huawei.com/consumer/cn/doc/harmonyos-releases/sdk-version-percentage
# 注意: 请定期更新此数据
MANUAL_VERSION_DATA = {
    # 单框架 (HarmonyOS NEXT) 版本使用率
    '22': '12.5',  # HarmonyOS 6.0.2
    '21': '8.2',   # HarmonyOS 6.0.1
    '20': '15.3',  # HarmonyOS 6.0.0
    '19': '22.1',  # HarmonyOS 5.1.1
    '18': '18.7',  # HarmonyOS 5.1.0
    '17': '3.2',   # HarmonyOS 5.0.5
    '16': '5.8',   # HarmonyOS 5.0.4
    '15': '2.1',   # HarmonyOS 5.0.3
    '14': '1.5',   # HarmonyOS 5.0.2
    '13': '1.2',   # HarmonyOS 5.0.1
    '12': '3.3',   # HarmonyOS 5.0.0
    # 更早期版本使用率较低，可省略
}


def fetch_version_percentage_online():
    """尝试从华为开发者网站在线爬取数据"""
    url = "https://developer.huawei.com/consumer/cn/doc/harmonyos-releases/sdk-version-percentage"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }

    try:
        print(f"尝试访问: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        print(f"HTTP状态码: {response.status_code}")

        if response.status_code == 200:
            # 尝试解析页面内容
            soup = BeautifulSoup(response.text, 'html.parser')

            # 检查是否有JSON数据嵌入
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    # 查找包含版本数据的JSON
                    match = re.search(r'sdkVersionPercentage[^>]*>([^<]+)', script.string)
                    if match:
                        try:
                            data = json.loads(match.group(1))
                            print("从嵌入式JSON提取数据成功")
                            return data
                        except:
                            pass

        print("在线爬取失败，将使用本地数据")
        return None

    except Exception as e:
        print(f"网络请求错误: {e}")
        return None


def get_version_percentage():
    """获取版本使用率数据（优先在线，备用本地）"""
    # 先尝试在线获取
    online_data = fetch_version_percentage_online()

    if online_data:
        return online_data

    # 使用手动维护的数据
    print("\n使用本地维护的版本使用率数据...")
    print("注意: 数据需要定期手动更新")
    print(f"当前数据日期: 请参考 https://developer.huawei.com/consumer/cn/doc/harmonyos-releases/sdk-version-percentage")

    return MANUAL_VERSION_DATA


def update_md_file(version_data):
    """更新MD文件，添加/更新使用率数据"""
    md_file = 'hoapi.md'

    try:
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 只处理单框架表格
        # 找到单框架部分
        single_section_pattern = r'(## 单框架\s*\n+)(.*?)(\n+## 双框架)'
        match = re.search(single_section_pattern, content, re.DOTALL)

        if match:
            single_header = match.group(1)
            single_table = match.group(2)
            separator = match.group(3)

            # 检查是否已有使用率列
            if '| 使用率 |' in single_table:
                # 已有使用率列，直接更新数据
                print("单框架表格已包含使用率列，正在更新数据...")
                lines = single_table.split('\n')
                new_lines = []

                for line in lines:
                    if line.strip().startswith('|') and not '|-----' in line:
                        parts = [p.strip() for p in line.split('|')]
                        parts = [p for p in parts if p]

                        if len(parts) >= 5 and parts[0] not in ['API', '']:
                            api_cell = parts[0]
                            # 从链接格式中提取API数字 [22](url) -> 22
                            link_match = re.match(r'\[(\d+)\]\(.+\)', api_cell)
                            if link_match:
                                api = link_match.group(1)
                            else:
                                api = api_cell

                            usage = version_data.get(api, '-')
                            if usage and usage != '-':
                                usage = f"{usage}%"

                            # 保持原有格式，只更新使用率列（第4列，索引3）
                            original_parts = line.split('|')
                            if original_parts[0] == '':
                                original_parts = original_parts[1:]
                            if original_parts[-1] == '':
                                original_parts = original_parts[:-1]

                            if len(original_parts) >= 5:
                                original_parts[3] = f' {usage} '
                                new_line = '|' + '|'.join(original_parts) + '|'
                                new_lines.append(new_line)
                            else:
                                new_lines.append(line)
                        else:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)

                new_table = '\n'.join(new_lines)
                content = single_header + new_table + separator + content[match.end():]

            else:
                # 需要添加使用率列
                print("添加使用率列到单框架表格...")
                lines = single_table.split('\n')
                new_lines = []

                for i, line in enumerate(lines):
                    if i == 0 and line.startswith('| API'):
                        # 修改表头
                        new_lines.append('| API | 对应系统版本 | 发布时间 | 使用率 | 备注 |')
                    elif '|-----' in line:
                        new_lines.append('|-----|-------------|---------|--------|------|')
                    elif line.strip().startswith('|'):
                        parts = [p.strip() for p in line.split('|')]
                        parts = [p for p in parts if p]

                        if len(parts) >= 4:
                            api = parts[0]
                            usage = version_data.get(api, '-')
                            if usage and usage != '-':
                                usage = f"{usage}%"

                            new_line = f"| {api} | {parts[1]} | {parts[2]} | {usage} | {parts[3]} |"
                            new_lines.append(new_line)
                        else:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)

                new_table = '\n'.join(new_lines)
                content = single_header + new_table + separator + content[match.end():]

            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"已更新 {md_file}")
            return content

        else:
            print("未找到单框架表格")
            return content

    except FileNotFoundError:
        print(f"文件 {md_file} 不存在")
        return None
    except Exception as e:
        print(f"更新文件错误: {e}")
        return None


def md_to_html(md_content, version_data=None):
    """将Markdown内容转换为HTML，参考androidapi.html样式"""
    import html

    lines = md_content.split('\n')

    # 构建HTML
    html_parts = [
        '<!DOCTYPE html>',
        '<html>',
        '<head>',
        '<meta charset="utf-8">',
        '<meta http-equiv="X-UA-Compatible" content="IE=edge">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<title>HarmonyOS API Levels</title>',
        '<style>',
        # 基本样式 - 参考androidapi.html
        '* { box-sizing: border-box; }',
        'html { font-size: 16px; }',

        # 浅色主题（默认）
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
        # 容器样式
        '.container {',
        '    max-width: 960px;',
        '    margin: 0 auto;',
        '}',
        # 标题样式
        '#site-title {',
        '    font-size: 2.5rem;',
        '    font-weight: 600;',
        '    margin-bottom: 0.5rem;',
        '    text-align: center;',
        '}',
        '#site-title a {',
        '    color: var(--title-color);',
        '    text-decoration: none;',
        '}',
        'h2 {',
        '    font-size: 1.5rem;',
        '    font-weight: 600;',
        '    margin-top: 2rem;',
        '    margin-bottom: 1rem;',
        '    border-bottom: 1px solid var(--border-color);',
        '    padding-bottom: 0.5rem;',
        '}',
        'h4 {',
        '    font-size: 1.25rem;',
        '    font-weight: 600;',
        '    margin-top: 1.5rem;',
        '    margin-bottom: 0.75rem;',
        '}',
        '#intro {',
        '    font-size: 0.9rem;',
        '    color: var(--text-secondary);',
        '    margin-bottom: 1.5rem;',
        '    padding: 0.75rem 1rem 0.75rem 1.25rem;',
        '    line-height: 1.7;',
        '    border-left: 3px solid var(--link-color);',
        '    background: linear-gradient(90deg, rgba(0, 125, 255, 0.05), transparent);',
        '    text-align: left;',
        '}',
        # 主题切换按钮
        '#theme-toggle {',
        '    position: fixed;',
        '    top: 1rem;',
        '    right: 1rem;',
        '    background: var(--table-header-bg);',
        '    border: 1px solid var(--border-color);',
        '    border-radius: 50%;',
        '    width: 44px;',
        '    height: 44px;',
        '    cursor: pointer;',
        '    display: flex;',
        '    align-items: center;',
        '    justify-content: center;',
        '    font-size: 1.25rem;',
        '    transition: all 0.3s ease;',
        '    z-index: 1000;',
        '    box-shadow: 0 2px 8px rgba(0,0,0,0.15);',
        '}',
        '#theme-toggle:hover {',
        '    transform: scale(1.1);',
        '    box-shadow: 0 4px 12px rgba(0,0,0,0.2);',
        '}',
        '#theme-toggle svg {',
        '    width: 22px;',
        '    height: 22px;',
        '}',
        '#theme-toggle svg line, #theme-toggle svg circle, #theme-toggle svg path {',
        '    stroke: var(--text-color);',
        '}',
        '[data-theme="dark"] #sun-icon { display: block; }',
        '[data-theme="dark"] #moon-icon { display: none; }',
        '[data-theme="light"] #sun-icon { display: none; }',
        '[data-theme="light"] #moon-icon { display: block; }',
        # 语言切换按钮
        '#lang-toggle {',
        '    position: fixed;',
        '    top: 1rem;',
        '    right: 4rem;',
        '    background: var(--table-header-bg);',
        '    border: 1px solid var(--border-color);',
        '    border-radius: 50%;',
        '    width: 44px;',
        '    height: 44px;',
        '    cursor: pointer;',
        '    display: flex;',
        '    align-items: center;',
        '    justify-content: center;',
        '    font-size: 0.875rem;',
        '    font-weight: 600;',
        '    transition: all 0.3s ease;',
        '    z-index: 1000;',
        '    box-shadow: 0 2px 8px rgba(0,0,0,0.15);',
        '    color: var(--text-color);',
        '}',
        '#lang-toggle:hover {',
        '    transform: scale(1.1);',
        '    box-shadow: 0 4px 12px rgba(0,0,0,0.2);',
        '}',
        # 表格样式
        '.table-responsive {',
        '    overflow-x: auto;',
        '    margin-bottom: 1.5rem;',
        '    border-radius: 8px;',
        '    box-shadow: 0 1px 3px rgba(0,0,0,0.08);',
        '}',
        'table {',
        '    width: 100%;',
        '    border-collapse: collapse;',
        '    background-color: var(--table-bg);',
        '    border-radius: 8px;',
        '    overflow: hidden;',
        '}',
        'th, td {',
        '    padding: 0.875rem 1rem;',
        '    text-align: left;',
        '    border: none;',
        '    vertical-align: middle;',
        '}',
        'thead {',
        '    border-bottom: 2px solid var(--border-color);',
        '}',
        'tbody tr {',
        '    border-bottom: 1px solid var(--border-color);',
        '    transition: background-color 0.2s ease;',
        '}',
        'tbody tr:last-child {',
        '    border-bottom: none;',
        '}',
        'th {',
        '    font-weight: 600;',
        '    background-color: var(--table-header-bg);',
        '    border-bottom: 2px solid var(--border-color);',
        '    white-space: nowrap;',
        '}',
        # 列宽优化
        'th:nth-child(1), td:nth-child(1) {',
        '    min-width: 3.5rem;',
        '    text-align: center;',
        '}',
        'th:nth-child(2), td:nth-child(2) {',
        '    min-width: 12rem;',
        '}',
        'th:nth-child(3), td:nth-child(3) {',
        '    min-width: 7rem;',
        '    white-space: nowrap;',
        '}',
        'th:nth-child(4), td:nth-child(4) {',
        '    min-width: 5rem;',
        '    text-align: center;',
        '}',
        'th:last-child, td:last-child {',
        '    min-width: 10rem;',
        '}',
        'tr:hover {',
        '    background-color: var(--table-hover);',
        '}',
        '.table-notes td {',
        '    background-color: var(--table-hover);',
        '    font-size: 0.875rem;',
        '    color: var(--text-secondary);',
        '}',
        '.table-notes ul {',
        '    margin: 0;',
        '    padding-left: 1.5rem;',
        '}',
        '.table-notes li {',
        '    margin-bottom: 0.25rem;',
        '}',
        # 使用率进度条样式 - 优化深色模式显示
        '.usage-cell {',
        '    position: relative;',
        '    min-width: 80px;',
        '}',
        '.usage-bar {',
        '    border-radius: 4px;',
        '    font-weight: 500;',
        '}',
        # 代码样式
        'code {',
        '    background-color: var(--code-bg);',
        '    padding: 0.2rem 0.4rem;',
        '    border-radius: 3px;',
        '    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;',
        '    font-size: 0.875em;',
        '}',
        # Beta/预览标签
        '.beta {',
        '    font-size: 0.75rem;',
        '    font-weight: 600;',
        '    color: var(--beta-color);',
        '    background-color: var(--beta-bg);',
        '    padding: 0.2rem 0.4rem;',
        '    border-radius: 3px;',
        '    margin-left: 0.25rem;',
        '}',
        '.stable {',
        '    font-size: 0.75rem;',
        '    font-weight: 600;',
        '    color: var(--stable-color);',
        '    background-color: var(--stable-bg);',
        '    padding: 0.2rem 0.4rem;',
        '    border-radius: 3px;',
        '    margin-left: 0.25rem;',
        '}',
        # 子版本样式
        '.subversion {',
        '    font-size: 0.875rem;',
        '    color: var(--text-secondary);',
        '    display: block;',
        '}',
        # 页脚
        '#site-footer {',
        '    text-align: center;',
        '    margin-top: 50px;',
        '    padding: 40px 20px;',
        '    color: var(--text-secondary);',
        '    font-size: 0.85rem;',
        '}',
        '#site-footer p {',
        '    margin: 5px 0;',
        '    display: flex;',
        '    align-items: center;',
        '    justify-content: center;',
        '    gap: 10px;',
        '    flex-wrap: wrap;',
        '}',
        '#site-footer a {',
        '    color: var(--link-color);',
        '    text-decoration: none;',
        '}',
        '#site-footer a:hover {',
        '    text-decoration: underline;',
        '}',
        '.separator {',
        '    color: var(--text-secondary);',
        '}',
        '.github-link {',
        '    display: inline-flex;',
        '    align-items: center;',
        '    gap: 5px;',
        '}',
        '.github-icon {',
        '    width: 16px;',
        '    height: 16px;',
        '}',
        # 表格中的链接样式
        'table a {',
        '    color: var(--link-color);',
        '    text-decoration: none;',
        '    font-weight: 600;',
        '}',
        'table a:hover {',
        '    text-decoration: underline;',
        '}',
        '.nowrap { white-space: nowrap; }',
        '.footnote { font-size: 0.75rem; vertical-align: super; }',
        '.source-links {',
        '    margin-bottom: 1rem;',
        '    font-size: 0.9rem;',
        '    color: var(--text-secondary);',
        '}',
        '.source-links a {',
        '    color: var(--link-color);',
        '    text-decoration: none;',
        '    display: inline-block;',
        '    margin-right: 1.5rem;',
        '}',
        '.source-links a:hover {',
        '    text-decoration: underline;',
        '}',
        '.source-links a::before {',
        '    content: \'→ \';',
        '    color: var(--text-secondary);',
        '}',
        '</style>',
        '</head>',
        '<body>',
        # 主题切换按钮
        '<button id="theme-toggle" title="切换主题">',
        '<svg id="moon-icon" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" stroke="currentColor" stroke-width="2" fill="none"/></svg>',
        '<svg id="sun-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="5" stroke="currentColor" stroke-width="2" fill="none"/><line x1="12" y1="1" x2="12" y2="3" stroke="currentColor" stroke-width="2"/><line x1="12" y1="21" x2="12" y2="23" stroke="currentColor" stroke-width="2"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64" stroke="currentColor" stroke-width="2"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" stroke="currentColor" stroke-width="2"/><line x1="1" y1="12" x2="3" y2="12" stroke="currentColor" stroke-width="2"/><line x1="21" y1="12" x2="23" y2="12" stroke="currentColor" stroke-width="2"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36" stroke="currentColor" stroke-width="2"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" stroke="currentColor" stroke-width="2"/></svg>',
        '</button>',
        '<button id="lang-toggle" title="切换语言">中</button>',
        '<script>',
        '(function() {',
        '    // 检查本地存储的主题设置',
        '    const savedTheme = localStorage.getItem("theme");',
        '    if (savedTheme) {',
        '        document.documentElement.setAttribute("data-theme", savedTheme);',
        '    } else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {',
        '        // 获取系统主题偏好',
        '        document.documentElement.setAttribute("data-theme", "dark");',
        '    } else {',
        '        document.documentElement.setAttribute("data-theme", "light");',
        '    }',
        '    // 主题切换函数',
        '    const toggleTheme = () => {',
        '        const currentTheme = document.documentElement.getAttribute("data-theme");',
        '        const newTheme = currentTheme === "dark" ? "light" : "dark";',
        '        document.documentElement.setAttribute("data-theme", newTheme);',
        '        localStorage.setItem("theme", newTheme);',
        '    };',
        '    // 绑定按钮点击事件',
        '    document.getElementById("theme-toggle").addEventListener("click", toggleTheme);',
        '    // 监听系统主题变化',
        '    if (window.matchMedia) {',
        '        window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (e) => {',
        '            if (!localStorage.getItem("theme")) {',
        '                document.documentElement.setAttribute("data-theme", e.matches ? "dark" : "light");',
        '            }',
        '        });',
        '    }',
        '',
        '    // 语言切换功能',
        '    const translations = {',
        '        "site-title": { zh: "HarmonyOS API Levels", en: "HarmonyOS API Levels" },',
        '        "intro": { zh: "这是鸿蒙系统 API 和系统版本映射关系参考表，涵盖单框架与双框架两个技术路线。单框架代表纯鸿蒙架构，双框架则兼容 Android 应用生态。使用率数据来源于华为官方，定期更新。", en: "This reference table documents the mapping between HarmonyOS API levels and system versions across both single-framework and dual-framework architectures. The single-framework represents pure HarmonyOS, while dual-framework maintains Android compatibility. Usage statistics are sourced from Huawei\'s official developer documentation and updated periodically." },',
        '        "section-single": { zh: "单框架", en: "Single Framework" },',
        '        "section-dual": { zh: "双框架", en: "Dual Framework" },',
        '        "section-notes": { zh: "版本类型说明", en: "Version Types" },',
        '        "th-api": { zh: "API", en: "API" },',
        '        "th-version": { zh: "对应系统版本", en: "System Version" },',
        '        "th-date": { zh: "发布时间", en: "Release Date" },',
        '        "th-usage": { zh: "使用率", en: "Usage" },',
        '        "th-android": { zh: "支持的 Android 版本", en: "Android Version" },',
        '        "th-note": { zh: "备注", en: "Notes" },',
        '        "th-type": { zh: "类型", en: "Type" },',
        '        "th-desc": { zh: "说明", en: "Description" },',
        '        "th-purpose": { zh: "作用", en: "Purpose" },',
        '    };',
        '',
        '    const savedLang = localStorage.getItem("lang") || "zh";',
        '    document.documentElement.setAttribute("data-lang", savedLang);',
        '    document.getElementById("lang-toggle").textContent = savedLang === "zh" ? "EN" : "中";',
        '',
        '    const applyLanguage = (lang) => {',
        '        document.querySelectorAll("[data-i18n]").forEach(el => {',
        '            const key = el.getAttribute("data-i18n");',
        '            if (translations[key] && translations[key][lang]) {',
        '                el.textContent = translations[key][lang];',
        '            }',
        '        });',
        '        document.getElementById("lang-toggle").textContent = lang === "zh" ? "EN" : "中";',
        '    };',
        '',
        '    applyLanguage(savedLang);',
        '',
        '    document.getElementById("lang-toggle").addEventListener("click", () => {',
        '        const currentLang = document.documentElement.getAttribute("data-lang");',
        '        const newLang = currentLang === "zh" ? "en" : "zh";',
        '        document.documentElement.setAttribute("data-lang", newLang);',
        '        localStorage.setItem("lang", newLang);',
        '        applyLanguage(newLang);',
        '    });',
        '})();',
        '</script>',
        '<div class="container">',
        '<h1 id="site-title"><a href="#" data-i18n="site-title">HarmonyOS API Levels</a></h1>',
        '<p id="intro" data-i18n="intro">这是鸿蒙系统 API 和系统版本映射关系参考表，涵盖单框架与双框架两个技术路线。单框架代表纯鸿蒙架构，双框架则兼容 Android 应用生态。使用率数据来源于华为官方，定期更新。</p>',
        '</div>',
        '<div class="container">',
        '<div id="page-content">',
    ]

    in_table = False
    table_id = 0
    current_section = ''

    for line in lines:
        stripped = line.strip()

        # 处理标题
        if stripped.startswith('# '):
            continue  # 主标题已处理
        elif stripped.startswith('## '):
            if in_table:
                html_parts.append('</table>')
                html_parts.append('</div>')
                in_table = False
            section_title = stripped[3:]
            current_section = section_title
            # 添加data-i18n属性用于语言切换
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

            # 判断是否是分隔行
            if all(set(c) <= set('-:|') for c in cells):
                continue

            if not in_table:
                html_parts.append('<div class="table-responsive">')
                html_parts.append('<table>')
                in_table = True
                table_id += 1

            # 构建表格行
            is_header = cells[0] in ['API', 'Version', '类型'] if cells else False

            # 表头使用thead标签
            if is_header:
                row_parts = ['<thead><tr>']
            else:
                row_parts = ['<tr>']

            for i, cell in enumerate(cells):
                # 处理特殊标记
                cell_processed = cell.replace('🔸', '<span class="beta">PREVIEW</span>')
                cell_processed = cell_processed.replace('🔹', '<span class="stable">LATEST</span>')
                cell_processed = cell_processed.replace('✅', '<span class="stable">ACTIVE</span>')
                cell_processed = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', cell_processed)

                # 处理Markdown超链接 [text](url)
                link_match = re.match(r'\[(.+?)\]\((.+?)\)', cell)
                if link_match:
                    link_text = link_match.group(1)
                    link_url = link_match.group(2)
                    # API列（第1列，索引0）添加超链接
                    if i == 0:
                        cell_processed = f'<a href="{link_url}" target="_blank" rel="noopener">{link_text}</a>'

                # 表头添加data-i18n属性
                if is_header:
                    # 根据列内容和当前section确定i18n key
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

                # 根据备注内容添加版本状态标签
                # 在版本名称列（第2列，索引1）添加标签
                # 跳过版本类型说明表格
                if i == 1 and not is_header and current_section not in ['版本类型说明']:
                    version_name = cell
                    # 检查备注中的版本类型信息
                    note_col = cells[-1] if cells else ''

                    # 根据版本名称判断状态
                    # 检查是否是标准格式: HarmonyOS + 版本号 (如 HarmonyOS 6.0.0)
                    is_standard_format = bool(re.match(r'^HarmonyOS\s+\d+(\.\d+)*$', version_name))

                    # 检查是否是非标准版本或需要特殊标签
                    status_tag = None

                    # 根据版本名称中的关键词判断标签
                    if '(Internal)' in version_name or 'Internal' in note_col:
                        status_tag = 'INTERNAL'
                    elif '(Canary)' in version_name or 'Canary' in note_col:
                        status_tag = 'CANARY'
                    elif 'Developer Beta' in version_name:
                        status_tag = 'BETA'
                    elif 'Developer Preview' in version_name:
                        status_tag = 'PREVIEW'
                    elif 'Preview' in version_name and 'Developer' not in version_name:
                        status_tag = 'PREVIEW'
                    elif 'Lite' in version_name or '(Wearable)' in version_name:
                        status_tag = 'LITE'
                    elif '(TV)' in version_name:
                        status_tag = 'TV'
                    elif 'Developer' in version_name:
                        status_tag = 'DEV'
                    # 对于标准格式，只在明确标注预览/测试时添加标签
                    # 注意：避免将正式版本（如包含"Beta"字样但实际已发布）误标记
                    elif '预览版本' in note_col:
                        status_tag = 'PREVIEW'
                    # 其他非标准格式
                    elif not is_standard_format:
                        if 'Preview' in note_col:
                            status_tag = 'PREVIEW'
                        elif '测试' in note_col:
                            status_tag = 'BETA'

                    if status_tag:
                        cell_processed = f'<b>{version_name}</b> <sup class="beta">{status_tag}</sup>'
                    else:
                        # 标准版本或无特殊标签，加粗显示
                        cell_processed = f'<b>{version_name}</b>'

                # 使用率列特殊处理（单框架表格第4列，索引3）
                if current_section == '单框架' and i == 3 and not is_header:
                    # 检查是否是使用率数据（百分比）
                    pct_match = re.match(r'(\d+(?:\.\d+)?)\s*%?', cell)
                    if pct_match:
                        pct = float(pct_match.group(1))
                        # 使用CSS变量实现主题自适应的进度条
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
        # 处理普通段落
        elif stripped and not in_table:
            # 特殊处理"数据来源"章节的链接
            if current_section == '数据来源' and stripped.startswith('- https://'):
                # 提取URL
                url = stripped[2:].strip()
                # 根据URL生成友好的链接文字
                link_text = 'Wikipedia: HarmonyOS version history' if 'wikipedia' in url else '华为开发者文档：SDK 版本使用率'
                if 'source_links_started' not in dir():
                    source_links_started = True
                    html_parts.append(f'<p class="source-links">')
                html_parts.append(f'<a href="{url}" target="_blank" rel="noopener">{link_text}</a>')
            else:
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

    # 添加页脚
    html_parts.append('</div>')
    html_parts.append('</div>')
    html_parts.append('<div class="container">')
    html_parts.append('<div id="site-footer">')
    html_parts.append('<p>')
    html_parts.append('© 2026 <a href="https://github.com/secnotes" target="_blank">Security Notes</a>')
    html_parts.append('<span class="separator">|</span>')
    html_parts.append('<a href="https://github.com/secnotes/harmonyoslevel" target="_blank" class="github-link">')
    html_parts.append('<svg class="github-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.938 9.9 9.207 11.387.68.113.893-.261.893-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.218.694.825.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>')
    html_parts.append('Star on GitHub')
    html_parts.append('</a>')
    html_parts.append('</p>')
    html_parts.append('</div>')
    html_parts.append('</div>')
    html_parts.append('</body>')
    html_parts.append('</html>')

    return '\n'.join(html_parts)


def main():
    print("=" * 60)
    print("HarmonyOS API Level 文档处理脚本")
    print("=" * 60)

    # 步骤1: 获取版本使用率数据
    print("\n[步骤1] 获取HarmonyOS版本使用率数据...")
    version_data = get_version_percentage()

    if version_data:
        print(f"\n获取到的版本数据:")
        for api, pct in sorted(version_data.items(), key=lambda x: int(x[0]), reverse=True):
            print(f"  API {api}: {pct}%")
    else:
        print("\n警告: 未能获取版本使用率数据，将使用 '-' 作为占位符")
        version_data = {}

    # 步骤2: 更新MD文件
    print("\n[步骤2] 更新 harmonyosapi.md 文件...")
    updated_content = update_md_file(version_data)

    if not updated_content:
        print("读取原始文件...")
        try:
            with open('hoapi.md', 'r', encoding='utf-8') as f:
                updated_content = f.read()
        except FileNotFoundError:
            print("错误: hoapi.md 文件不存在")
            return

    # 步骤3: 转换为HTML
    print("\n[步骤3] 转换为HTML...")
    html_content = md_to_html(updated_content, version_data)

    html_file = 'index.html'
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\n✅ 完成! HTML文件已生成: {html_file}")
    print("=" * 60)


if __name__ == '__main__':
    main()