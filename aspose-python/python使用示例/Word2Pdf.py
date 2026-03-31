"""
Word 转 PDF 转换器
==================
使用 Aspose.Words for .NET 将 Word 文档转换为 PDF 格式。

依赖说明：
- pythonnet: Python 调用 .NET 程序集的桥接库
- Aspose.Words.dll: Aspose 文档处理核心库
- SkiaSharp.dll + libSkiaSharp.dll: 图形渲染引擎（用于渲染图片、图形等）
- Aspose.Total.NET.lic: Aspose 许可证文件（避免评估模式水印）

关键注意事项：
1. 必须调用 os.add_dll_directory() 注册 DLL 目录，否则 libSkiaSharp.dll 无法被加载
2. 必须在 import clr 之前调用 pythonnet.load() 加载 .NET 运行时
3. 加载顺序：SkiaSharp.dll → Aspose.Words.dll（确保渲染引擎先就绪）
"""

import sys
import os

# ==================================================
# 第一步：设置路径
# ==================================================
# 获取当前脚本所在目录（用于定位输入/输出文件）
script_dir = os.path.dirname(os.path.abspath(__file__))

# libs 目录包含所有 .NET DLL 文件
libs_dir = os.path.join(script_dir, "libs")

# ==================================================
# 第二步：注册 DLL 搜索目录（关键！）
# ==================================================
# Windows 上 Python 3.8+ 必须使用 os.add_dll_directory() 注册 native DLL 路径
# 如果不调用这个函数，libSkiaSharp.dll（SkiaSharp 的 native 实现）将无法被找到
# 后果：图片渲染会静默失败，PDF 中图片区域变成空白
os.add_dll_directory(libs_dir)

# ==================================================
# 第三步：加载 .NET Core 运行时
# ==================================================
# pythonnet 支持两种运行时：
# - "coreclr": .NET Core / .NET 5+ （跨平台，推荐）
# - "netfx": .NET Framework（仅 Windows，已过时）
# 
# runtime_config 指向 runtimeconfig.json，定义了 .NET 版本和依赖
import pythonnet
pythonnet.load("coreclr", runtime_config=os.path.join(libs_dir, "runtimeconfig.json"))

# ==================================================
# 第四步：导入 CLR（公共语言运行时）模块
# ==================================================
# clr 模块是 pythonnet 的核心，用于加载和调用 .NET 程序集
import clr

# ==================================================
# 第五步：加载 .NET 程序集（顺序重要！）
# ==================================================
# 先加载 SkiaSharp（图形渲染引擎）
# Aspose.Words 25.x 内部依赖 SkiaSharp 进行图片/图形渲染
clr.AddReference(os.path.join(libs_dir, "SkiaSharp.dll"))

# 再加载 Aspose.Words（文档处理核心）
clr.AddReference(os.path.join(libs_dir, "Aspose.Words.dll"))

# ==================================================
# 第六步：注册编码支持
# ==================================================
# .NET Core 默认不包含旧版代码页（如 GB2312、Big5 等）
# 必须显式注册 CodePagesEncodingProvider，否则处理中文文档可能出现乱码
clr.AddReference("System.Text.Encoding.CodePages")
import System.Text
System.Text.Encoding.RegisterProvider(System.Text.CodePagesEncodingProvider.Instance)

# ==================================================
# 第七步：导入 Aspose.Words 类
# ==================================================
from Aspose.Words import License, Document, SaveFormat

# ==================================================
# 第八步：激活 Aspose 许可证
# ==================================================
# 不激活许可证时，Aspose 会在输出文件中添加评估水印
# 许可证文件通常是 .lic 格式，需要从 Aspose 官方获取
lic = License()
lic.SetLicense(os.path.join(libs_dir, "Aspose.Total.NET.lic"))

# ==================================================
# 第九步：执行文档转换
# ==================================================
# 定义要转换的文件列表（支持 .doc 和 .docx 格式）
files_to_convert = [
    "这是一个doc格式的测试文件.doc",
    "这是一个docx格式的测试文件.docx",
]

for filename in files_to_convert:
    input_file = os.path.join(script_dir, filename)
    output_file = os.path.join(script_dir, os.path.splitext(filename)[0] + ".pdf")
    
    print(f"正在转换: {filename}")
    
    # 加载 Word 文档
    doc = Document(input_file)
    
    # 保存为 PDF 格式
    # SaveFormat.Pdf 会触发完整的文档渲染流程，包括：
    # - 文本排版
    # - 图片渲染（需要 SkiaSharp）
    # - 表格布局
    # - 页眉页脚
    doc.Save(output_file, SaveFormat.Pdf)
    
    print(f"  -> {os.path.basename(output_file)} [完成]")

print("\n全部转换完成!")
