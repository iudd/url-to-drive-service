---
title: URL to Drive Saver
emoji: 🚀
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 4.44.1
app_file: app.py
pinned: false
---

# 🚀 URL to Google Drive Saver (API Edition)

这是一个部署在 Hugging Face Space 上的全栈应用，用于将网络上的文件（视频、图片等）自动转存到您的 Google Drive。

## ✨ 核心特性

- **日期归档**: 自动按日期 (`2024-01-01`) 创建子文件夹，整理文件。
- **智能命名**: 自动解析文件名，如果 URL 是乱码或 raw，则使用时间戳命名。
- **API 支持**: 提供受密码保护的 API 接口，可被其他 AI Agent 调用。
- **OAuth 2.0**: 使用个人账号鉴权，无 Service Account 限制。

---

## 🔐 环境变量配置

请在 Space 的 **Settings** -> **Repository secrets** 中设置：

| Secret Name | 说明 | 示例 |
| :--- | :--- | :--- |
| `G_CLIENT_ID` | OAuth Client ID | `xxx.apps.googleusercontent.com` |
| `G_CLIENT_SECRET` | OAuth Client Secret | `GOCSPX-xxxx...` |
| `G_REFRESH_TOKEN` | 您的刷新令牌 | `1//04Pq...` |
| `ACCESS_PASSWORD` | **(新)** API 访问密码 | `sk-mysecret123` |
| `GDRIVE_FOLDER_ID` | (可选) 根目录 ID | `1AbCdEf...` |

---

## 🤖 API 调用指南

您可以在任何 Python 程序中调用此服务：

```python
from gradio_client import Client

# 1. 初始化客户端
client = Client("https://iyougame-url2drive.hf.space")

# 2. 调用上传接口
result = client.predict(
    "https://example.com/video.mp4",  # file_url
    "sk-mysecret123",                 # password
    api_name="/upload"
)

# 3. 获取结果
print(result)
# 返回示例:
# {
#   "status": "success",
#   "filename": "video.mp4",
#   "download_link": "https://drive.google.com/uc?id=...",
#   "view_link": "https://drive.google.com/file/d/.../view"
# }
```

---

## 🛠️ 故障排除

- **401 Unauthorized**: 检查 `ACCESS_PASSWORD` 是否匹配。
- **0KB 文件**: 检查源链接是否有效，通常是因为源服务器拒绝了请求。
