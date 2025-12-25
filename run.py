import os
import subprocess

if __name__ == "__main__":
    print("🚀 启动独立鉴权测试...")
    # 运行测试脚本
    subprocess.run(["python", "test_auth.py"])
    
    # 启动原来的 app
    print("\n🚀 启动主程序 app.py ...")
    subprocess.run(["python", "app.py"])
