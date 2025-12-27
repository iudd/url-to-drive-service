# 🚀 URL to Google Drive Saver (API Ready)

这个 Space 不仅可以通过网页界面使用，还可以作为 **API 微服务** 被其他 AI Agent 调用。

## ✨ 新功能

- **📁 用户名自动分类**: 支持按用户名自动创建专属文件夹
- **🏷️ 智能文件命名**: 支持使用 post_id 等元数据作为文件名
- **🔗 公开外链**: 返回 Google Drive 直接下载链接，可外链访问
- **📅 日期归档**: 自动按日期组织文件

## 🔐 配置

请确保在 **Settings** -> **Repository secrets** 中设置了以下变量：
- `ACCESS_PASSWORD`: 设置一个访问密码（API Key），防止他人滥用。
- `G_REFRESH_TOKEN`, `G_CLIENT_ID`, `G_CLIENT_SECRET`: OAuth 凭据。
- `GDRIVE_FOLDER_ID`: (可选) 根目录 ID。

## 📁 文件夹结构

### 有用户名时
```
指定文件夹/
└── xever121/                    # 用户文件夹
    └── 2025-12-27/              # 日期文件夹
        └── s_xxx.mp4
```

### 无用户名时
```
指定文件夹/
└── 2025-12-27/                  # 日期文件夹
    └── video_xxx.mp4
```

## 🤖 API 调用示例 (Python)

### 方式1：简单模式（兼容旧版）

```python
from gradio_client import Client

client = Client("iyougame/url2drive")
result = client.predict(
    "https://example.com/video.mp4",  # 文件 URL
    "your_password",                  # 访问密码
    api_name="/upload"
)
print(result)
```

### 方式2：完整模式（支持用户名和元数据）⭐ 推荐

```python
from gradio_client import Client

client = Client("iyougame/url2drive")

# 构造请求
request = {
    "url": "https://oscdn2.dyysy.com/MP4/s_xxx.mp4",
    "password": "your_password",
    "username": "xever121",           # 用户名（可选）
    "metadata": {                     # 元数据（可选）
        "post_id": "s_xxx",
        "user_id": "user-xxx"
    }
}

# 调用 API
result = client.predict(request, api_name="/upload_json")

# 获取下载链接
if result["status"] == "success":
    print(f"下载链接: {result['download_link']}")
    print(f"存储路径: {result['folder_path']}")
```

**返回数据示例**:
```json
{
  "status": "success",
  "filename": "s_xxx.mp4",
  "file_id": "1abcde...",
  "download_link": "https://drive.google.com/uc?id=...",
  "view_link": "https://drive.google.com/file/d/.../view",
  "folder": "2025-12-27",
  "username": "xever121",
  "folder_path": "xever121/2025-12-27"
}
```

## 📖 详细文档

查看 [API_REQUEST_TEMPLATE.md](./API_REQUEST_TEMPLATE.md) 获取完整的 API 使用文档。
