---
title: URL to Drive Saver
emoji: ☁️
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 4.0.0
app_file: app.py
pinned: false
---

# ☁️ URL to Drive Saver

这是一个全栈解决方案，用于将任意 URL 的文件（视频、压缩包等）通过 Hugging Face Space 中转，**流式**上传到您的个人 Google Drive。

## ✨ 特性

- **OAuth 2.0 鉴权**: 彻底解决 Service Account 存储配额为 0 的问题。
- **内存优化**: 使用 Python Generator 和 Streaming Upload，支持转存数 GB 的大文件，不会爆掉 Hugging Face 的内存。
- **前后端分离**: 提供独立的 `index.html`，可部署在任何地方（GitHub Pages, Vercel 等）。

---

## 🚀 部署步骤

### 第一步：获取 Google OAuth 凭据 (Refresh Token)

由于我们不能使用 Service Account，您需要创建一个 OAuth 应用来授权访问您的个人 Drive。

1. 去 [Google Cloud Console](https://console.cloud.google.com/).
2. 创建一个新项目，启用 **Google Drive API**。
3. 进入 **OAuth 同意屏幕**，User Type 选择 **External** (外部)，并添加您的测试邮箱。
4. 进入 **凭据** -> **创建凭据** -> **OAuth 客户端 ID** (类型选 Desktop App)。
5. 获取 `Client ID` 和 `Client Secret`。
6. **获取 Refresh Token**:
   - 在本地运行一个 Python 脚本来完成一次授权流程（Google 官方库的 `flow.run_local_server()`）。
   - 或者使用提供的 `get_token.py` 脚本生成。

### 第二步：部署后端 (Hugging Face Space)

1. 创建一个新的 Hugging Face Space (SDK 选择 **Gradio**)。
2. 将 `app.py`, `requirements.txt`, `get_token.py` 上传到 Space。
3. 进入 **Settings** -> **Repository Secrets**，添加以下环境变量：
   - `G_CLIENT_ID`: 您的 Client ID
   - `G_CLIENT_SECRET`: 您的 Client Secret
   - `G_REFRESH_TOKEN`: 您的 Refresh Token
   - `GDRIVE_FOLDER_ID`: (可选) 目标文件夹 ID，不填则存根目录。

### 第三步：部署前端

1. 打开 `index.html`。
2. 修改第 52 行：`const HF_SPACE_ID = "YourUsername/YourSpaceName";` 为您的 Space ID。
3. 将 HTML 文件部署到 GitHub Pages，或者直接在浏览器打开使用。

---

## ⚠️ 注意事项

- **流量**: 文件流经 Hugging Face 服务器，速度取决于 HF 的网络状况。
- **超时**: 极大的文件可能会触达 Gradio 或 HF 的超时限制（通常 1 小时左右）。
