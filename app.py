import os
import io
import json
import requests
import gradio as gr
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError
from urllib.parse import urlparse
import traceback

# 从环境变量加载配置
GDRIVE_CREDENTIALS = os.environ.get('GDRIVE_CREDENTIALS')
GDRIVE_FOLDER_ID = os.environ.get('GDRIVE_FOLDER_ID')
SECRET_CODE = os.environ.get('SECRET_CODE', 'default_secret')
# 新增：文件夹所有者邮箱（用于转移所有权）
OWNER_EMAIL = os.environ.get('OWNER_EMAIL', '')

# Google Drive API 作用域 - 使用完整权限
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    """初始化 Google Drive 服务"""
    try:
        if not GDRIVE_CREDENTIALS:
            raise ValueError("GDRIVE_CREDENTIALS 环境变量未设置")
        
        # 解析 JSON 凭据
        credentials_info = json.loads(GDRIVE_CREDENTIALS)
        credentials = service_account.Credentials.from_service_account_info(
            credentials_info, scopes=SCOPES
        )
        
        service = build('drive', 'v3', credentials=credentials)
        return service
    except Exception as e:
        raise Exception(f"初始化 Google Drive 服务失败: {str(e)}")

def get_filename_from_url(url, content_disposition=None):
    """从 URL 或 Content-Disposition 头中提取文件名"""
    if content_disposition:
        import re
        filename_match = re.findall('filename="?([^"]+)"?', content_disposition)
        if filename_match:
            return filename_match[0]
    
    # 从 URL 中提取文件名
    parsed_url = urlparse(url)
    filename = os.path.basename(parsed_url.path)
    
    # 如果没有文件名或文件名无效，使用默认名称
    if not filename or '.' not in filename:
        filename = 'downloaded_file'
    
    return filename

