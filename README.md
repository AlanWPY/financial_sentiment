# 金融舆情分析系统

本项目是一个面向数据库课程期末大作业的金融舆情分析系统，覆盖数据采集、清洗入库、情感分析、主题建模、相关性研究与 Web 可视化展示的完整流程。系统围绕“金融舆情分析”这一应用场景构建，能够采集主流财经平台的新闻、公告与投资者评论，将异构文本统一写入本地 MySQL，并通过 Flask + Web 前端展示分析结果。

## 项目特点

- 多源金融舆情采集：新浪财经、东方财富财经新闻、巨潮资讯公告、东方财富股吧评论
- 本地 MySQL 存储：统一字段设计，支持去重、分页检索与结果回写
- 金融文本分析：SnowNLP 情感分析 + 金融词典修正 + LDA 主题建模
- 实证研究扩展：金融舆情与股票指数的相关性研究
- 专业前端展示：总览、情感分析、主题模型、舆情明细、采集控制
- 研究报告配套：自动生成图表、前端截图与 Word 报告

## 系统结构

```text
financial_sentiment/
├─ analysis/                    # 情感分析、主题建模、相关性研究
├─ backend/                     # Flask 后端与 MySQL 连接
├─ crawler/                     # 多源爬虫与数据扩充脚本
├─ data/                        # 中间数据与缓存目录
├─ frontend/                    # 前端页面、样式、脚本
├─ models/                      # 模型输出与词典等资源
├─ launch_financial_sentiment.ps1
├─ run.py                       # 系统主入口
├─ requirements.txt
└─ README.md

上一级目录：
期末大作业/
├─ financial_sentiment/         # 本项目
└─ reports/                     # 报告、图表、截图与最终文档
```

## 技术栈

- 后端：Flask、Flask-CORS
- 数据库：MySQL、PyMySQL
- 爬虫：requests、BeautifulSoup、lxml
- 数据分析：pandas、numpy、scikit-learn、gensim
- 中文 NLP：SnowNLP、jieba
- 可视化：ECharts、matplotlib、seaborn
- 报告生成：python-docx

## 数据表设计

系统当前主要使用以下数据表：

- `news`：舆情原始文本主表
- `sentiment_result`：情感分析结果
- `topic_result`：LDA 主题归因结果
- `crawl_log`：采集日志

`news` 表核心字段包括：

- `title`
- `content`
- `source`
- `url`
- `url_hash`
- `publish_time`
- `crawl_time`
- `category`
- `doc_type`
- `stock_code`
- `stock_name`
- `author`
- `keywords`

## 功能说明

### 1. 数据采集

系统支持以下金融舆情来源：

- 新浪财经滚动新闻
- 东方财富财经新闻
- 巨潮资讯上市公司公告
- 东方财富股吧评论

采集后统一进行：

- 文本清洗
- 时间解析
- 发布时间校验
- URL 哈希去重
- 字段标准化
- 入库 MySQL

### 2. 情感分析

情感分析采用两阶段方法：

1. 使用 SnowNLP 生成中文文本情感概率
2. 使用金融领域词典对情感方向进行修正

输出结果包括：

- `positive`
- `neutral`
- `negative`
- 情感得分
- 置信度

### 3. 主题建模

系统使用 LDA 模型对舆情文本进行主题抽取，支持识别如下典型金融主题：

- 股票市场
- 公司公告
- 监管治理
- 宏观经济
- 国际金融
- 产业趋势

### 4. Web 可视化

访问首页后可使用以下功能页面：

- 舆情总览
- 情感分析
- 主题模型
- 舆情明细
- 采集控制

其中“舆情明细”页面直接通过后端 API 从 MySQL 分页读取新闻数据表。

## 环境要求

- Windows 10 / 11
- Python 3.10+
- MySQL 8.x

本地数据库默认配置位于 [backend/database.py](E:/A研一下/大数据/期末大作业/financial_sentiment/backend/database.py)：

- Host: `localhost`
- Port: `3306`
- Database: `financial_sentiment`
- User: `root`

## 安装步骤

### 1. 安装依赖

```powershell
pip install -r requirements.txt
```

### 2. 准备 MySQL

确保本地 MySQL 已启动，并允许使用 `backend/database.py` 中的配置连接。

### 3. 启动系统

方式一：双击启动

- 直接双击：
  - [双击启动金融舆情分析系统.bat](E:/A研一下/大数据/期末大作业/financial_sentiment/双击启动金融舆情分析系统.bat)

方式二：命令行启动

```powershell
python run.py
```

启动成功后访问：

- [http://127.0.0.1:5000/#dashboard](http://127.0.0.1:5000/#dashboard)

## 常用脚本

### 运行主系统

```powershell
python run.py
```

### 扩充采集数据

```powershell
python crawler\enhanced_collect.py
python crawler\fast_expand.py
```

### 运行相关性研究

```powershell
python analysis\market_correlation.py
```

### 生成论文图表

```powershell
python ..\reports\generate_figures.py
```

### 生成最终报告

```powershell
python ..\reports\create_report_utf8.py
```

## API 概览

主要接口包括：

- `/api/stats`：系统统计信息
- `/api/sentiment`：情感与主题统计
- `/api/model-eval`：模型评估指标
- `/api/news`：新闻分页与筛选
- `/api/crawl`：触发爬虫采集
- `/api/analyze`：触发情感分析与主题建模
- `/api/wordcloud`：词云数据
- `/api/sources`：来源列表
- `/api/crawl-logs`：采集日志

## 项目输出

项目研究报告、图表和截图位于上一级目录的 `reports` 文件夹：

- `financial_sentiment_final_report.docx`
- `金融舆情分析系统期末报告_无乱码版.docx`
- 架构图、模型图、相关性图
- 前端总览截图、舆情明细截图

## 注意事项

- 本项目默认使用本地 MySQL，运行前请确认数据库服务已启动
- 部分在线数据源可能因网络、反爬或页面结构调整而发生变化
- 研究报告与图表依赖数据库中的最新数据，请在采集和分析完成后再生成

## 许可说明

本项目为课程作业与研究展示用途。
