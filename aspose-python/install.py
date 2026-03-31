#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aspose.Words 智能安装脚本

支持 Windows 和 Linux 系统
自动检测安装状态，避免重复安装
"""

import os
import sys
import subprocess
import platform
import shutil
import json

def command_exists(cmd):
    """检查命令是否存在"""
    try:
        subprocess.run(["which", cmd], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False

class AsposeSmartInstaller:
    """Aspose.Words 智能安装器"""
    
    def __init__(self):
        """初始化安装器"""
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.libs_dir = os.path.join(self.script_dir, "lib")
        self.system = platform.system().lower()
        self.required_files = [
            "Aspose.Total.NET.lic",
            "Aspose.Words.dll",
            "SkiaSharp.dll",
            "System.Text.Encoding.CodePages.dll",
            "runtimeconfig.json"
        ]
        
    def check_installation_status(self):
        """检查安装状态"""
        print("检查安装状态...")
        
        # 检查 libs 目录是否存在
        if not os.path.exists(self.libs_dir):
            print("  ✓ 首次安装")
            return False
        
        # 检查必需文件是否存在
        missing_files = []
        for file in self.required_files:
            file_path = os.path.join(self.libs_dir, file)
            if not os.path.exists(file_path):
                missing_files.append(file)
        
        # 检查 native DLL（仅 Windows）
        if self.system == "windows":
            native_file = "libSkiaSharp.dll"
            native_path = os.path.join(self.libs_dir, native_file)
            if not os.path.exists(native_path):
                missing_files.append(native_file)
        
        if missing_files:
            print(f"  ✓ 需要安装，缺少文件: {', '.join(missing_files)}")
            return False
        
        # 检查 pythonnet 是否已安装
        try:
            import pythonnet
            print("  ✓ pythonnet 已安装")
        except ImportError:
            print("  ✓ 需要安装 pythonnet")
            return False
        
        # 检查许可证激活
        try:
            license_status = self.check_license_activation()
            if license_status:
                print("  ✓ 许可证已激活")
                return True
            else:
                print("  ✓ 许可证未激活，需要重新配置")
                return False
        except Exception as e:
            print(f"  ✓ 许可证检查失败: {e}")
            return False
    
    def check_license_activation(self):
        """检查许可证是否已激活"""
        try:
            # 注册 DLL 搜索目录（仅 Windows）
            if platform.system().lower() == "windows":
                if hasattr(os, "add_dll_directory"):
                    os.add_dll_directory(self.libs_dir)
            
            # 加载 .NET Core 运行时
            import pythonnet
            runtime_config = os.path.join(self.libs_dir, "runtimeconfig.json")
            pythonnet.load("coreclr", runtime_config=runtime_config)
            
            # 导入 CLR
            import clr
            
            # 加载程序集
            clr.AddReference(os.path.join(self.libs_dir, "SkiaSharp.dll"))
            clr.AddReference(os.path.join(self.libs_dir, "Aspose.Words.dll"))
            
            # 导入 Aspose.Words License 类
            from Aspose.Words import License
            
            # 尝试激活许可证
            lic = License()
            license_path = os.path.join(self.libs_dir, "Aspose.Total.NET.lic")
            
            import System.IO
            license_stream = System.IO.FileStream(license_path, System.IO.FileMode.Open, System.IO.FileAccess.Read)
            try:
                lic.SetLicense(license_stream)
                return True
            finally:
                license_stream.Dispose()
                
        except Exception as e:
            print(f"许可证激活检查失败: {e}")
            return False
    
    def check_python(self):
        """检查 Python 版本"""
        print("检查 Python 版本...")
        version = sys.version_info
        if version.major < 3 or version.minor < 12:
            print("错误: 需要 Python 3.12 或更高版本")
            return False
        print(f"  ✓ Python {version.major}.{version.minor}.{version.micro}")
        
        # 检查是否为 64 位
        is_64bit = sys.maxsize > 2**32
        if not is_64bit:
            print("错误: 需要 64 位 Python")
            return False
        print("  ✓ 64 位 Python")
        return True
    
    def install_windows(self):
        """Windows 系统安装"""
        print("\n=== Windows 系统安装 ===")
        
        # 安装 pythonnet
        print("安装 pythonnet...")
        try:
            # 尝试安装 pythonnet
            print("  尝试使用默认源安装...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "pythonnet", "--timeout", "60"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("  ✓ pythonnet 安装成功")
            else:
                print("  ✗ 默认源安装失败，尝试使用 --no-build-isolation")
                # 尝试使用 --no-build-isolation
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "pythonnet", "--no-build-isolation", "--timeout", "60"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    print("  ✓ pythonnet 安装成功")
                else:
                    # 尝试使用国内镜像源
                    print("  ✗ 安装失败，尝试使用国内镜像源...")
                    mirrors = [
                        "https://pypi.tuna.tsinghua.edu.cn/simple",
                        "https://mirrors.aliyun.com/pypi/simple",
                        "https://pypi.mirrors.ustc.edu.cn/simple"
                    ]
                    
                    for mirror in mirrors:
                        print(f"  尝试使用镜像源: {mirror}")
                        result = subprocess.run(
                            [sys.executable, "-m", "pip", "install", "pythonnet", "--no-build-isolation", "--timeout", "60", "-i", mirror],
                            capture_output=True,
                            text=True
                        )
                        if result.returncode == 0:
                            print("  ✓ pythonnet 安装成功")
                            break
                    else:
                        # 所有方法都失败
                        print("  ✗ pythonnet 安装失败")
                        print(f"  错误信息: {result.stderr[:500]}...")
                        return False
        except Exception as e:
            print(f"  ✗ pythonnet 安装失败: {e}")
            return False
        
        # 复制 DLL 文件
        self._copy_dll_files()
        return True
    
    def install_linux(self):
        """Linux 系统安装"""
        print("\n=== Linux 系统安装 ===")
        
        # 安装 .NET 8.0 SDK
        print("安装 .NET 8.0 SDK...")
        try:
            # 检查包管理器类型
            if command_exists("apt"):
                # Debian/Ubuntu
                subprocess.run(["sudo", "apt", "update"], check=True)
                subprocess.run(["sudo", "apt", "install", "-y", "dotnet-sdk-8.0"], check=True)
            elif command_exists("dnf"):
                # Fedora/RHEL
                subprocess.run(["sudo", "dnf", "install", "-y", "dotnet-sdk-8.0"], check=True)
            elif command_exists("yum"):
                # 旧版 RHEL/CentOS
                subprocess.run(["sudo", "yum", "install", "-y", "dotnet-sdk-8.0"], check=True)
            elif command_exists("pacman"):
                # Arch Linux
                subprocess.run(["sudo", "pacman", "-Syu", "--noconfirm", "dotnet-sdk"], check=True)
            else:
                print("  ✗ 不支持的包管理器")
                print("  请手动安装 .NET 8.0 SDK")
                return False
            print("  ✓ .NET 8.0 SDK 安装成功")
        except subprocess.CalledProcessError:
            print("  ✗ .NET 8.0 SDK 安装失败")
            print("  请手动安装 .NET 8.0 SDK")
            return False
        
        # 创建并使用虚拟环境
        print("创建 Python 虚拟环境...")
        venv_dir = os.path.join(self.script_dir, "venv")
        if os.path.exists(venv_dir):
            print("  ✓ 虚拟环境已存在")
        else:
            try:
                subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
                print("  ✓ 虚拟环境创建成功")
            except subprocess.CalledProcessError:
                print("  ✗ 虚拟环境创建失败")
                return False
        
        # 安装 pythonnet 到虚拟环境
        print("安装 pythonnet...")
        pip_executable = os.path.join(venv_dir, "bin", "pip")
        try:
            # 尝试使用默认源
            print("  尝试使用默认源安装...")
            result = subprocess.run(
                [pip_executable, "install", "pythonnet", "--timeout", "60"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print("  ✓ pythonnet 安装成功")
            else:
                # 尝试使用国内镜像源
                print("  ✗ 默认源安装失败，尝试使用国内镜像源...")
                mirrors = [
                    "https://pypi.tuna.tsinghua.edu.cn/simple",
                    "https://mirrors.aliyun.com/pypi/simple",
                    "https://pypi.mirrors.ustc.edu.cn/simple"
                ]
                
                for mirror in mirrors:
                    print(f"  尝试使用镜像源: {mirror}")
                    result = subprocess.run(
                        [pip_executable, "install", "pythonnet", "--timeout", "60", "-i", mirror],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0:
                        print("  ✓ pythonnet 安装成功")
                        break
                else:
                    # 所有镜像源都失败
                    print("  ✗ pythonnet 安装失败")
                    print(f"  错误信息: {result.stderr[:500]}...")
                    return False
        except Exception as e:
            print(f"  ✗ pythonnet 安装失败: {e}")
            return False
        
        # 复制 DLL 文件
        self._copy_dll_files()
        return True
    
    def _copy_dll_files(self):
        """复制 DLL 文件"""
        print("复制 DLL 文件...")
        
        # 查找源目录（按优先级）
        aspose_source = None
        
        # 1. 检查当前目录下的 lib 目录（单数）
        current_lib_dir = os.path.join(self.script_dir, "lib")
        if os.path.exists(current_lib_dir):
            aspose_source = current_lib_dir
            print(f"  ✓ 找到 DLL 源目录: {aspose_source}")
        
        # 2. 检查当前目录下的 libs 目录（复数）
        if not aspose_source:
            current_libs_dir = os.path.join(self.script_dir, "libs")
            if os.path.exists(current_libs_dir):
                aspose_source = current_libs_dir
                print(f"  ✓ 找到 DLL 源目录: {aspose_source}")
        
        # 3. 检查上级目录的 lib 目录
        if not aspose_source:
            parent_lib_dir = os.path.join(self.script_dir, "..", "lib")
            if os.path.exists(parent_lib_dir):
                aspose_source = parent_lib_dir
                print(f"  ✓ 找到 DLL 源目录: {aspose_source}")
        
        # 4. 检查上级目录的 libs 目录
        if not aspose_source:
            parent_libs_dir = os.path.join(self.script_dir, "..", "libs")
            if os.path.exists(parent_libs_dir):
                aspose_source = parent_libs_dir
                print(f"  ✓ 找到 DLL 源目录: {aspose_source}")
        
        # 5. 检查环境变量中指定的目录
        if not aspose_source:
            aspose_libs = os.environ.get("ASPOSE_LIBS")
            if aspose_libs and os.path.exists(aspose_libs):
                aspose_source = aspose_libs
                print(f"  ✓ 找到 DLL 源目录（环境变量）: {aspose_source}")
        
        # 6. 检查常见的系统路径
        if not aspose_source:
            common_paths = []
            if self.system == "windows":
                common_paths = [
                    os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\Administrator"), "Downloads", "Aspose.Words", "libs"),
                    "C:\\Downloads\\Aspose.Words\\libs",
                ]
            else:
                common_paths = [
                    os.path.join(os.environ.get("HOME", "/home/user"), "Downloads", "Aspose.Words", "libs"),
                    "/opt/Aspose.Words/libs",
                ]
            
            for path in common_paths:
                if os.path.exists(path):
                    aspose_source = path
                    print(f"  ✓ 找到 DLL 源目录: {aspose_source}")
                    break
        
        if not aspose_source:
            print("  ✗ 找不到 DLL 源目录")
            print("  请将 Aspose.Words 相关文件放置在以下目录之一:")
            print(f"    - {os.path.join(self.script_dir, 'lib')}")
            print(f"    - {os.path.join(self.script_dir, 'libs')}")
            print(f"    - {os.path.join(self.script_dir, '..', 'lib')}")
            print(f"    - {os.path.join(self.script_dir, '..', 'libs')}")
            if self.system == "windows":
                print(f"    - {os.path.join(os.environ.get('USERPROFILE', 'C:\\Users\\Administrator'), 'Downloads', 'Aspose.Words', 'libs')}")
            else:
                print(f"    - {os.path.join(os.environ.get('HOME', '/home/user'), 'Downloads', 'Aspose.Words', 'libs')}")
            print("  或设置环境变量 ASPOSE_LIBS 指向 DLL 目录")
            return
        
        # 创建目标目录
        os.makedirs(self.libs_dir, exist_ok=True)
        
        # 复制文件
        for file in self.required_files:
            src = os.path.join(aspose_source, file)
            dst = os.path.join(self.libs_dir, file)
            if os.path.exists(src):
                # 检查是否是同一个文件
                if os.path.abspath(src) == os.path.abspath(dst):
                    print(f"  ✓ 跳过复制 {file}（源和目标相同）")
                else:
                    shutil.copy2(src, dst)
                    print(f"  ✓ 复制 {file}")
            else:
                print(f"  ✗ 找不到 {file}")
        
        # 复制 native DLL（仅 Windows）
        if self.system == "windows":
            native_file = "libSkiaSharp.dll"
            src = os.path.join(aspose_source, native_file)
            dst = os.path.join(self.libs_dir, native_file)
            if os.path.exists(src):
                # 检查是否是同一个文件
                if os.path.abspath(src) == os.path.abspath(dst):
                    print(f"  ✓ 跳过复制 {native_file}（源和目标相同）")
                else:
                    shutil.copy2(src, dst)
                    print(f"  ✓ 复制 {native_file}")
            else:
                print(f"  ✗ 找不到 {native_file}")
    
    def create_runtime_config(self):
        """创建 runtimeconfig.json 文件"""
        print("创建运行时配置文件...")
        
        config_content = {
            "runtimeOptions": {
                "tfm": "net8.0",
                "framework": {
                    "name": "Microsoft.NETCore.App" if self.system == "linux" else "Microsoft.WindowsDesktop.App",
                    "version": "8.0.0"
                }
            }
        }
        
        config_path = os.path.join(self.libs_dir, "runtimeconfig.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_content, f, indent=2)
        
        print("  ✓ runtimeconfig.json 创建成功")
    
    def run(self):
        """运行安装过程"""
        print("=======================================")
        print("Aspose.Words 智能安装脚本")
        print("=======================================")
        
        # 检查 Python
        if not self.check_python():
            return False
        
        # 检查安装状态
        is_installed = self.check_installation_status()
        
        if is_installed:
            print("\n🎉 环境已安装并激活，无需重新安装！")
            print("\n可以直接运行转换脚本:")
            if self.system == "windows":
                print(f"  {sys.executable} convert.py 源文档.docx 模板.docx 输出文档.docx")
            else:  # Ubuntu
                venv_python = os.path.join(self.script_dir, "venv", "bin", "python3")
                print(f"  {venv_python} convert.py 源文档.docx 模板.docx 输出文档.docx")
                print(f"  或使用: ./convert.sh 源文档.docx 模板.docx 输出文档.docx")
            return True
        
        # 根据系统执行安装
        if self.system == "windows":
            success = self.install_windows()
        elif self.system == "linux":
            # 支持所有 Linux 系统
            success = self.install_linux()
        else:
            print(f"错误: 不支持 {self.system} 系统")
            return False
        
        # 创建运行时配置
        self.create_runtime_config()
        
        if success:
            print("\n🎉 安装完成！")
            print("\n使用方法:")
            print("1. 运行转换脚本")
            print("2. 或使用示例命令:")
            if self.system == "windows":
                print(f"   {sys.executable} convert.py 源文档.docx 模板.docx 输出文档.docx")
            else:  # Ubuntu
                venv_python = os.path.join(self.script_dir, "venv", "bin", "python3")
                print(f"   {venv_python} convert.py 源文档.docx 模板.docx 输出文档.docx")
                print(f"   或使用: ./convert.sh 源文档.docx 模板.docx 输出文档.docx")
        else:
            print("\n❌ 安装失败，请检查错误信息")
        
        return success

if __name__ == "__main__":
    installer = AsposeSmartInstaller()
    installer.run()
