import os
from google_auth_oauthlib.flow import InstalledAppFlow

def get_refresh_token_manual():
    """
    手动模式获取 Refresh Token (适用于无头服务器/SSH 环境)
    """
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    print("="*50)
    print("🚀 Google Drive Refresh Token 获取助手 (手动模式)")
    print("="*50)
    
    if not os.path.exists('client_secrets.json'):
        print("\n❌ 错误: 未找到 'client_secrets.json'")
        print("请确保已下载桌面应用的凭据文件并重命名为 client_secrets.json")
        return

    try:
        # 使用 OOB (Out-Of-Band) 流程
        flow = InstalledAppFlow.from_client_secrets_file(
            'client_secrets.json',
            SCOPES,
            redirect_uri='urn:ietf:wg:oauth:2.0:oob'
        )
        
        # 获取授权 URL
        auth_url, _ = flow.authorization_url(prompt='consent')
        
        print("\n1. 请复制下面的链接，在您本地电脑的浏览器中打开：")
        print("-" * 20)
        print(auth_url)
        print("-" * 20)
        
        print("\n2. 在浏览器中登录 Google 账号并授权。")
        print("3. 最后会显示一串授权代码 (Authorization Code)。")
        
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
        
    except Exception as e:
        print(f"\n❌ 发生错误: {str(e)}")

if __name__ == "__main__":
    get_refresh_token_manual()
