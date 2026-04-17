#!/usr/bin/env python3
"""
HarmonyOS 支持设备型号清单爬取脚本
从华为开发者网站获取设备信息，生成 Markdown 文件
"""

import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from collections import defaultdict
from datetime import datetime


def fetch_device_data():
    """使用 Playwright 获取华为开发者网站的设备数据"""
    url = 'https://developer.huawei.com/consumer/cn/doc/harmonyos-releases/support-device'

    print("正在加载页面...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 使用 domcontentloaded 而不是 networkidle，更快加载
        page.goto(url, wait_until='domcontentloaded', timeout=30000)

        # 等待表格出现
        try:
            page.wait_for_selector('table', timeout=15000)
        except Exception as e:
            print(f"等待表格超时: {e}")
            # 尝试等待更长时间
            page.wait_for_selector('table', timeout=30000)

        # 获取页面 HTML
        html_content = page.content()
        browser.close()

    print(f"页面加载完成，内容长度: {len(html_content)}")
    return html_content


def parse_text_devices(heading):
    """解析文字形式的设备列表（如 Wearable）"""
    devices = []

    # 设备型号关键词
    device_keywords = ['WATCH', 'GT', 'FIT', 'Band', '手环', '手表']

    # 无关关键词（过滤掉网页其他内容）
    exclude_keywords = ['你问我答', '咨询', '专家', '服务', '解决方案', '客服', '合作', '开发者']

    # 获取标题后面的内容，直到下一个标题
    next_h = heading.find_next(['h2', 'h3', 'h4'])

    current = heading.find_next()
    current_series = None
    max_iterations = 100  # 安全限制
    iterations = 0

    while current and current != next_h and iterations < max_iterations:
        iterations += 1
        if current.name == 'p':
            text = current.get_text(strip=True)
            if text and len(text) < 60:
                # 过滤无关内容
                if any(kw in text for kw in exclude_keywords):
                    current = current.find_next()
                    continue

                # 判断是否是设备系列（包含"系列"）
                if '系列' in text:
                    current_series = text
                elif current_series:
                    # 设备型号
                    devices.append({
                        'series': current_series,
                        'model': text,
                        'code': '-'
                    })
                elif any(kw in text for kw in device_keywords):
                    # 包含设备关键词的单独型号
                    devices.append({
                        'series': '其他',
                        'model': text,
                        'code': '-'
                    })

        current = current.find_next()

    return devices


def parse_tables(html_content):
    """解析 HTML 内容，提取表格数据"""
    soup = BeautifulSoup(html_content, 'html.parser')

    # 设备类型映射（英文 -> 中文）
    device_type_map = {
        'Phone': '手机',
        'Tablet': '平板',
        'PC/2in1': 'PC',
        'PC': 'PC',
        'Wearable': '穿戴',
        'Lite Wearable': '穿戴',
        'TV': 'IoT',
        'IoT': 'IoT',
        '智能音箱': 'IoT',
    }

    # 版本格式匹配
    version_pattern = re.compile(r'^(\d+\.\d+\.\d+|\d+\.\d+)(\(\d+\))?')

    data = defaultdict(lambda: defaultdict(list))

    # 获取所有表格
    tables = soup.find_all('table')

    for table in tables:
        # 查找表格前面的设备类型标题
        device_heading = table.find_previous(['h3', 'h4'])
        if not device_heading:
            continue

        device_type_text = device_heading.get_text(strip=True)
        if device_type_text not in device_type_map:
            continue

        device_type = device_type_map[device_type_text]

        # 查找表格前面的版本号标题（在设备类型标题之前）
        version_heading = device_heading.find_previous(['h2'])
        if not version_heading:
            continue

        version_text = version_heading.get_text(strip=True)
        version_match = version_pattern.match(version_text)
        if not version_match:
            continue

        current_version = version_match.group(1)

        # 解析表格
        devices = parse_table(table)
        if devices:
            data[device_type][current_version].extend(devices)
            print(f"  {current_version} -> {device_type}: {len(devices)} 条")

    # 处理文字形式的设备列表（Wearable, Lite Wearable）
    text_device_types = ['Wearable', 'Lite Wearable']
    headings = soup.find_all(['h3', 'h4'])

    for heading in headings:
        heading_text = heading.get_text(strip=True)
        if heading_text in text_device_types:
            device_type = '穿戴'

            # 查找版本号
            version_heading = heading.find_previous(['h2'])
            if version_heading:
                version_text = version_heading.get_text(strip=True)
                version_match = version_pattern.match(version_text)
                if version_match:
                    current_version = version_match.group(1)

                    # 解析文字设备列表
                    devices = parse_text_devices(heading)
                    if devices:
                        data[device_type][current_version].extend(devices)
                        print(f"  {current_version} -> {device_type}(文字): {len(devices)} 条")

    return data


def parse_table(table):
    """解析单个表格，提取设备信息"""
    devices = []

    tbody = table.find('tbody')
    if not tbody:
        return devices

    rows = tbody.find_all('tr')
    current_series = None

    for row in rows:
        cells = row.find_all('td')

        if len(cells) == 3:
            series_text = cells[0].get_text(strip=True)
            # 过滤"说明"后面的内容
            if '说明' in series_text:
                series_text = series_text.split('说明')[0].strip()
            current_series = series_text

            model = cells[1].get_text(strip=True)
            # 处理型号代码：提取每个 p 标签的内容，用逗号分隔
            code_cell = cells[2]
            p_tags = code_cell.find_all('p')
            if p_tags:
                codes = ', '.join([p.get_text(strip=True) for p in p_tags if p.get_text(strip=True)])
            else:
                codes = code_cell.get_text(strip=True)
                codes = re.sub(r'\s+', ', ', codes.strip())
        elif len(cells) == 2:
            if current_series is None:
                current_series = '其他'

            model = cells[0].get_text(strip=True)
            # 处理型号代码
            code_cell = cells[1]
            p_tags = code_cell.find_all('p')
            if p_tags:
                codes = ', '.join([p.get_text(strip=True) for p in p_tags if p.get_text(strip=True)])
            else:
                codes = code_cell.get_text(strip=True)
                codes = re.sub(r'\s+', ', ', codes.strip())
        else:
            continue

        if current_series and model:
            devices.append({
                'series': current_series,
                'model': model,
                'code': codes
            })

    return devices


def generate_markdown(data, output_file='hodevice.md'):
    """生成 Markdown 文件"""
    lines = []

    # 文件标题
    lines.append('# HarmonyOS 支持设备型号清单')
    lines.append('')
    lines.append(f'> 数据来源: https://developer.huawei.com/consumer/cn/doc/harmonyos-releases/support-device')
    lines.append(f'> 更新时间: {datetime.now().strftime("%Y-%m-%d")}')
    lines.append('')

    # 设备类型顺序
    type_order = ['手机', '平板', 'PC', '穿戴', 'IoT']

    for device_type in type_order:
        if device_type not in data:
            continue

        lines.append(f'## {device_type}')
        lines.append('')

        # 表头
        lines.append('| 设备系列 | 设备型号 | 型号代码 | 支持版本 |')
        lines.append('|---------|---------|---------|---------|')

        # 按版本排序（从高到低）
        versions = sorted(data[device_type].keys(), key=lambda v: [int(x) for x in v.split('.')], reverse=True)

        # 收集所有设备，按系列分组
        all_devices = []
        for version in versions:
            for device in data[device_type][version]:
                device['version'] = version
                all_devices.append(device)

        # 按系列和版本排序
        # 同一设备系列，只保留最新版本
        series_version_map = defaultdict(dict)
        for device in all_devices:
            series = device['series']
            model = device['model']
            version = device['version']

            # 如果同一型号出现在多个版本中，只保留最高版本
            if model not in series_version_map[series] or \
               [int(x) for x in version.split('.')] > [int(x) for x in series_version_map[series][model]['version'].split('.')]:
                series_version_map[series][model] = device

        # 输出表格
        for series in sorted(series_version_map.keys()):
            models = series_version_map[series]
            first_model = True

            for model_name in sorted(models.keys()):
                device = models[model_name]

                if first_model:
                    # 第一行显示设备系列
                    lines.append(f'| {series} | {device["model"]} | {device["code"]} | {device["version"]} |')
                    first_model = False
                else:
                    # 后续行不重复设备系列
                    lines.append(f'| | {device["model"]} | {device["code"]} | {device["version"]} |')

        lines.append('')

    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"已生成文件: {output_file}")
    return output_file


def main():
    print("=" * 60)
    print("HarmonyOS 支持设备型号清单爬取脚本")
    print("=" * 60)

    # 获取数据
    html_content = fetch_device_data()

    # 解析数据
    print("\n解析表格数据...")
    data = parse_tables(html_content)

    # 统计
    print("\n数据统计:")
    for device_type in data:
        total = sum(len(devices) for devices in data[device_type].values())
        print(f"  {device_type}: {total} 条")

    # 生成 Markdown
    print("\n生成 Markdown 文件...")
    generate_markdown(data)

    print("\n✅ 完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()