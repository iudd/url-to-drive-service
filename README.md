---
title: URL to Drive Saver
emoji: 🚀
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 4.19.2
app_file: app.py
pinned: false
---

# ☁️ URL to Drive Saver (OAuth 2.0 版)

这是一个全栈解决方案，用于将任意 URL 的文件（视频、压缩包等）通过 Hugging Face Space 中转，**流式**上传到您的个人 Google Drive。

## ✨ 特性

- **OAuth 2.0 鉴权**: 彻底解决 Service Account 存储配额为 0 的问题，直接使用您的个人 Google Drive 空间（15GB+）。
- **内存优化**: 使用流式传输 (Streaming Upload)，支持转存数 GB 的大文件，不会爆掉 Hugging Face 的内存。
- **前后端分离**: 提供独立的 `index.html`，可部署在任何地方。

---

## 🚀 部署与配置指南

### 第一步：获取 Google OAuth 凭据 (Refresh Token)

**注意**：由于 Hugging Face 服务器在海外，如果您本地网络无法连接 Google，建议使用云端方式（如 Colab）或在 VPS 上获取 Token。

1. **创建凭据**:
   - 访问 [Google Cloud Console](https://console.cloud.google.com/)。
   - 创建 **OAuth 客户端 ID** -> 应用类型选择 **桌面应用 (Desktop App)**。
   - 获取 `Client ID` 和 `Client Secret`。

2. **获取 Refresh Token**:
   - 运行项目中的 `get_token.py` 脚本（需在本地或 Colab 运行，不要在 Space 运行）。
   - 按提示输入 ID 和 Secret，完成登录授权，获取 `Refresh Token`。

### 第二步：配置 Hugging Face Space

1. 点击 Space 页面顶部的 **Settings** 选项卡。
2. 找到 **Variables and secrets** -> 点击 **New secret**。
3. 添加以下三个环境变量：
   - `G_CLIENT_ID`: (您的 Client ID)
   - `G_CLIENT_SECRET`: (您的 Client Secret)
   - `G_REFRESH_TOKEN`: (脚本获取的 Refresh Token)
   - `GDRIVE_FOLDER_ID`: (可选，指定上传的文件夹 ID)

### 第三步：使用

配置完成后，Space 会自动重启。等待状态变为 **Running**：

1. 打开项目中的 `index.html` 文件。
2. 修改代码中的 `HF_SPACE_ID` 为您的 Space ID (例如 `iyougame/url2drive`)。
3. 用浏览器打开 `index.html`，输入文件 URL 即可开始转存。

---

## ⚠️ 常见问题

- **Redirect URI mismatch**: 请确保在 Google Cloud Console 创建凭据时选的是**桌面应用**，不要选 Web 应用。
- **Token 过期**: 请在 OAuth 同意屏幕中将应用发布为**生产环境 (Production)**，否则 Token 只有 7 天有效期。
