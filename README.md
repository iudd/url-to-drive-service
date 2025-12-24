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

## 🚀 部署步骤

### 1. 准备 Google Cloud 服务账号

1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建新项目或选择现有项目
3. 启用 Google Drive API
4. 创建服务账号（Service Account）
5. 为服务账号创建 JSON 密钥
6. 下载 JSON 密钥文件（稍后需要用到）

### 2. 准备 Google Drive 文件夹

1. 在 Google Drive 中创建一个文件夹用于存储上传的文件
2. 记录文件夹的 ID（在 URL 中可以找到）
3. 将文件夹共享给服务账号的邮箱地址（格式：`xxx@xxx.iam.gserviceaccount.com`）

### 3. 部署到 Hugging Face Spaces

#### 方式一：通过 Web 界面部署

1. 访问 [Hugging Face Spaces](https://huggingface.co/spaces)
2. 点击 "Create new Space"
3. 填写 Space 信息：
   - **Name**: `url-to-drive-service`
   - **SDK**: 选择 `Gradio`
   - **Hardware**: 选择 `CPU basic`（免费）
4. 创建 Space 后，上传以下文件：
   - `app.py`
   - `requirements.txt`
5. 在 Space Settings 中设置 Secrets（环境变量）：
   - `GDRIVE_CREDENTIALS`: 将 JSON 密钥文件的全部内容复制粘贴（单行，不要换行）
   - `GDRIVE_FOLDER_ID`: Google Drive 文件夹 ID
   - `SECRET_CODE`: 设置访问密码（用于前端验证）

#### 方式二：通过 Git 部署

```bash
# 克隆项目
git clone https://github.com/YOUR_USERNAME/url-to-drive-service.git
cd url-to-drive-service

# 添加 Hugging Face Space 作为远程仓库
git remote add space https://huggingface.co/spaces/YOUR_USERNAME/url-to-drive-service
git push --force space main
```

然后在 Space Settings 中设置环境变量（同上）。

### 4. 配置前端页面

1. 打开 `index.html` 文件
2. 找到以下代码行：
   ```javascript
   const SPACE_ID = "YOUR_USERNAME/url-to-drive-service";
   ```
3. 将 `YOUR_USERNAME` 替换为您的 Hugging Face 用户名
4. 保存文件
5. 将 `index.html` 部署到任何静态网站托管服务（如 GitHub Pages、Netlify、Vercel 等）

或者直接在浏览器中打开 `index.html` 文件使用。

## 🔧 环境变量说明

在 Hugging Face Space Settings 中需要设置以下 Secrets：

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `GDRIVE_CREDENTIALS` | Google Service Account JSON 密钥（完整内容） | `{"type":"service_account",...}` |
| `GDRIVE_FOLDER_ID` | Google Drive 目标文件夹 ID | `1a2b3c4d5e6f7g8h9i0j` |
| `SECRET_CODE` | 访问密码 | `your_secret_password` |

### 获取 GDRIVE_CREDENTIALS

打开下载的 JSON 密钥文件，复制全部内容（应该是类似这样的格式）：

```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "your-service-account@your-project.iam.gserviceaccount.com",
  "client_id": "...",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "..."
}
```

将整个 JSON 对象（包括花括号）复制粘贴到 `GDRIVE_CREDENTIALS` 环境变量中。

### 获取 GDRIVE_FOLDER_ID

1. 在 Google Drive 中打开目标文件夹
2. 查看浏览器地址栏的 URL
3. URL 格式为：`https://drive.google.com/drive/folders/FOLDER_ID`
4. `FOLDER_ID` 就是您需要的文件夹 ID

## 📖 使用方法

1. 访问您部署的前端页面
2. 输入要转存的文件 URL
3. 输入正确的访问密码
4. 点击"开始转存"按钮
5. 等待处理完成，获取 Google Drive 下载链接

## ⚠️ 注意事项

- 文件大小受 Hugging Face Spaces 的内存限制（免费版约 16GB）
- 下载速度受源 URL 服务器限制
- 上传速度受 Google Drive API 限制
- 请妥善保管访问密码，避免服务被滥用
- 建议定期清理 Google Drive 文件夹

## 🛠️ 技术栈

- **Backend**: Python, Gradio, Google API Client
- **Frontend**: HTML, CSS, JavaScript
- **Cloud Services**: Hugging Face Spaces, Google Drive API

## 📝 开发说明

### 本地开发

```bash
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

### API 端点

Gradio 自动生成的 API 端点：

- `POST /api/predict`: 主要功能端点
  - 输入参数：`data: [file_url, secret_code]`
  - 输出参数：`data: [result_text]`

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 🔗 相关链接

- [Hugging Face Spaces 文档](https://huggingface.co/docs/hub/spaces)
- [Gradio 文档](https://gradio.app/docs/)
- [Google Drive API 文档](https://developers.google.com/drive/api/v3/about-sdk)

## ❓ 常见问题

### Q: 为什么上传失败？

A: 请检查：
1. Google Service Account JSON 密钥是否正确
2. 服务账号是否有权限访问目标文件夹
3. Google Drive API 是否已启用
4. 文件 URL 是否可以正常访问

### Q: 支持哪些文件类型？

A: 支持任何可以通过 HTTP/HTTPS 访问的文件，包括但不限于：
- 图片（jpg, png, gif 等）
- 视频（mp4, avi, mkv 等）
- 文档（pdf, docx, xlsx 等）
- 压缩包（zip, rar, 7z 等）

### Q: 文件大小有限制吗？

A: 受 Hugging Face Spaces 免费版内存限制（约 16GB），建议单个文件不超过 10GB。

### Q: 如何修改访问密码？

A: 在 Hugging Face Space Settings 的 Secrets 中修改 `SECRET_CODE` 环境变量即可。

### Q: 上传的文件会被删除吗？

A: 不会自动删除。您可以手动在 Google Drive 中管理这些文件。

## 🛠️ 开发说明

### 本地开发

```bash
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

### API 端点

Gradio 自动生成的 API 端点：

- `POST /api/predict`: 主要功能端点
  - 输入参数：`data: [file_url, secret_code]`
  - 输出参数：`data: [result_text]`

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 🔗 相关链接

- [Hugging Face Spaces 文档](https://huggingface.co/docs/hub/spaces)
- [Gradio 文档](https://gradio.app/docs/)
- [Google Drive API 文档](https://developers.google.com/drive/api/v3/about-sdk)

## ❓ 常见问题

### Q: 为什么上传失败？

A: 请检查：
1. Google Service Account JSON 密钥是否正确
2. 服务账号是否有权限访问目标文件夹
3. Google Drive API 是否已启用
4. 文件 URL 是否可以正常访问

### Q: 支持哪些文件类型？

A: 支持任何可以通过 HTTP/HTTPS 访问的文件，包括但不限于：
- 图片（jpg, png, gif 等）
- 视频（mp4, avi, mkv 等）
- 文档（pdf, docx, xlsx 等）
- 压缩包（zip, rar, 7z 等）

### Q: 文件大小有限制吗？

A: 受 Hugging Face Spaces 免费版内存限制（约 16GB），建议单个文件不超过 10GB。

### Q: 如何修改访问密码？

A: 在 Hugging Face Space Settings 的 Secrets 中修改 `SECRET_CODE` 环境变量即可。

### Q: 上传的文件会被删除吗？

A: 不会自动删除。您可以手动在 Google Drive 中管理这些文件。

## 🎓 学习资源

- [Gradio 快速入门](https://gradio.app/quickstart/)
- [Google Drive API Python 快速开始](https://developers.google.com/drive/api/quickstart/python)
- [Hugging Face Spaces 指南](https://huggingface.co/docs/hub/spaces-overview)
- [Python Requests 库文档](https://docs.python-requests.org/)

## 💡 使用提示

### 示例 URL 来源

可以从以下来源获取文件 URL：

1. **直接下载链接**
   - GitHub Releases 文件
   - 网盘直链
   - CDN 文件链接

2. **API 生成的链接**
   - 临时文件分享链接
   - API 返回的文件 URL

3. **公开资源**
   - 开源软件下载链接
   - 公开数据集链接

### 调试技巧

如果遇到问题，可以：

1. **查看 Space 日志**
   - 在 Hugging Face Space 页面查看实时日志
   - 检查错误信息

2. **验证环境变量**
   - 确保 JSON 格式正确
   - 检查是否有多余的空格或换行

3. **测试 Google Drive 权限**
   - 使用服务账号邮箱手动上传文件测试
   - 确认文件夹共享设置正确

4. **网络连接测试**
   - 确保 URL 可以从服务器访问
   - 检查是否有防火墙限制

## 📞 支持与反馈

如有问题或建议，欢迎通过以下方式联系：

- 提交 GitHub Issue
- 发送邮件反馈
- 在 Hugging Face Space 页面留言

---

**祝您使用愉快！** 🎉

如果这个项目对您有帮助，欢迎给个 Star ⭐️