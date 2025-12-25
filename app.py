import os
import requests
import gradio as gr
import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from urllib.parse import urlparse, unquote
import uuid
from datetime import datetime
import shutil

# ---------------------------------------------------------
# 0. 配置日志
# ---------------------------------------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# 1. 辅助函数
# ---------------------------------------------------------
def get_drive_service():
    client_id = os.environ.get("G_CLIENT_ID")
    client_secret = os.environ.get("G_CLIENT_SECRET")
    refresh_token = os.environ.get("G_REFRESH_TOKEN")
    
    if not all([client_id, client_secret, refresh_token]):
        raise EnvironmentError("❌ 缺少必要的 OAuth 环境变量")

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )
    return build("drive", "v3", credentials=creds)

def get_smart_filename(response, url):
    # 1. 尝试从 Content-Disposition 获取文件名
    content_disposition = response.headers.get("Content-Disposition")
    if content_disposition:
        import re
        fname = re.findall('filename="?([^"]+)"?', content_disposition)
        if fname:
            return unquote(fname[0])
            
    # 2. 从 URL 路径获取
    parsed = urlparse(url)
    path_name = os.path.basename(unquote(parsed.path))
    
    # 3. 如果路径名太乱（比如只是 'raw'），或者包含特殊字符，则加时间戳
    if not path_name or len(path_name) < 3 or path_name.lower() == 'raw':
        return f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    
    return path_name

def get_or_create_date_folder(service, root_folder_id):
    """
    在 root_folder_id 下查找或创建名为 'YYYY-MM-DD' 的文件夹
    """
    folder_name = datetime.now().strftime("%Y-%m-%d")
    
    # 搜索文件夹是否存在
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
    if root_folder_id:
        query += f" and '{root_folder_id}' in parents"
    
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get('files', [])

    if files:
        logger.info(f"📂 找到现有日期文件夹: {folder_name} ({files[0]['id']})")
        return files[0]['id']
    else:
        # 创建新文件夹
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if root_folder_id:
            file_metadata['parents'] = [root_folder_id]
            
        file = service.files().create(body=file_metadata, fields='id').execute()
        logger.info(f"✨ 创建新日期文件夹: {folder_name} ({file.get('id')})")
        return file.get('id')

# ---------------------------------------------------------
# 2. 核心处理逻辑
# ---------------------------------------------------------
def process_upload(file_url, access_pwd, progress=gr.Progress()):
    # --- 0. 密码校验 ---
    env_pwd = os.environ.get("API_PASSWORD", "")
    if env_pwd and access_pwd != env_pwd:
        logger.warning("❌ 访问拒绝: 密码错误")
        return {"status": "error", "message": "❌ 密码错误，拒绝访问"}
    
    if not file_url:
        return {"status": "error", "message": "❌ URL 为空"}
    
    temp_file_path = None
    try:
        service = get_drive_service()

        # --- 1. 下载到本地 ---
        logger.info(f"📥 开始下载: {file_url}")
        progress(0, desc="🚀 正在连接...")
        
        with requests.get(file_url, stream=True, headers={'User-Agent': 'Mozilla/5.0'}) as response:
            response.raise_for_status()
            
            filename = get_smart_filename(response, file_url)
            total_size = int(response.headers.get('Content-Length', 0))
            
            # 临时路径
            temp_file_path = f"/tmp/{uuid.uuid4()}_{filename}"
            
            with open(temp_file_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress((downloaded/total_size)*0.5, desc="📥 下载中...")

        local_size = os.path.getsize(temp_file_path)
        if local_size == 0:
            return {"status": "error", "message": "下载失败: 文件大小为 0"}

        # --- 2. 准备上传目录 (日期文件夹) ---
        root_folder_id = os.environ.get("GDRIVE_FOLDER_ID", "").strip()
        target_folder_id = get_or_create_date_folder(service, root_folder_id)

        # --- 3. 上传 ---
        progress(0.5, desc="☁️ 正在上传到 Google Drive...")
        
        file_metadata = {
            'name': filename,
            'parents': [target_folder_id]
        }
        
        media = MediaFileUpload(
            temp_file_path,
            resumable=True,
            chunksize=10*1024*1024
        )

        request = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webContentLink, webViewLink, size'
        )
        
        response_obj = None
        while response_obj is None:
            status, response_obj = request.next_chunk()
            if status:
                progress(0.5 + (0.5 * status.progress()), desc="☁️ 上传中...")

        file_id = response_obj.get('id')
        
        # --- 4. 设置公开权限并获取链接 ---
        try:
            service.permissions().create(
                fileId=file_id,
                body={'role': 'reader', 'type': 'anyone'}
            ).execute()
        except Exception: pass
        
        # 获取直链
        web_content_link = response_obj.get('webContentLink', '') # 直链 (下载)
        web_view_link = response_obj.get('webViewLink', '')       # 预览链 (观看)

        # 构造详细的返回信息
        result = {
            "status": "success",
            "filename": filename,
            "file_id": file_id,
            "folder": datetime.now().strftime("%Y-%m-%d"),
            "size_mb": round(local_size / 1024 / 1024, 2),
            "download_url": web_content_link,  # 👈 这是给 AI 用的直链
            "view_url": web_view_link
        }
        
        return str(result) # 返回字符串给界面显示，API 调用方可以解析 JSON

    except Exception as e:
        logger.error(f"❌ 错误: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
        
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# ---------------------------------------------------------
# 3. 构建界面
# ---------------------------------------------------------
with gr.Blocks(title="URL to Drive Saver") as demo:
    gr.Markdown("# 🚀 URL to Google Drive Saver (API Enabled)")
    
    with gr.Row():
        url_input = gr.Textbox(label="文件 URL")
        pwd_input = gr.Textbox(label="访问密码 (API Key)", type="password")
        submit_btn = gr.Button("开始转存", variant="primary")
    
    # 输出改为 Textbox 以便复制，或者给 API 返回 JSON 字符串
    output_json = gr.Textbox(label="执行结果 (JSON)", show_copy_button=True)

    submit_btn.click(
        fn=process_upload,
        inputs=[url_input, pwd_input],
        outputs=output_json,
        api_name="save" # 👈 这个 api_name 很重要
    )

if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0", show_api=True)
