#!/usr/bin/env python3
"""
HarmonyOS API 版本使用率数据获取脚本
从华为开发者网站爬取或使用本地数据更新 hoapi.md
"""

import re
import json
import shutil
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def launch_chromium(p):
    """启动浏览器：依次尝试 Playwright 自带 Chromium -> 系统 Chrome -> 系统 Chromium。
    避免 Playwright 内置浏览器未安装时直接失败。"""
    attempts = [
        {},  # Playwright 自带 Chromium
        {'channel': 'chrome'},  # 系统 Google Chrome
    ]
    system_chromium = shutil.which('chromium')
    if system_chromium:
        attempts.append({'executable_path': system_chromium})  # 系统 Chromium（如 Debian/Kali）
    for kwargs in attempts:
        try:
            return p.chromium.launch(headless=True, **kwargs)
        except Exception:
            continue
    raise RuntimeError('无法启动 Chromium/Chrome：请安装 Playwright 内置浏览器（playwright install chromium）或系统 Chrome/Chromium')

# HarmonyOS SDK版本使用率数据（手动维护）
# 数据来源: https://developer.huawei.com/consumer/cn/doc/harmonyos-releases/sdk-version-percentage
# 注意: 请定期更新此数据
MANUAL_VERSION_DATA = {
    # 单框架 (HarmonyOS NEXT) 版本使用率
    # 与 hoapi.md 保持同步；在线抓取失败时作为回退数据
    '24': '36.73',  # HarmonyOS 6.1.1
    '23': '58.87',  # HarmonyOS 6.1.0
    '22': '2.85',   # HarmonyOS 6.0.2
    '21': '0.62',   # HarmonyOS 6.0.1
    '20': '0.06',   # HarmonyOS 6.0.0
    '19': '0.17',   # HarmonyOS 5.1.1
    '18': '0.10',   # HarmonyOS 5.1.0
    '17': '0.36',   # HarmonyOS 5.0.5
    '15': '0',      # HarmonyOS 5.0.3
    '14': '0',      # HarmonyOS 5.0.2
    '13': '0',      # HarmonyOS 5.0.1
    '12': '0',      # HarmonyOS 5.0.0
}


def fetch_version_percentage_online():
    """使用 Playwright 从华为开发者网站在线爬取数据"""
    url = "https://developer.huawei.com/consumer/cn/doc/harmonyos-releases/sdk-version-percentage"

    print(f"尝试访问: {url}")
    try:
        with sync_playwright() as p:
            browser = launch_chromium(p)
            page = browser.new_page()

            page.goto(url, wait_until='domcontentloaded', timeout=30000)

            # 等待页面内容加载
            try:
                page.wait_for_selector('table', timeout=15000)
            except:
                pass

            html_content = page.content()
            browser.close()

        print(f"页面加载完成，内容长度: {len(html_content)}")

        # 解析页面内容
        soup = BeautifulSoup(html_content, 'html.parser')

        # 查找表格中的版本使用率数据
        version_data = {}

        # 尝试从表格解析（页面为 3 列：系统版本 | 版本号(API) | 使用率）
        tables = soup.find_all('table')
        for table in tables:
            tbody = table.find('tbody')
            if tbody:
                rows = tbody.find_all('tr')
                for row in rows:
                    cells = [c.get_text(strip=True) for c in row.find_all('td')]
                    if len(cells) < 2:
                        continue
                    # 找 "API版本" 列：含 "(API)" 的单元格（位置不固定，稳健处理）
                    # 页面列结构：HarmonyOS版本 | API版本 | 设备量占比
                    api = None
                    version_idx = None
                    ver_name = None
                    for idx, c in enumerate(cells):
                        m = re.search(r'\((?:API\s*)?(\d+)\)', c, re.IGNORECASE)
                        if m:
                            api = m.group(1)
                            version_idx = idx
                            break
                    if api is None:
                        # 新版号方案：API版本列写作 "26.0.0"（主版本号即 API 号），无括号。
                        # 识别：匹配 N.N.N 且其后一格为使用率（含 %）的单元格
                        for idx, c in enumerate(cells):
                            if re.fullmatch(r'\d+\.\d+\.\d+', c) and idx + 1 < len(cells) and '%' in cells[idx + 1]:
                                api = c.split('.')[0]
                                version_idx = idx
                                break
                    if api is None:
                        continue  # 无法识别 API 号的行，跳过
                    # 版本名：取 "API版本" 列前一格的 "HarmonyOS版本" 列（如 7.0.0）；
                    # 取不到则用 API版本列本身去掉 (API nn) 后缀
                    if version_idx > 0 and cells[version_idx - 1]:
                        ver_name = cells[version_idx - 1]
                    else:
                        ver_name = re.sub(r'\s*\((?:API\s*)?\d+\)\s*$', '', cells[version_idx], flags=re.IGNORECASE).strip() or None
                    # 使用率：版本列之后第一个含 % 的单元格
                    for c in cells[version_idx + 1:]:
                        if '%' in c:
                            pm = re.match(r'(\d+(?:\.\d+)?)', c)
                            if pm:
                                version_data[api] = {'usage': pm.group(1), 'version': ver_name}
                            break

        if version_data:
            print(f"成功获取 {len(version_data)} 条在线数据")
            return version_data

        print("未能从页面提取数据，将使用本地数据")
        return None

    except Exception as e:
        print(f"网络请求错误: {e}")
        return None


