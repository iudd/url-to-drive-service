---
title: URL to Google Drive Service
emoji: 🚀
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: "4.0.0"
app_file: app.py
pinned: false
---

# URL to Google Drive Service

一个将任意 URL 的文件直接转存到 Google Drive 的在线服务。

## 🌟 功能特点

- ✅ 支持任何可通过 HTTP/HTTPS 访问的文件
- ✅ 流式下载和上传，避免内存溢出
- ✅ 自动设置文件为公开可读
- ✅ 简洁美观的 Web 界面
- ✅ 密码保护，防止滥用
- ✅ 完整的错误处理机制

## 📋 项目架构

- **Backend**: 基于 Gradio SDK 运行在 Hugging Face Spaces
- **Frontend**: 静态 HTML 页面，通过 JavaScript 调用后端 API
- **Storage**: Google Drive (使用 Service Account)

## 🚀 快速开始

### 1. 访问在线服务

直接访问部署好的前端界面：[URL to Google Drive](https://your-frontend-url.com)

### 2. 使用方法

1. 在文件 URL 框中输入要转存的文件链接
2. 输入正确的访问密码
3. 点击"开始转存"按钮
4. 等待处理完成，获取 Google Drive 下载链接

## 🔧 部署指南

### 自动部署（推荐）

1. **Fork 此仓库** 到您的 GitHub 账户
2. **启用 GitHub Actions**（在仓库设置中）
3. **配置 Secrets**：
   - `HF_TOKEN`: 您的 Hugging Face API Token
4. **推送代码** 或 **手动触发 Actions**
5. 系统会自动在 Hugging Face Spaces 创建应用

### 手动部署

#### 步骤 1: 准备 Google Cloud

1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建新项目或选择现有项目
3. 启用 Google Drive API
4. 创建服务账号并下载 JSON 密钥

#### 步骤 2: 创建 Hugging Face Space

1. 访问 [Hugging Face Spaces](https://huggingface.co/spaces)
2. 点击 "Create new Space"
3. 配置：
   - **Name**: `url2drive`
   - **SDK**: `Gradio`
   - **Hardware**: `CPU basic` (免费)

#### 步骤 3: 配置环境变量

在 Space Settings > Secrets 中添加：

```
GDRIVE_CREDENTIALS: [完整的 JSON 密钥内容]
GDRIVE_FOLDER_ID: [Google Drive 文件夹 ID]
SECRET_CODE: [访问密码]
```

#### 步骤 4: 上传代码

上传以下文件到 Space：
- `app.py`
- `requirements.txt`

### 前端部署

将 `index.html` 文件部署到任何静态托管服务：
- GitHub Pages
- Netlify
- Vercel
- 直接浏览器打开

## 🔧 环境变量说明

| 变量名 | 必需 | 说明 |
|--------|------|------|
| `GDRIVE_CREDENTIALS` | 是 | Google Service Account JSON 密钥 |
| `GDRIVE_FOLDER_ID` | 否 | 目标文件夹 ID（可选） |
| `SECRET_CODE` | 否 | 访问密码（默认为 'default_secret'） |

### 获取 GDRIVE_CREDENTIALS

1. 在 Google Cloud Console 创建服务账号
2. 生成 JSON 密钥文件
3. 复制整个 JSON 内容（包括大括号）

### 获取 GDRIVE_FOLDER_ID

1. 在 Google Drive 中打开目标文件夹
2. URL 中的 `folders/FOLDER_ID` 部分即为 ID

## 📖 使用示例

### 支持的文件类型
- 📄 文档: PDF, DOCX, XLSX, PPTX
- 🖼️ 图片: JPG, PNG, GIF, SVG
- 🎥 视频: MP4, AVI, MKV, MOV
- 📦 压缩包: ZIP, RAR, 7Z
- 💾 其他: 任何可下载的文件

### 示例 URL
```
https://example.com/file.pdf
https://github.com/user/repo/releases/download/v1.0/file.zip
https://cdn.example.com/image.jpg
```

## ⚠️ 注意事项

- 文件大小受 Hugging Face Spaces 免费版限制（约 16GB）
- 下载速度取决于源服务器
- 上传速度受 Google Drive API 限制
- 请妥善保管访问密码

## 🛠️ 本地开发

```bash
# 克隆项目
git clone https://github.com/iudd/url-to-drive-service.git
cd url-to-drive-service

# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export GDRIVE_CREDENTIALS='{"type":"service_account",...}'
export GDRIVE_FOLDER_ID='your_folder_id'
export SECRET_CODE='your_password'

# 运行应用
python app.py
```

访问 `http://localhost:7860` 测试应用。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 🔗 相关链接

- [Hugging Face Spaces 文档](https://huggingface.co/docs/hub/spaces)
- [Gradio 文档](https://gradio.app/docs/)
- [Google Drive API 文档](https://developers.google.com/drive/api/v3/about-sdk)

---

**⭐ 如果这个项目对你有帮助，请给个 Star！**