#!/bin/bash

# Aspose.Words 安装脚本 (Ubuntu)
# 运行此脚本安装 Aspose.Words 依赖

echo "======================================="
echo "Aspose.Words 安装脚本 (Ubuntu)"
echo "======================================="
echo

# 检查 Python 是否存在
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python 3"
    echo "请安装 Python 3.12 或更高版本"
    exit 1
fi

# 检查 Python 版本
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
MAJOR_VERSION=$(echo $PYTHON_VERSION | cut -d. -f1)
MINOR_VERSION=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$MAJOR_VERSION" -lt 3 ] || [ "$MINOR_VERSION" -lt 12 ]; then
    echo "错误: 需要 Python 3.12 或更高版本"
    echo "当前版本: $PYTHON_VERSION"
    exit 1
fi

# 检查是否为 Linux 系统
if [ "$(uname -s)" != "Linux" ]; then
    echo "错误: 仅支持 Linux 系统"
    exit 1
fi

echo "正在运行安装..."
echo

# 运行安装脚本
python3 install.py

if [ $? -eq 0 ]; then
    echo
echo "安装完成！"
echo "可以运行 convert.py 进行文档转换"
echo
echo "示例命令:"
echo "  ./convert.sh 源文档.docx 模板.docx 输出文档.docx"
echo
else
    echo
echo "安装失败，请检查错误信息"
echo
fi