def upload_to_drive(file_url, secret_code):
    """
    从 URL 下载文件并上传到 Google Drive
    
    Args:
        file_url: 要下载的文件 URL
        secret_code: 访问密码
    
    Returns:
        str: 成功时返回下载链接，失败时返回错误信息
    """
    # 验证密码
    if secret_code != SECRET_CODE:
        return "❌ 密码错误，访问被拒绝"
    
    # 验证 URL
    if not file_url or not file_url.startswith(('http://', 'https://')):
        return "❌ 请提供有效的 URL"
    
    try:
        # 初始化 Google Drive 服务
        service = get_drive_service()
        
        # 第一步：发送 HEAD 请求获取文件信息
        print(f"正在获取文件信息: {file_url}")
        head_response = requests.head(file_url, allow_redirects=True, timeout=10)
        
        # 获取文件名
        content_disposition = head_response.headers.get('Content-Disposition')
        filename = get_filename_from_url(file_url, content_disposition)
        
        # 获取文件大小（如果可用）
        content_length = head_response.headers.get('Content-Length')
        if content_length:
            file_size_mb = int(content_length) / (1024 * 1024)
            print(f"文件大小: {file_size_mb:.2f} MB")
        
        # 第二步：流式下载文件
        print(f"开始下载文件: {filename}")
        response = requests.get(file_url, stream=True, timeout=30)
        response.raise_for_status()
        
        # 使用 BytesIO 作为内存缓冲区
        file_buffer = io.BytesIO()
        
        # 分块下载
        chunk_size = 8192
        downloaded = 0
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                file_buffer.write(chunk)
                downloaded += len(chunk)
        
        print(f"下载完成，总大小: {downloaded / (1024 * 1024):.2f} MB")
        
        # 重置缓冲区指针到开始位置
        file_buffer.seek(0)
        
        # 第三步：上传到 Google Drive
        print(f"开始上传到 Google Drive: {filename}")
        
        # 获取 MIME 类型
        content_type = response.headers.get('Content-Type', 'application/octet-stream')
        
        file_metadata = {
            'name': filename,
        }
        
        # 如果设置了文件夹ID，添加到父文件夹
        if GDRIVE_FOLDER_ID:
            file_metadata['parents'] = [GDRIVE_FOLDER_ID]
        
        media = MediaIoBaseUpload(
            file_buffer,
            mimetype=content_type,
            resumable=True,
            chunksize=1024*1024  # 1MB chunks
        )
        
        # 上传文件，支持共享驱动器
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink, webContentLink, owners',
            supportsAllDrives=True
        ).execute()
        
        file_id = file.get('id')
        print(f"上传成功，文件 ID: {file_id}")
        
        # 第四步：如果设置了所有者邮箱，尝试转移所有权
        if OWNER_EMAIL:
            try:
                print(f"正在将文件所有权转移给: {OWNER_EMAIL}")
                permission = {
                    'type': 'user',
                    'role': 'owner',
                    'emailAddress': OWNER_EMAIL
                }
                service.permissions().create(
                    fileId=file_id,
                    body=permission,
                    transferOwnership=True,
                    supportsAllDrives=True
                ).execute()
                print("所有权转移成功")
            except HttpError as e:
                print(f"所有权转移失败，尝试设置编辑权限: {str(e)}")
                # 如果转移失败，至少给予编辑权限
                try:
                    permission = {
                        'type': 'user',
                        'role': 'writer',
                        'emailAddress': OWNER_EMAIL
                    }
                    service.permissions().create(
                        fileId=file_id,
                        body=permission,
                        supportsAllDrives=True
                    ).execute()
                except:
                    pass
        
        # 第五步：设置文件权限为公开可读
        try:
            permission = {
                'type': 'anyone',
                'role': 'reader'
            }
            service.permissions().create(
                fileId=file_id,
                body=permission,
                supportsAllDrives=True
            ).execute()
            print("文件权限设置成功")
        except HttpError as e:
            print(f"设置权限时出现警告: {str(e)}")
        
        # 获取下载链接
        download_link = file.get('webContentLink') or file.get('webViewLink')
        
        result = f"""
✅ 上传成功！

📁 文件名: {filename}
🔗 下载链接: {download_link}
📊 文件大小: {downloaded / (1024 * 1024):.2f} MB

您可以通过上述链接访问或下载文件。
        """
        
        return result.strip()
        
    except requests.exceptions.RequestException as e:
        error_msg = f"❌ 下载文件时出错: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return error_msg
    
    except HttpError as e:
        error_msg = f"❌ Google Drive API 错误: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return error_msg
    
    except Exception as e:
        error_msg = f"❌ 发生未知错误: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return error_msg

# 创建 Gradio 界面
with gr.Blocks(title="URL to Google Drive", theme=gr.themes.Soft()) as demo:
    gr.Markdown("""
    # 🚀 URL to Google Drive Service
    
    将任意 URL 的文件直接转存到 Google Drive
    """)
    
    with gr.Row():
        with gr.Column():
            file_url_input = gr.Textbox(
                label="文件 URL",
                placeholder="请输入文件的完整 URL (http:// 或 https://)",
                lines=2
            )
            secret_code_input = gr.Textbox(
                label="访问密码",
                placeholder="请输入访问密码",
                type="password"
            )
            submit_btn = gr.Button("🚀 开始转存", variant="primary")
    
    with gr.Row():
        output = gr.Textbox(
            label="结果",
            lines=10,
            show_copy_button=True
        )
    
    submit_btn.click(
        fn=upload_to_drive,
        inputs=[file_url_input, secret_code_input],
        outputs=output
    )
    
    gr.Markdown("""
    ---
    ### 📝 使用说明
    1. 输入要转存的文件 URL
    2. 输入正确的访问密码
    3. 点击"开始转存"按钮
    4. 等待处理完成，获取 Google Drive 下载链接
    
    ### ⚠️ 注意事项
    - 支持任何可通过 HTTP/HTTPS 访问的文件
    - 文件将被上传到配置的 Google Drive 文件夹
    - 上传后的文件默认设置为公开可读
    """)

# 启动应用
if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_api=True
    )
