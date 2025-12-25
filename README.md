---
title: URL to Drive Saver
emoji: ☁️
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 4.19.2
app_file: app.py
pinned: false
---

# 🚀 URL to Google Drive Saver (OAuth 2.0 Streaming Edition)

这是一个部署在 Hugging Face Space 上的全栈应用，用于将网络上的文件（视频、压缩包等）**流式传输**直接保存到您的 Google Drive 个人版。

## ✨ 核心特性

- **OAuth 2.0 鉴权**: 使用您自己的 Google 账号，**彻底解决** Service Account 存储配额为 0 的问题。
- **流式传输 (Streaming)**: 采用 `requests(stream=True)` 和 `MediaIoBaseUpload`，支持转存超大文件，不占用服务器内存。
- **隐私安全**: 您的 Refresh Token 存储在 Secrets 中，文件直接存入您的网盘，不经过第三方存储。

---

## ⚙️ 部署配置指南 (必读)

要让此应用正常工作，您必须配置以下 **Repository Secrets**：

### 1. 准备 OAuth 凭据
请参考项目中的 `get_token.py` 脚本或使用 Google OAuth Playground 获取以下三个值：
1. **Client ID** (桌面应用类型)
2. **Client Secret**
3. **Refresh Token** (用于获取访问令牌)

### 2. 添加 Secrets
进入 Space 的 **Settings** -> **Repository secrets**，添加以下变量：

| Secret Name | 说明 | 示例值 |
| :--- | :--- | :--- |
| `G_CLIENT_ID` | 您的 OAuth 客户端 ID | `xxx.apps.googleusercontent.com` |
| `G_CLIENT_SECRET` | 您的 OAuth 客户端密钥 | `GOCSPX-xxxx...` |
| `G_REFRESH_TOKEN` | 您的刷新令牌 | `1//04Pq...` |
| `GDRIVE_FOLDER_ID` | (可选) 目标文件夹 ID | `1AbCdEf...` (留空则存入根目录) |

---

## 🖥️ 如何使用

### 方式 A: 使用 Space 自带界面
直接在当前 Space 页面输入文件 URL 和（可选的）访问密码（如果在代码中设置了的话），点击提交。

### 方式 B: 使用独立前端 (推荐)
本项目包含一个 `index.html` 文件，您可以将其部署到 GitHub Pages 或本地运行。
1. 打开 `index.html`。
2. 修改 `const HF_SPACE_ID = "您的用户名/Space名称";`。
3. 打开页面即可使用，界面更现代，体验更好。

---

## 🛠️ 故障排除

- **Error: redirect_uri_mismatch**: 您的 Client ID 类型选错了（选了 Web 而不是 Desktop），或者未配置 Playground 回调地址。请重建“桌面应用”类型的 ID。
- **Error: invalid_grant**: Refresh Token 已过期（测试版 7 天过期）。请在 Google Cloud Console 将应用发布为“生产环境”。
- **Runtime Error**: 请检查 Logs，通常是环境变量未正确设置。

---

此项目旨在解决 Hugging Face 临时空间无法持久化存储大文件的问题。如有问题，请查看 Logs。
