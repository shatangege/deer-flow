#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用 Aspose.Words for .NET 进行文档格式转换

支持跨平台（Windows 和 Ubuntu 24.04）
"""

import sys
import os
import platform

class AsposeWordFormatter:
    """使用 Aspose.Words 进行文档格式转换"""
    
    def __init__(self):
        """初始化格式化器"""
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.libs_dir = os.path.join(self.script_dir, "lib")
        self.system = platform.system().lower()
        self._load_dependencies()
    
    def _load_dependencies(self):
        """加载依赖"""
        print("加载 Aspose.Words 依赖...")
        
        # 注册 DLL 搜索目录（仅 Windows）
        if self.system == "windows":
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(self.libs_dir)
                print("  ✓ 注册 DLL 搜索目录")
        
        # 加载 .NET Core 运行时
        import pythonnet
        runtime_config = os.path.join(self.libs_dir, "runtimeconfig.json")
        pythonnet.load("coreclr", runtime_config=runtime_config)
        
        # 导入 CLR
        import clr
        
        # 加载程序集（顺序重要）
        clr.AddReference(os.path.join(self.libs_dir, "SkiaSharp.dll"))
        clr.AddReference(os.path.join(self.libs_dir, "Aspose.Words.dll"))
        
        # 注册编码支持
        clr.AddReference("System.Text.Encoding.CodePages")
        import System.Text
        System.Text.Encoding.RegisterProvider(System.Text.CodePagesEncodingProvider.Instance)
        
        # 导入 Aspose.Words 类
        global License, Document, SaveFormat
        from Aspose.Words import License, Document, SaveFormat
        
        # 激活许可证
        self._activate_license()
    
    def _activate_license(self):
        """激活 Aspose 许可证"""
        try:
            lic = License()
            license_path = os.path.join(self.libs_dir, "Aspose.Total.NET.lic")
            
            # 检查许可证文件是否存在
            if not os.path.exists(license_path):
                print(f"⚠ 许可证文件不存在: {license_path}")
                print("  将使用评估模式，输出文档会有水印")
                return
            
            # 导入 System.IO
            import System.IO
            
            # 使用 .NET FileStream 加载许可证
            license_stream = System.IO.FileStream(license_path, System.IO.FileMode.Open, System.IO.FileAccess.Read)
            try:
                lic.SetLicense(license_stream)
                print("✓ 许可证激活成功")
            finally:
                license_stream.Dispose()
                
        except Exception as e:
            print(f"⚠ 许可证激活失败: {e}")
            print("  将使用评估模式，输出文档会有水印")
            import traceback
            traceback.print_exc()
    
    def convert_document(self, source_path, template_path, output_path):
        """
        执行文档格式转换
        
        Args:
            source_path: 源文档路径
            template_path: 模板文档路径
            output_path: 输出文档路径
        
        Returns:
            str: 输出文档路径
        """
        print(f"\n开始转换文档: {source_path}")
        print(f"使用模板: {template_path}")
        
        try:
            # 加载源文档和模板
            source = Document(source_path)
            template = Document(template_path)
            
            # 复制模板的样式
            for style in template.Styles:
                if style.Name not in source.Styles:
                    source.Styles.AddCopy(style)
            
            # 应用模板的页面设置
            for i in range(min(source.Sections.Count, template.Sections.Count)):
                source_section = source.Sections[i]
                template_section = template.Sections[i]
                
                # 复制页面设置
                source_section.PageSetup.PageWidth = template_section.PageSetup.PageWidth
                source_section.PageSetup.PageHeight = template_section.PageSetup.PageHeight
                source_section.PageSetup.LeftMargin = template_section.PageSetup.LeftMargin
                source_section.PageSetup.RightMargin = template_section.PageSetup.RightMargin
                source_section.PageSetup.TopMargin = template_section.PageSetup.TopMargin
                source_section.PageSetup.BottomMargin = template_section.PageSetup.BottomMargin
                source_section.PageSetup.Orientation = template_section.PageSetup.Orientation
            
            # 保存输出文档
            source.Save(output_path, SaveFormat.Docx)
            
            print(f"✓ 转换完成！输出文档: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"✗ 转换失败: {e}")
            import traceback
            traceback.print_exc()
            return None

def main():
    """主函数"""
    print("========================================")
    print("Aspose.Words 文档格式转换器")
    print("========================================")
    
    # 解析命令行参数
    if len(sys.argv) == 4:
        source_path = sys.argv[1]
        template_path = sys.argv[2]
        output_path = sys.argv[3]
    else:
        # 默认参数
        script_dir = os.path.dirname(os.path.abspath(__file__))
        source_path = os.path.join(script_dir, "源论文.docx")
        template_path = os.path.join(script_dir, "论文模板.docx")
        output_path = os.path.join(script_dir, "格式化论文.docx")
    
    print(f"源论文: {source_path}")
    print(f"论文模板: {template_path}")
    print(f"输出文档: {output_path}")
    
    # 检查文件
    if not os.path.exists(source_path):
        print(f"错误: 源论文文件不存在: {source_path}")
        return 1
    
    if not os.path.exists(template_path):
        print(f"错误: 论文模板文件不存在: {template_path}")
        return 1
    
    # 执行转换
    try:
        formatter = AsposeWordFormatter()
        result = formatter.convert_document(source_path, template_path, output_path)
        
        if result:
            print("\n🎉 文档转换成功！")
            print("输出文件已按照模板格式进行了标准化处理")
            return 0
        else:
            return 1
            
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
