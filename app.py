import os
import requests
import gradio as gr
import logging
import shutil
import uuid
import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from urllib.parse import urlparse, unquote

# ---------------------------------------------------------
# 0. 配置日志
# ---------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# 1. 工具函数：鉴权、文件名、日期文件夹
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
    # 1. 尝试从 Content-Disposition 获取
    content_disposition = response.headers.get("Content-Disposition")
    if content_disposition:
        import re
        fname = re.findall('filename="?([^"]+)"?', content_disposition)
        if fname:
            return unquote(fname[0])
    
    # 2. 尝试从 URL 路径获取
    parsed = urlparse(url)
    path_name = os.path.basename(unquote(parsed.path))
    
    # 3. 如果 URL 结尾是 raw/blob 或者太短，使用时间戳命名
    if not path_name or len(path_name) < 3 or path_name.lower() in ['raw', 'blob', 'file', 'download']:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"video_{timestamp}.mp4"
    
    return path_name

def get_or_create_date_folder(service, parent_id=None):
    """
    在 parent_id 下查找或创建名为 'YYYY-MM-DD' 的文件夹
    """
    folder_name = datetime.datetime.now().strftime("%Y-%m-%d")
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    
    # 查找
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get('files', [])
    
    if files:
        logger.info(f"📂 找到已有日期文件夹: {folder_name} ({files[0]['id']})")
        return files[0]['id']
    else:
        # 创建
        metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            metadata['parents'] = [parent_id]
        
        folder = service.files().create(body=metadata, fields='id').execute()
        logger.info(f"📂 创建新日期文件夹: {folder_name} ({folder['id']})")
        return folder['id']

# ---------------------------------------------------------
# 2. 核心逻辑
# ---------------------------------------------------------
def process_upload(file_url, password, progress=gr.Progress()):
    # --- 0. 密码验证 ---
    correct_pass = os.environ.get("ACCESS_PASSWORD")
    # 如果设置了环境变量且密码不匹配，则拒绝
    if correct_pass and password != correct_pass:
        return {"status": "error", "message": "❌ 密码错误，拒绝访问。"}
    
    if not file_url:
        return {"status": "error", "message": "❌ 错误: URL 为空"}

    temp_path = None
    try:
        # --- 1. 鉴权 ---
        service = get_drive_service()

        # --- 2. 下载到本地 (稳定方案) ---
        progress(0.1, desc="🚀 连接资源...")
        with requests.get(file_url, stream=True, headers={'User-Agent': 'Mozilla/5.0'}) as response:
            response.raise_for_status()
            
            filename = get_smart_filename(response, file_url)
            total_size = int(response.headers.get('Content-Length', 0))
            
            temp_path = f"/tmp/{uuid.uuid4()}_{filename}"
            logger.info(f"📥 下载到: {temp_path}")
            
            downloaded = 0
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress((downloaded/total_size)*0.4, desc="📥 下载中...")

        # --- 3. 准备文件夹 ---
        root_folder_id = os.environ.get("GDRIVE_FOLDER_ID", "").strip() or None
        # 获取或创建日期子文件夹
        target_folder_id = get_or_create_date_folder(service, root_folder_id)

        # --- 4. 上传 ---
        progress(0.5, desc="☁️ 上传到 Google Drive...")
        metadata = {'name': filename, 'parents': [target_folder_id]}
        
        media = MediaFileUpload(temp_path, resumable=True, chunksize=5*1024*1024)
        
        request = service.files().create(
            body=metadata, media_body=media, fields='id, webContentLink, webViewLink'
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress(0.5 + (status.progress()*0.5), desc="☁️ 上传中...")

        # --- 5. 权限与链接 ---
        file_id = response.get('id')
        
        # 尝试公开
        try:
            service.permissions().create(
                fileId=file_id, body={'role': 'reader', 'type': 'anyone'}
            ).execute()
        except: pass

        # 获取直连 (webContentLink 是直接下载，webViewLink 是预览)
        direct_link = response.get('webContentLink', '')
        view_link = response.get('webViewLink', '')
        
        # 清理
        os.remove(temp_path)

        # 返回 JSON 格式结果 (方便 API 调用)
        return {
            "status": "success",
            "filename": filename,
            "file_id": file_id,
            "download_link": direct_link,  # 直接下载链接
            "view_link": view_link,        # 预览链接
            "folder": datetime.datetime.now().strftime("%Y-%m-%d")
        }

    except Exception as e:
        logger.error(f"❌: {e}", exc_info=True)
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        return {"status": "error", "message": str(e)}

# ---------------------------------------------------------
# 3. 界面与 API
# ---------------------------------------------------------
def ui_wrapper(url, pwd):
    result = process_upload(url, pwd)
    if result.get("status") == "success":
        return (
            f"✅ **成功!**\n\n"
            f"📂 文件夹: {result['folder']}\n"
            f"📄 文件名: {result['filename']}\n"
            f"🔗 [预览链接]({result['view_link']})\n"
            f"⬇️ [直接下载]({result['download_link']})"
        )
    else:
        return f"❌ 失败: {result.get('message')}"

with gr.Blocks(title="URL to Drive Saver") as demo:
    gr.Markdown("# 🚀 URL to Drive (API Enabled)")
    
    with gr.Row():
        url_input = gr.Textbox(label="文件 URL")
        pwd_input = gr.Textbox(label="访问密码", type="password")
        submit_btn = gr.Button("🚀 开始转存", variant="primary")
    
    output = gr.Markdown(label="结果")

    submit_btn.click(ui_wrapper, inputs=[url_input, pwd_input], outputs=output)
    
    # 暴露为 API，名为 "upload"
    api = gr.Interface(
        fn=process_upload,
        inputs=[
            gr.Textbox(label="url"),
            gr.Textbox(label="password")
        ],
        outputs="json",
        api_name="upload"
    )

if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0", show_api=True)
