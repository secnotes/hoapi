# HarmonyOS API Levels

鸿蒙系统 API 和系统版本映射关系参考表。

## 文件说明

| 文件 | 说明 |
|------|------|
| `hoapi.md` | Markdown 数据源文件 |
| `index.html` | HTML 页面，可直接在浏览器中打开 |
| `ho_tools.py` | Python 工具脚本，用于更新数据和生成 HTML |

## 功能特点

- 单框架与双框架版本分类展示
- SDK 版本使用率可视化（进度条）
- 深色/浅色主题切换
- 中英文语言切换
- 响应式设计，适配移动端

## 使用方法

直接在浏览器中打开 `index.html` 即可查看。

如需更新数据：

```bash
python3 ho_tools.py
```

脚本会自动：
1. 尝试从华为开发者网站获取最新使用率数据
2. 更新 `hoapi.md` 文件
3. 重新生成 `index.html`

## 数据来源

- [Wikipedia: HarmonyOS version history](https://en.wikipedia.org/wiki/HarmonyOS_version_history)
- [华为开发者文档：SDK 版本使用率](https://developer.huawei.com/consumer/cn/doc/harmonyos-releases/sdk-version-percentage)

## License

MIT