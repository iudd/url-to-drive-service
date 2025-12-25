import os
from google_auth_oauthlib.flow import InstalledAppFlow

def get_refresh_token_manual_input():
    """
    完全手动模式：直接输入 Client ID 和 Secret，无需 json 文件
    """
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    print("="*50)
    print("🚀 Google Drive Refresh Token 获取助手 (纯手动版)")
    print("="*50)
    
    # 1. 直接让用户输入凭据信息
    print("\n请准备好您的 Google Cloud Console -> 凭据 -> OAuth 客户端 ID 信息")
    print("注意：Client ID 通常以 .apps.googleusercontent.com 结尾")
    
    client_id = input("\n👉 请输入 Client ID: ").strip()
    client_secret = input("👉 请输入 Client Secret: ").strip()
    
    if not client_id or not client_secret:
        print("❌ 错误: ID 或 Secret 不能为空")
        return

    # 构造配置字典
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
        }
    }

    try:
        # 使用配置字典初始化流程
        flow = InstalledAppFlow.from_client_config(
            client_config,
            SCOPES,
            redirect_uri='urn:ietf:wg:oauth:2.0:oob'
        )
        
        # 获取授权 URL
        auth_url, _ = flow.authorization_url(prompt='consent')
        
        print("\n" + "-" * 20)
        print("1. 请复制下面的长链接，在您本地电脑浏览器打开：")
        print(auth_url)
        print("-" * 20)
        
        print("\n2. 在浏览器登录 Google 账号 -> 允许访问。")
        print("3. 页面会显示一串授权代码 (Authorization Code)。")
        
        # 手动输入代码
        code = input("\n✍️ 请在此粘贴授权代码并回车: ").strip()
        
        # 换取 Token
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        print("\n" + "="*50)
        print("✅ 授权成功！")
        print("="*50)
        print(f"\n您的 Refresh Token:\n\n{creds.refresh_token}\n")
        print("="*50)
        print("\n接下来请去 Hugging Face 配置 Secrets:")
        print(f"G_CLIENT_ID: {client_id}")
        print(f"G_CLIENT_SECRET: {client_secret}")
        print(f"G_REFRESH_TOKEN: (上面那个长字符串)")
        
    except Exception as e:
        print(f"\n❌ 发生错误: {str(e)}")

if __name__ == "__main__":
    get_refresh_token_manual_input()
