# HarmonyOS API Levels

鸿蒙系统 API 和系统版本映射关系参考表，同时提供设备支持清单。

## 文件说明

| 文件 | 说明 |
|------|------|
| `hoapi.md` | API 版本数据 Markdown 源文件 |
| `hodevice.md` | 设备支持清单 Markdown 源文件 |
| `index.html` | HTML 页面，可直接在浏览器中打开 |
| `main.py` | 主脚本，整合数据获取和 HTML 生成 |
| `ho_crawler.py` | API 版本使用率数据爬取脚本 |
| `device_crawler.py` | 设备支持清单爬取脚本 |
| `ho_html_gen.py` | HTML 生成脚本 |

## 功能特点

- 单框架与双框架版本分类展示
- SDK 版本使用率可视化（进度条）
- HarmonyOS 设备支持清单（手机、平板、PC、穿戴、IoT）
- 目录导航（TOC）
- 深色/浅色主题切换
- 中英文语言切换
- 移动端响应式设计

## 使用方法

直接在浏览器中打开 `index.html` 即可查看。

如需更新数据：

```bash
python3 main.py
```

脚本会自动：
1. 从华为开发者网站获取最新 API 版本使用率数据
2. 更新 `hoapi.md` 文件
3. 获取设备支持清单数据
4. 更新 `hodevice.md` 文件
5. 重新生成 `index.html`

也可以单独运行各模块：

```bash
# 仅更新 API 版本使用率
python3 ho_crawler.py

# 仅更新设备支持清单
python3 device_crawler.py

# 仅生成 HTML
python3 ho_html_gen.py
```

## 数据来源

- [Wikipedia: HarmonyOS version history](https://en.wikipedia.org/wiki/HarmonyOS_version_history)
- [华为开发者文档：SDK 版本使用率](https://developer.huawei.com/consumer/cn/doc/harmonyos-releases/sdk-version-percentage)
- [华为开发者文档：支持设备型号清单](https://developer.huawei.com/consumer/cn/doc/harmonyos-releases/support-device)

## License

MIT