def get_version_percentage():
    """获取版本使用率数据（优先在线，备用本地）。
    返回格式: {api号: {'usage': 使用率字符串, 'version': 版本名或 None}}"""
    online_data = fetch_version_percentage_online()

    if online_data:
        return online_data

    print("\n使用本地维护的版本使用率数据...")
    print("注意: 数据需要定期手动更新")
    print(f"当前数据日期: 请参考 https://developer.huawei.com/consumer/cn/doc/harmonyos-releases/sdk-version-percentage")

    return {api: {'usage': pct, 'version': None} for api, pct in MANUAL_VERSION_DATA.items()}


PLACEHOLDER = '待补充'


def parse_md_row(line):
    """拆分 MD 表格行为单元格列表（去掉首尾空管道）"""
    raw = line.split('|')
    if raw and raw[0].strip() == '':
        raw = raw[1:]
    if raw and raw[-1].strip() == '':
        raw = raw[:-1]
    return [c.strip() for c in raw]


def extract_api(cells):
    """从首列单元格提取 API 号（支持 [24](url) 与 24 两种写法），无则返回 None"""
    m = re.match(r'\[(\d+)\]', cells[0]) or re.match(r'^(\d+)$', cells[0])
    return m.group(1) if m else None


def build_new_version_row(api, info):
    """构造缺失版本的表格新行：已知信息自动填充，未知字段用占位符提示手动补充"""
    version = info.get('version') or PLACEHOLDER
    # 纯数字版本号（如 26.0.0）补 "HarmonyOS " 前缀，与表格风格一致
    if re.fullmatch(r'\d+(\.\d+)*', version):
        version = f'HarmonyOS {version}'
    usage = f"{info['usage']}%" if info.get('usage') else '-'
    return (f'| {api} | {version} | {PLACEHOLDER} | {usage} | '
            f'⚠️ {PLACEHOLDER}：新增版本行，请核对版本名并补充发布时间/链接/说明 |')


def find_insert_position(lines, api):
    """按 API 降序确定新行插入位置：首个 API 更小的数据行之前；无则插到最后一个数据行之后"""
    api_num = int(api)
    last_data_idx = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not (stripped.startswith('|') and '|-----' not in stripped):
            continue
        cells = parse_md_row(stripped)
        row_api = extract_api(cells)
        if not row_api:
            continue
        last_data_idx = idx
        if int(row_api) < api_num:
            return idx
    return (last_data_idx + 1) if last_data_idx is not None else len(lines)


