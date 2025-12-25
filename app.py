import os
import requests
import gradio as gr
import logging
import http.client
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from urllib.parse import urlparse, unquote
from googleapiclient.errors import HttpError
import uuid

# ---------------------------------------------------------
# 0. 配置日志
# ---------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# 1. 鉴权与服务初始化
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

def get_filename_from_response(response, url):
    content_disposition = response.headers.get("Content-Disposition")
    if content_disposition:
        import re
        fname = re.findall('filename="?([^"]+)"?', content_disposition)
        if fname:
            return unquote(fname[0])
    parsed = urlparse(url)
    return os.path.basename(unquote(parsed.path)) or "downloaded_file"

# ---------------------------------------------------------
# 2. 核心逻辑 (Download to Disk -> Upload)
# ---------------------------------------------------------
def process_upload(file_url, progress=gr.Progress()):
    if not file_url:
        return "❌ 错误: 请输入有效的 URL"
    
    temp_file_path = None
    
    try:
        # --- 1. 鉴权 ---
        service = get_drive_service()

        # --- 2. 下载到本地 ---
        logger.info(f"📥 开始下载到临时空间: {file_url}")
        
        with requests.get(file_url, stream=True, headers={'User-Agent': 'Mozilla/5.0'}) as response:
            response.raise_for_status()
            
            filename = get_filename_from_response(response, file_url)
            total_size = int(response.headers.get('Content-Length', 0))
            msg_size = f"{total_size / 1024 / 1024:.2f} MB" if total_size > 0 else "未知大小"
            
            progress(0.1, desc=f"📥 正在下载: {filename} ({msg_size})")

            # 生成唯一临时文件名
            temp_file_path = f"/tmp/{uuid.uuid4()}_{filename}"
            
            # 写入硬盘 (Download)
            downloaded = 0
            with open(temp_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        # 更新下载进度
                        if total_size > 0:
                            p = 0.1 + (0.4 * (downloaded / total_size))
                            # progress(p, desc=f"📥 下载中: {int(downloaded/total_size*100)}%")

        # --- 3. 校验本地文件 ---
        actual_size = os.path.getsize(temp_file_path)
        logger.info(f"📦 本地文件已就绪: {temp_file_path}, 大小: {actual_size} bytes")
        
        if actual_size == 0:
            return f"❌ **下载失败**: 源文件下载到本地后大小为 0。请检查源链接是否有效。"

        # --- 4. 上传到 Google Drive ---
        progress(0.5, desc=f"☁️ 正在上传到 Google Drive ({actual_size / 1024 / 1024:.2f} MB)...")
        
        folder_id = os.environ.get("GDRIVE_FOLDER_ID", "").strip()
        file_metadata = {'name': filename}
        if folder_id:
            file_metadata['parents'] = [folder_id]

        # 使用 MediaFileUpload (最稳健的本地文件上传)
        media = MediaFileUpload(
            temp_file_path,
            mimetype=response.headers.get('Content-Type', 'application/octet-stream'),
            resumable=True,
            chunksize=10 * 1024 * 1024  # 10MB 分片
        )

        request = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink, size'
        )
        
        response_obj = None
        while response_obj is None:
            status, response_obj = request.next_chunk()
            if status:
                progress_percent = int(status.progress() * 100)
                # progress(0.5 + (0.5 * status.progress()), desc=f"☁️ 上传中: {progress_percent}%")
                if progress_percent % 10 == 0:
                    logger.info(f"⏳ 上传进度: {progress_percent}%")

        file = response_obj
        file_id = file.get('id')
        cloud_size = int(file.get('size', 0))
        
        logger.info(f"✅ 上传完成. ID: {file_id}, 云端大小: {cloud_size} bytes")

        # --- 5. 清理 & 权限 ---
        # 删除临时文件
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logger.info("🧹 临时文件已清理")

        web_link = file.get('webViewLink', f"https://drive.google.com/file/d/{file_id}/view")
        perm_status = "🔒 私有"
        
        try:
            service.permissions().create(
                fileId=file_id,
                body={'role': 'reader', 'type': 'anyone'}
            ).execute()
            perm_status = "🌍 公开"
        except Exception:
            pass

        return f"""✅ **转存成功!**
        
**文件名**: {filename}
**大小**: {cloud_size / 1024 / 1024:.2f} MB
**状态**: {perm_status}
**链接**: [点击打开]({web_link})
"""

    except Exception as e:
        logger.error(f"❌ 错误: {e}", exc_info=True)
        # 尝试清理
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        return f"❌ **发生错误**: {str(e)}"

# ---------------------------------------------------------
# 3. 构建界面
# ---------------------------------------------------------
with gr.Blocks(title="URL to Drive Saver") as demo:
    gr.Markdown("# 🚀 URL to Google Drive Saver (Stable Mode)")
    
    with gr.Row():
        url_input = gr.Textbox(label="文件 URL", placeholder="https://example.com/video.mp4")
        submit_btn = gr.Button("开始转存", variant="primary")
    
    output_markdown = gr.Markdown(label="结果")

    submit_btn.click(
        fn=process_upload,
        inputs=url_input,
        outputs=output_markdown,
        api_name="save_to_drive"
    )

if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0", show_api=True)
