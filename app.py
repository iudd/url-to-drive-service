import os
import requests
import gradio as gr
import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from urllib.parse import urlparse, unquote
import uuid
import shutil

# ---------------------------------------------------------
# 0. 配置日志 (INFO)
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
# 2. 核心处理逻辑 (落盘暂存模式 - 绝对稳健)
# ---------------------------------------------------------
def process_upload(file_url, progress=gr.Progress()):
    if not file_url:
        return "❌ 错误: 请输入有效的 URL"
    
    temp_filepath = None
    try:
        # --- 1. 鉴权 ---
        try:
            service = get_drive_service()
        except Exception as e:
            return f"❌ **鉴权失败**: {str(e)}"

        # --- 2. 下载到临时文件 ---
        progress(0, desc="🚀 初始化下载...")
        logger.info(f"📥 [Phase 1] 开始下载: {file_url}")
        
        with requests.get(file_url, stream=True, headers={'User-Agent': 'Mozilla/5.0'}) as response:
            response.raise_for_status()
            
            filename = get_filename_from_response(response, file_url)
            total_size = int(response.headers.get('Content-Length', 0))
            
            # 使用 UUID 防止文件名冲突
            temp_filename = f"{uuid.uuid4()}_{filename}"
            temp_filepath = os.path.join("/tmp", temp_filename)
            
            logger.info(f"💾 正在写入临时文件: {temp_filepath}")
            
            with open(temp_filepath, 'wb') as f:
                downloaded = 0
                # 1MB 缓冲区写入硬盘
                for chunk in response.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # 更新下载进度 (0% - 50%)
                        if total_size > 0:
                            p = (downloaded / total_size) * 0.5
                            progress(p, desc=f"📥 下载中: {downloaded/1024/1024:.1f} MB")
        
        # --- 3. 校验本地文件 ---
        local_size = os.path.getsize(temp_filepath)
        logger.info(f"✅ 本地下载完成. 大小: {local_size} bytes")
        
        if local_size == 0:
            return "❌ **下载失败**: 源文件下载到本地后大小为 0KB，请检查 URL 是否有效。"

        # --- 4. 上传到 Google Drive ---
        progress(0.5, desc="☁️ 准备上传...")
        logger.info(f"🚀 [Phase 2] 开始上传到 Google Drive")
        
        folder_id = os.environ.get("GDRIVE_FOLDER_ID", "").strip()
        file_metadata = {'name': filename}
        if folder_id:
            file_metadata['parents'] = [folder_id]

        # 使用 MediaFileUpload (针对本地文件，这是 Google 最稳健的上传方式)
        media = MediaFileUpload(
            temp_filepath,
            resumable=True,
            chunksize=10 * 1024 * 1024 
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
                # 更新上传进度 (50% - 100%)
                upload_prog = status.progress()
                total_prog = 0.5 + (upload_prog * 0.5)
                progress(total_prog, desc=f"☁️ 上传中: {int(upload_prog * 100)}%")
                
        file = response_obj
        file_id = file.get('id')
        uploaded_size = int(file.get('size', 0))
        logger.info(f"✅ 上传完成. ID: {file_id}, 云端大小: {uploaded_size}")

        if uploaded_size == 0:
             return f"❌ **上传警告**: 云端文件 0KB，但本地文件正常({local_size})。这非常罕见。"

        # --- 5. 权限设置 ---
        web_link = file.get('webViewLink', f"https://drive.google.com/file/d/{file_id}/view")
        perm_status = "🔒 私有"
        try:
            progress(0.95, desc="🔓 设置权限...")
            service.permissions().create(
                fileId=file_id,
                body={'role': 'reader', 'type': 'anyone'}
            ).execute()
            perm_status = "🌍 公开"
        except Exception: pass

        return f"""✅ **转存成功!**
        
**文件名**: {filename}
**本地大小**: {local_size / 1024 / 1024:.2f} MB
**云端大小**: {uploaded_size / 1024 / 1024:.2f} MB
**状态**: {perm_status}
**链接**: [Google Drive]({web_link})
"""

    except Exception as e:
        logger.error(f"❌ 错误: {e}", exc_info=True)
        return f"❌ **发生错误**: {str(e)}"
        
    finally:
        # --- 6. 清理临时文件 ---
        if temp_filepath and os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
                logger.info(f"🧹 已删除临时文件: {temp_filepath}")
            except Exception as e:
                logger.warning(f"⚠️ 无法删除临时文件: {e}")

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
