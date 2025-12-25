import os
import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import http.client

# 开启调试日志
http.client.HTTPConnection.debuglevel = 1
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_auth_only():
    print("\n" + "="*50)
    print("🛠️ 正在执行纯鉴权测试 (Test Auth Only)")
    print("="*50)

    client_id = os.environ.get("G_CLIENT_ID")
    client_secret = os.environ.get("G_CLIENT_SECRET")
    refresh_token = os.environ.get("G_REFRESH_TOKEN")

    print(f"Client ID: {client_id[:10]}... (Len: {len(str(client_id))})")
    print(f"Client Secret: {client_secret[:5]}... (Len: {len(str(client_secret))})")
    print(f"Refresh Token: {refresh_token[:10]}... (Len: {len(str(refresh_token))})")

    if not all([client_id, client_secret, refresh_token]):
        print("❌ 错误: 环境变量缺失")
        return

    try:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret
        )
        
        # 强制刷新 Token，这是最直接的验证方式
        print("\n🔄 正在尝试刷新 Access Token...")
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        print(f"✅ Token 刷新成功! 新 Access Token: {creds.token[:10]}...")

        # 构建 Service 并调用简单的 API
        print("\n📡 正在连接 Google Drive API...")
        service = build("drive", "v3", credentials=creds)
        
        print("👤 正在获取用户信息 (about.get)...")
        about = service.about().get(fields="user").execute()
        user_info = about.get('user', {})
        
        print("\n" + "="*50)
        print(f"✅ 鉴权完美通过！")
        print(f"👋 用户名: {user_info.get('displayName')}")
        print(f"📧 邮箱: {user_info.get('emailAddress')}")
        print("="*50)

    except Exception as e:
        print("\n" + "="*50)
        print(f"❌ 鉴权测试失败!")
        print(f"错误信息: {e}")
        print("="*50)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_auth_only()
