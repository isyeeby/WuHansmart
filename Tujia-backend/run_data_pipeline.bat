@echo off
chcp 65001 >nul
echo ============================================
echo 民宿价格分析系统 - 完整数据流程
echo ============================================
echo.
echo 流程说明:
echo   1. 导入JSON数据到MySQL
echo   2. 导出CSV供Hive导入
echo   3. 导入数据到Hive数据仓库
echo   4. 从Hive DWD层训练XGBoost模型
echo   5. 从Hive DWD层构建推荐模型
echo.

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Python未安装或未添加到PATH
    exit /b 1
)

echo [1/5] 安装依赖...
pip install -q pandas sqlalchemy pymysql xgboost scikit-learn joblib scipy
if errorlevel 1 (
    echo [警告] 部分依赖安装失败，继续执行...
)

echo.
echo [2/5] 导入数据到MySQL...
python scripts/import_data.py
if errorlevel 1 (
    echo [错误] 数据导入失败
    exit /b 1
)

echo.
echo [3/5] 导出数据到CSV...
python scripts/export_to_csv.py
if errorlevel 1 (
    echo [警告] CSV导出失败，继续...
)

echo.
echo [4/5] 导入数据到Hive...
echo 注意: 请确保Hive Docker容器已启动
echo       docker ps | findstr hive
python scripts/hive_docker_import.py
if errorlevel 1 (
    echo [警告] Hive导入失败，模型训练将使用MySQL数据...
)

echo.
echo [5/5] 训练机器学习模型（从Hive DWD层加载）...
echo.
echo 训练XGBoost价格预测模型...
python scripts/train_xgboost_model.py --source hive
if errorlevel 1 (
    echo [警告] XGBoost训练失败，尝试从MySQL加载...
    python scripts/train_xgboost_model.py --source mysql
)

echo.
echo 构建协同过滤推荐模型...
python scripts/build_recommendation_model.py
if errorlevel 1 (
    echo [警告] 推荐模型构建失败
)

echo.
echo ============================================
echo 数据处理流程完成！
echo ============================================
echo.
echo 模型训练数据来源: Hive DWD层 (推荐^)
echo   - 数据已清洗: 过滤异常价格和质量分<50的数据
echo   - 特征已标准化: 价格等级、评分等级、设施统计
echo.
echo 如果Hive不可用，会自动回退到MySQL数据源。
echo.
echo 启动后端服务：
echo   uvicorn app.main:app --reload
echo.
echo 查看数据流程文档：
echo   docs/ML_DATA_FLOW.md
echo.

pause
