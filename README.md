---
title: URL to Drive Saver
emoji: ☁️
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 4.44.1
app_file: app.py
pinned: false
---

# 🚀 URL to Google Drive Saver (API Ready)

这个 Space 不仅可以通过网页界面使用，还可以作为 **API 微服务** 被其他 AI Agent 调用。

## 🔐 配置

请确保在 **Settings** -> **Repository secrets** 中设置了以下变量：
- `ACCESS_PASSWORD`: 设置一个访问密码（API Key），防止他人滥用。
- `G_REFRESH_TOKEN`, `G_CLIENT_ID`, `G_CLIENT_SECRET`: OAuth 凭据。
- `GDRIVE_FOLDER_ID`: (可选) 根目录 ID。

## 📅 功能特性

- **自动日期归档**: 文件会自动存入 `YYYY-MM-DD` 格式的文件夹中。
- **智能重命名**: 自动识别乱码 URL，防止文件名冲突。
- **公开直链**: 返回 `webContentLink`，供下游程序直接下载。

## 🤖 API 调用示例 (Python)

使用 `gradio_client` 库可以轻松调用此服务：

```python
from gradio_client import Client

# 初始化客户端
client = Client("iyougame/url2drive")

# 你的密码
API_PASSWORD = "你的密码"

# 调用上传
result = client.predict(
    "https://example.com/video.mp4", # 文件 URL
    API_PASSWORD,                    # 访问密码
    api_name="/upload"               # API 端点名
)

# 打印结果 (JSON 格式)
print(result)
```

**返回数据示例**:
```json
{
  "status": "success",
  "filename": "video_20231225.mp4",
  "file_id": "1abcde...",
  "download_link": "https://drive.google.com/uc?id=...",
  "view_link": "https://drive.google.com/file/d/.../view",
  "folder": "2023-12-25"
}
```
