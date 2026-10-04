**SeqSketch 1.0.2 — 2026-10-04**

本版本只解决一个交付一致性问题:GitHub Actions 打包的软件界面控件样式与本地打包不一致。

原因是没有钉住 PyQt6 的版本。`requirements.txt` 原来只声明 `PyQt6>=6.0.0`,CI 在 2026-10-02 构建 v1.0.1 时解析到最新的 PyQt6 6.11(Qt 6.11.2),而本地开发环境是 6.10.0(Qt 6.10.0)。Qt 6.11 改变了 windows11 样式(`qmodernwindowsstyle`)中 QSpinBox 上下箭头、QComboBox 下拉箭头和 QTabBar 关闭按钮的画法,而 `styles.qss` 没有接管这些子控件,于是 CI 产物在同样的 Windows 11 机器上呈现出明显不同的控件外观(实心大箭头、无底色关闭按钮)。

修复与发布约定:

- `requirements.txt` 钉住 `PyQt6==6.10.0` 与 `PyQt6-Qt6==6.10.0`(后者必须显式钉住,因为 PyQt6 对它的约束只是 `>=6.10.0`,干净环境会连带装到 6.10.x 最新补丁版)。三条 CI 构建腿(Windows、macOS arm64、macOS Intel)共用这份文件,Mac 产物同步受益。
- 今后升级 PyQt6 属于需要评审界面的变更:预期控件细节会随 Qt 原生样式演进,升级钉住版本前应重新过一遍界面。

验证:干净 Python 3.13 环境解析结果为 `PyQt6-6.10.0 PyQt6-Qt6-6.10.0`,与本地 venv 及既有 `dist/SeqSketch` 中的 `Qt6Core.dll`(6.10.0)逐位一致;全量测试 561 项通过。

1.0.1 的修复内容与交付验证见[发布说明](release-notes-1.0.1.md)与[验证记录](release-validation-1.0.1.md)。