def add_usage_column(table_lines, version_data):
    """给单框架表格插入使用率列（原 4 列 -> 5 列）"""
    new_lines = []
    for i, line in enumerate(table_lines):
        stripped = line.strip()
        if i == 0 and stripped.startswith('| API'):
            new_lines.append('| API | 对应系统版本 | 发布时间 | 使用率 | 备注 |')
        elif '|-----' in stripped:
            new_lines.append('|-----|-------------|---------|--------|------|')
        elif stripped.startswith('|'):
            cells = parse_md_row(stripped)
            if len(cells) >= 4:
                api = extract_api(cells)
                info = version_data.get(api) if api else None
                usage = f"{info['usage']}%" if info and info.get('usage') else '-'
                new_lines.append(f"| {cells[0]} | {cells[1]} | {cells[2]} | {usage} | {cells[3]} |")
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    return new_lines


def update_md_file(version_data, md_file='hoapi.md'):
    """更新MD文件中的使用率数据；若版本数据中存在表格里没有的 API 版本，
    自动在单框架表格中按 API 降序新增一行，未知字段以占位符提示用户手动补充"""
    try:
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 找到单框架部分
        single_section_pattern = r'(## 单框架\s*\n+)(.*?)(\n+## 双框架)'
        match = re.search(single_section_pattern, content, re.DOTALL)

        if not match:
            print("未找到单框架表格")
            return content

        single_header = match.group(1)
        table_lines = match.group(2).split('\n')
        separator = match.group(3)

        # 表头无使用率列时先补列（保证后续统一按 5 列处理）
        has_usage_col = any(
            l.strip().startswith('| API') and '使用率' in l for l in table_lines
        )
        if not has_usage_col:
            print("添加使用率列到单框架表格...")
            table_lines = add_usage_column(table_lines, version_data)
        else:
            print("单框架表格已包含使用率列，正在更新数据...")

        # 第一遍：更新已有行使用率，并记录表格中已有的 API
        new_lines = []
        seen_apis = set()
        for line in table_lines:
            stripped = line.strip()
            if not (stripped.startswith('|') and '|-----' not in stripped):
                new_lines.append(line)
                continue
            cells = parse_md_row(stripped)
            api = extract_api(cells)
            if api:
                seen_apis.add(api)
            info = version_data.get(api) if api else None
            if info and info.get('usage') and len(cells) >= 5:
                cells[3] = f"{info['usage']}%"
                new_lines.append('| ' + ' | '.join(cells) + ' |')
            else:
                new_lines.append(line)

        # 第二遍：爬取到但表格中不存在的版本 -> 自动新增行
        missing = {api: info for api, info in version_data.items() if api not in seen_apis}
        for api, info in sorted(missing.items(), key=lambda x: int(x[0]), reverse=True):
            row = build_new_version_row(api, info)
            new_lines.insert(find_insert_position(new_lines, api), row)
            ver_hint = f"（{info.get('version')}）" if info.get('version') else ''
            print(f"⚠️ 发现表格中不存在的版本 API {api}{ver_hint}，已自动新增一行，"
                  f"请手动补充发布时间/链接/备注（表格中以「{PLACEHOLDER}」标注）")

        new_table = '\n'.join(new_lines)
        content = single_header + new_table + separator + content[match.end():]

        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"已更新 {md_file}")
        return content

    except FileNotFoundError:
        print(f"文件 {md_file} 不存在")
        return None
    except Exception as e:
        print(f"更新文件错误: {e}")
        return None


def main():
    """主函数：获取数据并更新 MD 文件"""
    print("=" * 60)
    print("HarmonyOS API 版本使用率数据获取脚本")
    print("=" * 60)

    print("\n[步骤1] 获取HarmonyOS版本使用率数据...")
    version_data = get_version_percentage()

    if version_data:
        print(f"\n获取到的版本数据:")
        for api, info in sorted(version_data.items(), key=lambda x: int(x[0]), reverse=True):
            ver = f"（{info['version']}）" if info.get('version') else ''
            print(f"  API {api}: {info['usage']}%{ver}")
    else:
        print("\n警告: 未能获取版本使用率数据")
        version_data = {}

    print("\n[步骤2] 更新 hoapi.md 文件...")
    updated_content = update_md_file(version_data)

    if updated_content:
        print("\n✅ 完成!")
    else:
        print("\n❌ 更新失败")

    print("=" * 60)
    return version_data


if __name__ == '__main__':
    main()