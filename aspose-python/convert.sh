#!/bin/bash

# Aspose.Words 转换脚本 (Ubuntu)
# 使用虚拟环境中的 Python 运行转换

echo "======================================="
echo "Aspose.Words 转换脚本 (Ubuntu)"
echo "======================================="
echo

# 检查参数
if [ $# -ne 3 ]; then
    echo "错误: 参数不足"
    echo "使用方法: ./convert.sh 源文档.docx 模板.docx 输出文档.docx"
    exit 1
fi

SOURCE_FILE="$1"
TEMPLATE_FILE="$2"
OUTPUT_FILE="$3"

# 检查文件是否存在
if [ ! -f "$SOURCE_FILE" ]; then
    echo "错误: 源文档文件不存在: $SOURCE_FILE"
    exit 1
fi

if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "错误: 模板文件不存在: $TEMPLATE_FILE"
    exit 1
fi

echo "源论文: $SOURCE_FILE"
echo "论文模板: $TEMPLATE_FILE"
echo "输出文档: $OUTPUT_FILE"
echo

# 检查虚拟环境是否存在
VENV_DIR="$(dirname "$0")/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "错误: 虚拟环境不存在，请先运行 install.sh"
    exit 1
fi

# 使用虚拟环境中的 Python 运行转换
PYTHON_EXECUTABLE="$VENV_DIR/bin/python3"

if [ ! -f "$PYTHON_EXECUTABLE" ]; then
    echo "错误: 虚拟环境中的 Python 不存在"
    exit 1
fi

echo "使用虚拟环境 Python 运行转换..."
echo

"$PYTHON_EXECUTABLE" "$(dirname "$0")/convert.py" "$SOURCE_FILE" "$TEMPLATE_FILE" "$OUTPUT_FILE"

if [ $? -eq 0 ]; then
    echo
echo "🎉 转换成功！"
echo "输出文件: $OUTPUT_FILE"
echo
else
    echo
echo "❌ 转换失败，请检查错误信息"
echo
fi