#!/bin/bash

# 定义颜色
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 显示使用说明
function show_usage {
    echo -e "${YELLOW}自动化API测试运行工具${NC}"
    echo
    echo "用法: $0 [选项]"
    echo
    echo "选项:"
    echo "  -a, --all        运行所有测试"
    echo "  -p, --api        只运行API测试"
    echo "  -u, --unit       只运行单元测试"
    echo "  -i, --integration 只运行集成测试"
    echo "  -c, --cov        生成测试覆盖率报告"
    echo "  -h, --help       显示此帮助信息"
    echo
    echo "示例:"
    echo "  $0 --api         运行所有API测试"
    echo "  $0 --cov         运行所有测试并生成覆盖率报告"
    echo "  $0 --api --cov   运行API测试并生成覆盖率报告"
    echo
}

# 安装测试依赖
function install_deps {
    echo -e "${GREEN}安装测试依赖...${NC}"
    pip install -r tests/requirements-test.txt
}

# 默认参数
RUN_ALL=0
RUN_API=0
RUN_UNIT=0
RUN_INTEGRATION=0
COVERAGE=0

# 解析命令行参数
if [ $# -eq 0 ]; then
    RUN_ALL=1
else
    for arg in "$@"
    do
        case $arg in
            -a|--all)
            RUN_ALL=1
            shift
            ;;
            -p|--api)
            RUN_API=1
            shift
            ;;
            -u|--unit)
            RUN_UNIT=1
            shift
            ;;
            -i|--integration)
            RUN_INTEGRATION=1
            shift
            ;;
            -c|--cov)
            COVERAGE=1
            shift
            ;;
            -h|--help)
            show_usage
            exit 0
            ;;
            *)
            echo -e "${RED}未知选项: $arg${NC}"
            show_usage
            exit 1
            ;;
        esac
    done
fi

# 安装依赖
install_deps

# 构建pytest命令
CMD="python -m pytest"

# 添加详细输出
CMD="$CMD -v"

# 添加测试标记
if [ $RUN_API -eq 1 ]; then
    CMD="$CMD -m api"
elif [ $RUN_UNIT -eq 1 ]; then
    CMD="$CMD -m unit"
elif [ $RUN_INTEGRATION -eq 1 ]; then
    CMD="$CMD -m integration"
fi

# 添加覆盖率报告
if [ $COVERAGE -eq 1 ]; then
    echo -e "${GREEN}生成测试覆盖率报告...${NC}"
    CMD="$CMD --cov=app tests/ --cov-report=html --cov-report=term"
fi

# 运行测试
echo -e "${GREEN}运行测试命令: ${YELLOW}$CMD${NC}"
$CMD

# 显示覆盖率报告位置
if [ $COVERAGE -eq 1 ]; then
    echo -e "${GREEN}覆盖率报告已生成在 htmlcov/ 目录${NC}"
    echo -e "${GREEN}可以通过浏览器打开 htmlcov/index.html 查看详细报告${NC}"
fi 