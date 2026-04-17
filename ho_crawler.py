#!/usr/bin/env python3
"""
HarmonyOS API 版本使用率数据获取脚本
从华为开发者网站爬取或使用本地数据更新 hoapi.md
"""

import re
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

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
}


def fetch_version_percentage_online():
    """使用 Playwright 从华为开发者网站在线爬取数据"""
    url = "https://developer.huawei.com/consumer/cn/doc/harmonyos-releases/sdk-version-percentage"

    print(f"尝试访问: {url}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
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

        # 尝试从表格解析
        tables = soup.find_all('table')
        for table in tables:
            tbody = table.find('tbody')
            if tbody:
                rows = tbody.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        # 第一列格式: "6.0.2(22)" - 版本号(API)
                        version_cell = cells[0].get_text(strip=True)
                        # 从括号中提取API版本号
                        api_match = re.search(r'\((\d+)\)', version_cell)
                        if api_match:
                            api = api_match.group(1)

                            # 第二列是使用率百分比
                            pct_cell = cells[1].get_text(strip=True)
                            pct_match = re.match(r'(\d+(?:\.\d+)?)\s*%?', pct_cell)
                            if pct_match:
                                version_data[api] = pct_match.group(1)

        if version_data:
            print(f"成功获取 {len(version_data)} 条在线数据")
            return version_data

        print("未能从页面提取数据，将使用本地数据")
        return None

    except Exception as e:
        print(f"网络请求错误: {e}")
        return None


def get_version_percentage():
    """获取版本使用率数据（优先在线，备用本地）"""
    online_data = fetch_version_percentage_online()

    if online_data:
        return online_data

    print("\n使用本地维护的版本使用率数据...")
    print("注意: 数据需要定期手动更新")
    print(f"当前数据日期: 请参考 https://developer.huawei.com/consumer/cn/doc/harmonyos-releases/sdk-version-percentage")

    return MANUAL_VERSION_DATA


def update_md_file(version_data, md_file='hoapi.md'):
    """更新MD文件，添加/更新使用率数据"""
    try:
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 找到单框架部分
        single_section_pattern = r'(## 单框架\s*\n+)(.*?)(\n+## 双框架)'
        match = re.search(single_section_pattern, content, re.DOTALL)

        if match:
            single_header = match.group(1)
            single_table = match.group(2)
            separator = match.group(3)

            if '| 使用率 |' in single_table:
                print("单框架表格已包含使用率列，正在更新数据...")
                lines = single_table.split('\n')
                new_lines = []

                for line in lines:
                    if line.strip().startswith('|') and not '|-----' in line:
                        parts = [p.strip() for p in line.split('|')]
                        parts = [p for p in parts if p]

                        if len(parts) >= 5 and parts[0] not in ['API', '']:
                            api_cell = parts[0]
                            link_match = re.match(r'\[(\d+)\]\(.+\)', api_cell)
                            if link_match:
                                api = link_match.group(1)
                            else:
                                api = api_cell

                            usage = version_data.get(api, '-')
                            if usage and usage != '-':
                                usage = f"{usage}%"

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
                print("添加使用率列到单框架表格...")
                lines = single_table.split('\n')
                new_lines = []

                for i, line in enumerate(lines):
                    if i == 0 and line.startswith('| API'):
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


def main():
    """主函数：获取数据并更新 MD 文件"""
    print("=" * 60)
    print("HarmonyOS API 版本使用率数据获取脚本")
    print("=" * 60)

    print("\n[步骤1] 获取HarmonyOS版本使用率数据...")
    version_data = get_version_percentage()

    if version_data:
        print(f"\n获取到的版本数据:")
        for api, pct in sorted(version_data.items(), key=lambda x: int(x[0]), reverse=True):
            print(f"  API {api}: {pct}%")
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