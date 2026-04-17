#!/usr/bin/env python3
"""
HarmonyOS API Level 文档处理主脚本
整合爬虫和 HTML 生成功能
"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ho_crawler import get_version_percentage, update_md_file
from device_crawler import fetch_device_data, parse_tables, generate_markdown
from ho_html_gen import generate_html


def main():
    """主函数：获取数据、更新 MD、生成 HTML"""
    print("=" * 60)
    print("HarmonyOS API Level 文档处理脚本")
    print("=" * 60)

    # 步骤1: 获取版本使用率数据并更新 hoapi.md
    print("\n[步骤1] 获取HarmonyOS版本使用率数据...")
    version_data = get_version_percentage()

    if version_data:
        print(f"\n获取到的版本数据:")
        for api, pct in sorted(version_data.items(), key=lambda x: int(x[0]), reverse=True):
            print(f"  API {api}: {pct}%")

    print("\n[步骤2] 更新 hoapi.md 文件...")
    update_md_file(version_data)

    # 步骤2: 获取设备数据并更新 hodevice.md
    print("\n[步骤3] 获取设备支持清单数据...")
    try:
        html_content = fetch_device_data()
        print("\n解析表格数据...")
        device_data = parse_tables(html_content)

        print("\n数据统计:")
        for device_type in device_data:
            total = sum(len(devices) for devices in device_data[device_type].values())
            print(f"  {device_type}: {total} 条")

        print("\n更新 hodevice.md 文件...")
        generate_markdown(device_data)
    except Exception as e:
        print(f"获取设备数据失败: {e}")
        print("将使用现有的 hodevice.md 文件")

    # 步骤3: 生成 HTML
    print("\n[步骤4] 生成 HTML...")
    generate_html()

    print("\n✅ 完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()